"""Forge0 Portal — FastAPI app."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import gitea
from .chat import router as chat_router

app = FastAPI(title="Forge0 Portal", docs_url=None, redoc_url=None)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

GITEA_INTERNAL = os.getenv("GITEA_URL", "http://gitea:3000")

# Include chat router
app.include_router(chat_router)


def _time_ago(dt_str: str) -> str:
    """Convert ISO datetime to '2m ago' style string."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
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

    # Forward headers — strip Accept-Encoding so Gitea returns uncompressed
    # (Gitea's Content-Length is for compressed body, httpx decompresses = mismatch)
    headers = {}
    for name in ("accept", "content-type", "authorization", "cookie"):
        val = request.headers.get(name)
        if val:
            headers[name] = val
    headers["Accept-Encoding"] = "identity"  # no compression

    # Tell Gitea the original request came from localhost:3001 (the portal)
    headers["X-Forwarded-Host"] = request.headers.get("host", "localhost:3001")
    headers["X-Forwarded-Proto"] = "http"
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

    return Response(
        content=resp_body,
        status_code=resp_status,
        headers=resp_headers,
    )


@app.get("/gitea", include_in_schema=False)
async def gitea_root_redirect():
    """Redirect /gitea to /gitea/."""
    return HTMLResponse(
        status_code=301,
        headers={"Location": "/gitea/"},
    )


@app.get("/gitea-login", include_in_schema=False)
async def gitea_auto_login(request: Request):
    """Auto-sign in to Gitea and redirect. Creates a web session so the user
    is authenticated when they land on Gitea's UI."""
    import os
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
    response = Response(status_code=302, headers={"Location": "/gitea/"})
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


# ── pages ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    repos, actions_stats, stats = await asyncio.gather(
        gitea.list_repos(),
        gitea.get_actions_stats(),
        gitea.get_stats(),
    )
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "repos": repos,
        "actions_stats": actions_stats,
        "stats": stats,
        "page": "dashboard",
    })


@app.get("/actions", response_class=HTMLResponse)
async def actions_page(request: Request):
    runs = await gitea.list_all_workflow_runs(limit=60)
    return templates.TemplateResponse("actions.html", {
        "request": request,
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
        return HTMLResponse(f"<h1>Repo not found</h1><p>{repo}</p>", status_code=404)

    readme = None
    try:
        readme = await gitea.get_readme(owner, name)
    except Exception:
        pass

    file_tree = []
    try:
        file_tree = await gitea.list_contents(owner, name)
    except Exception:
        pass

    return templates.TemplateResponse("repo.html", {
        "request": request,
        "repo": repo,
        "commits": commits if not isinstance(commits, Exception) else [],
        "runs": runs if not isinstance(runs, Exception) else [],
        "issues": issues if not isinstance(issues, Exception) else [],
        "pulls": pulls if not isinstance(pulls, Exception) else [],
        "readme": readme,
        "file_tree": file_tree if not isinstance(file_tree, Exception) else [],
        "page": "repos",
    })


# ── HTMX partial endpoints (for auto-refresh) ───────────────────────────

@app.get("/partials/stats", response_class=HTMLResponse)
async def partial_stats(request: Request):
    stats, actions_stats = await asyncio.gather(
        gitea.get_stats(),
        gitea.get_actions_stats(),
    )
    return templates.TemplateResponse("_stats.html", {
        "request": request,
        "stats": stats,
        "actions_stats": actions_stats,
    })


@app.get("/partials/repos", response_class=HTMLResponse)
async def partial_repos(request: Request):
    repos = await gitea.list_repos()
    return templates.TemplateResponse("_repos.html", {
        "request": request,
        "repos": repos,
    })


@app.get("/partials/runs", response_class=HTMLResponse)
async def partial_runs(request: Request):
    runs = await gitea.list_all_workflow_runs(limit=60)
    return templates.TemplateResponse("_runs.html", {
        "request": request,
        "runs": runs,
    })
