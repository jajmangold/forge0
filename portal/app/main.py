"""Forge0 Portal — FastAPI app."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from . import auth, gitea
from .chat import router as chat_router
from .dogfood import DogfoodError, DogfoodService
from .experiment_queue import ExperimentQueue, ExperimentSubmission
from .research import ResearchRequest, ResearchService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    supervisor_enabled = os.getenv("FORGE0_SUPERVISOR_ENABLED", "true").lower() == "true"
    if supervisor_enabled:
        await get_dogfood_service().start()
    try:
        yield
    finally:
        if supervisor_enabled and _dogfood_service is not None:
            await _dogfood_service.stop()


app = FastAPI(title="Forge0 Portal", docs_url=None, redoc_url=None, lifespan=lifespan)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.globals["gitea_link"] = gitea.web_link
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

GITEA_INTERNAL = os.getenv("GITEA_URL", "http://gitea:3000")
_dogfood_service: DogfoodService | None = None
_experiment_queue: ExperimentQueue | None = None
_research_service: ResearchService | None = None

# Include chat router
app.include_router(chat_router)


@app.middleware("http")
async def require_gitea_identity(request: Request, call_next):
    """Protect interactive portal routes when OAuth has been provisioned."""
    config = auth.AuthConfig.from_env()
    request.state.user = auth.current_user(request, config) if config else None
    if config and request.state.user is None:
        path = request.url.path
        public = (
            path in {"/healthz", "/readyz", "/gitea", "/gitea-login"}
            or path.startswith(("/static/", "/auth/", "/gitea/"))
            or path == "/api/webhooks/gitea"
            or (path.startswith("/api/dogfood/run/") and request.method == "POST")
        )
        if not public:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            destination = auth.safe_next(f"{path}?{request.url.query}" if request.url.query else path)
            return RedirectResponse(f"/auth/login?{urlencode({'next': destination})}", status_code=302)
    return await call_next(request)


@app.get("/auth/login", include_in_schema=False)
async def auth_login(next: str = "/"):
    config = auth.AuthConfig.from_env()
    if config is None:
        raise HTTPException(status_code=503, detail="Gitea OAuth is not configured")
    url, state_cookie = auth.authorization(config, auth.safe_next(next))
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        auth.STATE_COOKIE,
        state_cookie,
        max_age=auth.STATE_MAX_AGE,
        httponly=True,
        secure=config.secure_cookies,
        samesite="lax",
        path="/auth/callback",
    )
    return response


@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(request: Request, code: str = "", state: str = ""):
    config = auth.AuthConfig.from_env()
    if config is None:
        raise HTTPException(status_code=503, detail="Gitea OAuth is not configured")
    saved = auth.unsign(request.cookies.get(auth.STATE_COOKIE, ""), config.session_secret, auth.STATE_MAX_AGE)
    if not code or not state or not saved or not hmac.compare_digest(state, str(saved.get("nonce", ""))):
        return templates.TemplateResponse(
            request,
            "auth_error.html",
            {
                "title": "Sign-in expired",
                "message": "Your Gitea sign-in request expired or is invalid. Start a fresh sign-in to continue.",
                "status_code": 400,
            },
            status_code=400,
        )
    identity_data = await auth.exchange_code(config, code, str(saved.get("verifier", "")))
    try:
        identity = auth.normalize_identity(identity_data, config)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        return templates.TemplateResponse(
            request,
            "auth_error.html",
            {
                "title": "Account not allowed",
                "message": "This Gitea account is not allowed to use Forge0.",
                "status_code": 403,
            },
            status_code=403,
        )
    response = RedirectResponse(auth.safe_next(str(saved.get("next", "/"))), status_code=302)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.sign(identity, config.session_secret),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        secure=config.secure_cookies,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(auth.STATE_COOKIE, path="/auth/callback")
    return response


@app.post("/auth/logout", include_in_schema=False)
async def auth_logout():
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response


def get_dogfood_service() -> DogfoodService:
    """Lazily initialize persistent dogfood state after configuration is loaded."""
    global _dogfood_service
    if _dogfood_service is None:
        _dogfood_service = DogfoodService()
    return _dogfood_service


def get_experiment_queue() -> ExperimentQueue:
    """Lazily open the shared durable experiment queue."""
    global _experiment_queue
    if _experiment_queue is None:
        _experiment_queue = ExperimentQueue()
    return _experiment_queue


def get_research_service() -> ResearchService:
    """Lazily open the durable research cache."""
    global _research_service
    if _research_service is None:
        _research_service = ResearchService()
    return _research_service


def _time_ago(dt_str: str) -> str:
    """Convert ISO datetime to '2m ago' style string."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        diff = datetime.now(UTC) - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except (ValueError, TypeError):
        return dt_str


def _format_size(kb: int) -> str:
    if kb < 1024:
        return f"{kb} KB"
    if kb < 1024 * 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb / (1024 * 1024):.1f} GB"


templates.env.filters["time_ago"] = _time_ago
templates.env.filters["format_size"] = _format_size
# Users access Gitea through the portal proxy at /gitea/
templates.env.globals["gitea_url"] = "/gitea"


# ── Gitea reverse proxy ─────────────────────────────────────────────────

@app.api_route("/gitea/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def gitea_proxy(request: Request, path: str):
    """Reverse proxy to Gitea. Users access Gitea via /gitea/ from the portal.
    Strip /gitea/ prefix — Gitea routes at / internally.
    ROOT_URL tells Gitea to generate /gitea/... URLs for assets/links."""
    target_url = f"{GITEA_INTERNAL}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Forward end-to-end headers. Hop-by-hop headers and Host must be rebuilt by
    # the HTTP client; compression is disabled because httpx decodes the body.
    excluded_headers = {
        "accept-encoding",
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
    headers = {name: value for name, value in request.headers.items() if name.lower() not in excluded_headers}
    headers["Accept-Encoding"] = "identity"  # no compression

    # Gitea and OAuth need one canonical public origin, even when this portal is
    # running as a shadow instance on another local port.
    public_origin = urlsplit(gitea.GITEA_PUBLIC_URL)
    headers["Host"] = public_origin.netloc
    headers["X-Forwarded-Host"] = public_origin.netloc
    headers["X-Forwarded-Proto"] = public_origin.scheme
    headers["X-Forwarded-For"] = request.client.host if request.client else "127.0.0.1"

    body = await request.body()

    async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=False) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
        )
        # Read content INSIDE the async block (before client closes)
        resp_body = resp.content
        resp_status = resp.status_code
        resp_ct = resp.headers.get("content-type")
        resp_location = resp.headers.get("location")
        resp_cache = resp.headers.get("cache-control")
        resp_cookies = resp.headers.get_list("set-cookie")

    # Rewrite response headers — never forward Content-Length
    # (httpx decompresses gzip, so the actual body size differs from the header)
    resp_headers = {}
    if resp_ct:
        resp_headers["content-type"] = resp_ct
    if resp_cache:
        resp_headers["cache-control"] = resp_cache

    # Rewrite redirects: Gitea sends /gitea/... (from ROOT_URL), keep as-is
    if resp_location:
        resp_headers["location"] = resp_location

    response = Response(
        content=resp_body,
        status_code=resp_status,
        headers=resp_headers,
    )
    for cookie in resp_cookies:
        response.headers.append("set-cookie", cookie)
    return response


@app.get("/gitea", include_in_schema=False)
async def gitea_root_redirect():
    """Redirect /gitea to /gitea/."""
    return RedirectResponse(url="/gitea/", status_code=308)


@app.get("/gitea-login", include_in_schema=False)
async def gitea_auto_login(request: Request, next: str = "/gitea/"):
    """Auto-sign in to Gitea and redirect. Creates a web session so the user
    is authenticated when they land on Gitea's UI."""
    safe_destination = (
        next.startswith("/gitea/")
        and "\\" not in next
        and not any(character in next for character in ("\r", "\n", "\0"))
    )
    destination = next if safe_destination else "/gitea/"
    oauth_config = auth.AuthConfig.from_env()
    if oauth_config is not None:
        if request.state.user is None:
            return RedirectResponse(
                url=f"/auth/login?{urlencode({'next': destination})}", status_code=302
            )
        return RedirectResponse(
            url=gitea.public_url(destination.removeprefix("/gitea/")), status_code=302
        )
    if os.getenv("GITEA_AUTO_LOGIN", "true").lower() != "true":
        query = urlencode({"redirect_to": destination})
        return RedirectResponse(
            url=f"{gitea.public_url('user/login')}?{query}",
            status_code=302,
        )

    gitea_user = os.getenv("GITEA_ADMIN_USER", "agent")
    gitea_pass = os.getenv("GITEA_ADMIN_PASS", "agentpass123")

    async with httpx.AsyncClient(timeout=15, verify=False, follow_redirects=False) as client:
        # POST login form
        login_resp = await client.post(
            f"{GITEA_INTERNAL}/user/login",
            data={
                "user_name": gitea_user,
                "password": gitea_pass,
            },
        )

    # Redirect to Gitea, forwarding session cookies
    public_destination = gitea.public_url(destination.removeprefix("/gitea/"))
    response = Response(status_code=302, headers={"Location": public_destination})
    # Parse all Set-Cookie headers — keep only the LAST value per cookie name
    # (Gitea sets the same cookie multiple times: first a temp, then the real session)
    seen = {}
    for raw_cookie in login_resp.headers.get_list("set-cookie"):
        parts = raw_cookie.split(";")
        if not parts or "=" not in parts[0]:
            continue
        name, value = parts[0].strip().split("=", 1)
        name = name.strip()
        value = value.strip()
        # Skip cookies that delete (Max-Age=0) or have empty values
        if "Max-Age=0" in raw_cookie or not value:
            # Remove from seen if a delete comes after a set
            seen.pop(name, None)
            continue
        # Always overwrite — last SET wins
        seen[name] = value

    for name, value in seen.items():
        response.set_cookie(
            key=name,
            value=value,
            path="/",
            httponly=True,
        )

    return response


@app.get("/healthz", include_in_schema=False)
async def healthcheck() -> dict[str, str]:
    """Process liveness endpoint for Docker and operators."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readiness() -> Response:
    """Report whether the portal can authenticate to its Gitea dependency."""
    try:
        await asyncio.wait_for(gitea.list_repos(limit=1), timeout=3)
    except (httpx.HTTPError, TimeoutError):
        return Response(content='{"status":"unavailable"}', status_code=503, media_type="application/json")
    return Response(content='{"status":"ready"}', media_type="application/json")


# ── pages ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    repos, actions_stats, stats = await asyncio.gather(
        gitea.list_repos(),
        gitea.get_actions_stats(),
        gitea.get_stats(),
    )
    return templates.TemplateResponse(request, "dashboard.html", {
        "repos": repos,
        "actions_stats": actions_stats,
        "stats": stats,
        "page": "dashboard",
    })


@app.get("/actions", response_class=HTMLResponse)
async def actions_page(request: Request):
    runs = await gitea.list_all_workflow_runs(limit=60)
    return templates.TemplateResponse(request, "actions.html", {
        "runs": runs,
        "page": "actions",
    })


@app.get("/repo/{owner}/{name:path}", response_class=HTMLResponse)
async def repo_detail(request: Request, owner: str, name: str):
    repo, commits, runs, issues, pulls = await asyncio.gather(
        gitea.get_repo(owner, name),
        gitea.list_commits(owner, name, limit=15),
        gitea.list_workflow_runs(owner, name, limit=20),
        gitea.list_issues(owner, name, limit=10),
        gitea.list_pulls(owner, name, limit=10),
        return_exceptions=True,
    )
    # Handle errors gracefully
    if isinstance(repo, Exception):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Repository not found",
                "message": "The repository may have moved, been removed, or is temporarily unavailable.",
                "status_code": 404,
                "page": "repos",
            },
            status_code=404,
        )

    readme = None
    readme_html = None
    try:
        readme = await gitea.get_readme(owner, name)
    except Exception:
        pass
    if readme:
        try:
            readme_html = Markup(await gitea.render_markdown(readme, f"{owner}/{name}"))
        except Exception:
            pass

    file_tree = []
    try:
        file_tree = await gitea.list_contents(owner, name)
    except Exception:
        pass

    return templates.TemplateResponse(request, "repo.html", {
        "repo": repo,
        "commits": commits if not isinstance(commits, Exception) else [],
        "runs": runs if not isinstance(runs, Exception) else [],
        "issues": issues if not isinstance(issues, Exception) else [],
        "pulls": pulls if not isinstance(pulls, Exception) else [],
        "readme": readme,
        "readme_html": readme_html,
        "file_tree": file_tree if not isinstance(file_tree, Exception) else [],
        "page": "repos",
    })


# ── self-extension / dogfooding ─────────────────────────────────────────

@app.get("/dogfood", response_class=HTMLResponse)
async def dogfood_page(request: Request):
    service = get_dogfood_service()
    return templates.TemplateResponse(request, "dogfood.html", {
        "runs": service.list_runs(),
        "config": service.config,
        "page": "dogfood",
    })


@app.get("/partials/dogfood-runs", response_class=HTMLResponse)
async def dogfood_runs_partial(request: Request):
    return templates.TemplateResponse(request, "_dogfood_runs.html", {
        "runs": get_dogfood_service().list_runs(),
    })


@app.get("/api/dogfood/runs/{run_id}")
async def dogfood_run(run_id: str) -> dict:
    record = get_dogfood_service().get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record.to_dict()


@app.post("/api/dogfood/run/{owner}/{repo}/{issue_number}", status_code=202)
async def start_dogfood_run(
    owner: str,
    repo: str,
    issue_number: int,
    operator_token: str = Header(default="", alias="X-Forge0-Operator-Token"),
) -> dict[str, str]:
    service = get_dogfood_service()
    if not service.config.operator_token:
        raise HTTPException(status_code=503, detail="FORGE0_OPERATOR_TOKEN is not configured")
    if not service.verify_operator_token(operator_token):
        raise HTTPException(status_code=401, detail="Invalid operator token")
    try:
        record = await service.enqueue(owner, repo, issue_number)
    except DogfoodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Gitea request failed") from exc
    return {"run_id": record.id, "status": record.status.value}


@app.post("/api/webhooks/gitea", status_code=202)
async def gitea_webhook(
    request: Request,
    signature: str = Header(default="", alias="X-Gitea-Signature"),
    event: str = Header(default="", alias="X-Gitea-Event"),
) -> dict[str, str]:
    service = get_dogfood_service()
    body = await request.body()
    if not service.config.webhook_secret:
        raise HTTPException(status_code=503, detail="FORGE0_WEBHOOK_SECRET is not configured")
    if not service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    if event != "issues":
        return {"status": "ignored"}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
    target = service.webhook_issue(payload)
    if target is None:
        return {"status": "ignored"}
    try:
        record = await service.enqueue(*target)
    except (DogfoodError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "queued", "run_id": record.id}


# ── bounded experiments and research ────────────────────────────────────

@app.get("/lab", response_class=HTMLResponse)
async def lab_page(request: Request):
    return templates.TemplateResponse(request, "lab.html", {
        "experiments": get_experiment_queue().list(),
        "page": "lab",
    })


@app.get("/partials/experiments", response_class=HTMLResponse)
async def experiments_partial(request: Request):
    return templates.TemplateResponse(request, "_experiments.html", {
        "experiments": get_experiment_queue().list(),
    })


@app.get("/experiments/{job_id}", response_class=HTMLResponse)
async def experiment_detail(request: Request, job_id: str):
    """Render a bounded, human-readable projection of one durable experiment."""
    record = get_experiment_queue().get(job_id)
    if record is None:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Experiment not found",
                "message": "The experiment id is unknown or its durable record is no longer available.",
                "status_code": 404,
                "page": "lab",
            },
            status_code=404,
        )

    result = record.result if isinstance(record.result, dict) else {}
    objectives = result.get("objectives", [])
    if not isinstance(objectives, list):
        objectives = []
    frontier = result.get("frontier", result.get("pareto_frontier", []))
    if not isinstance(frontier, list):
        frontier = []
    frontier_ids = {
        item.get("id") for item in frontier if isinstance(item, dict) and item.get("id") is not None
    }
    frontier_indexes = {
        item for item in frontier if isinstance(item, int) and not isinstance(item, bool)
    }
    candidates = []
    raw_candidates = result.get("candidates", [])
    if isinstance(raw_candidates, list):
        for index, candidate in enumerate(raw_candidates):
            if not isinstance(candidate, dict):
                continue
            candidate_id = candidate.get("id")
            candidates.append({
                "index": index,
                "id": candidate_id or f"Candidate {index + 1}",
                "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
                "feasible": candidate.get("feasible", True),
                "frontier": (
                    index in frontier_indexes
                    or (candidate_id is not None and candidate_id in frontier_ids)
                    or candidate in frontier
                ),
                "error": str(candidate.get("error") or "")[:500],
            })
    raw_wandb = result.get("wandb")
    wandb: dict[str, Any] = raw_wandb if isinstance(raw_wandb, dict) else {}
    safe_wandb = {
        key: str(wandb[key])[:500]
        for key in ("mode", "run_id", "status", "error")
        if wandb.get(key) is not None
    }
    return templates.TemplateResponse(request, "experiment_detail.html", {
        "experiment": record,
        "result": result,
        "objectives": objectives,
        "candidates": candidates,
        "wandb": safe_wandb,
        "bounded_error": str(record.error or "")[:1000],
        "page": "lab",
    })


@app.post("/api/experiments", status_code=202)
async def enqueue_experiment(submission: ExperimentSubmission) -> dict:
    """Queue a validated static harness; manifests can never supply commands."""
    return get_experiment_queue().enqueue(submission).to_dict()


@app.get("/api/experiments")
async def list_experiments(limit: int = 50) -> list[dict]:
    return [record.to_dict() for record in get_experiment_queue().list(limit)]


@app.get("/api/experiments/{job_id}")
async def get_experiment(job_id: str) -> dict:
    record = get_experiment_queue().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return record.to_dict()


@app.post("/api/research")
async def run_research(request: ResearchRequest) -> dict:
    """Run or reuse a bounded evidence review and optionally publish its wiki page."""
    try:
        return await get_research_service().run(request)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Research source or Gitea request failed") from exc


# ── HTMX partial endpoints (for auto-refresh) ───────────────────────────

@app.get("/partials/stats", response_class=HTMLResponse)
async def partial_stats(request: Request):
    stats, actions_stats = await asyncio.gather(
        gitea.get_stats(),
        gitea.get_actions_stats(),
    )
    return templates.TemplateResponse(request, "_stats.html", {
        "stats": stats,
        "actions_stats": actions_stats,
    })


@app.get("/partials/repos", response_class=HTMLResponse)
async def partial_repos(request: Request):
    repos = await gitea.list_repos()
    return templates.TemplateResponse(request, "_repos.html", {
        "repos": repos,
    })


@app.get("/partials/runs", response_class=HTMLResponse)
async def partial_runs(request: Request):
    runs = await gitea.list_all_workflow_runs(limit=60)
    return templates.TemplateResponse(request, "_runs.html", {
        "runs": runs,
    })
