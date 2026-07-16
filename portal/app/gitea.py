"""Async Gitea API client."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

GITEA_URL = os.getenv("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")

_headers = {"Authorization": f"token {GITEA_TOKEN}"}


async def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
) -> Any:
    """Send an authenticated Gitea API request and decode JSON responses."""
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        response = await client.request(
            method,
            f"{GITEA_URL}/api/v1{path}",
            headers=_headers,
            params=params or {},
            json=json,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()


async def _get(path: str, params: dict | None = None) -> Any:
    return await _request("GET", path, params=params)


# ── repos ────────────────────────────────────────────────────────────────

async def list_repos(limit: int = 50) -> list[dict]:
    """All repos visible to the token owner."""
    data = await _get("/repos/search", {"limit": limit, "sort": "updated"})
    return data.get("data", data) if isinstance(data, dict) else data


async def get_repo(owner: str, name: str) -> dict:
    return await _get(f"/repos/{owner}/{name}")


async def get_readme(owner: str, name: str) -> str | None:
    """Return decoded README content or None."""
    async with httpx.AsyncClient(timeout=15, verify=False) as c:
        r = await c.get(
            f"{GITEA_URL}/api/v1/repos/{owner}/{name}/readme",
            headers=_headers,
        )
        if r.status_code == 200:
            import base64
            data = r.json()
            return base64.b64decode(data.get("content", "")).decode(errors="replace")
    # Older Gitea versions may not expose /readme even when the file exists.
    for candidate in ("README.md", "README", "README.rst", "README.txt"):
        try:
            content = await get_file_content(owner, name, candidate)
        except httpx.HTTPError:
            continue
        if content is not None:
            return content
    return None


async def render_markdown(text: str, context: str) -> str:
    """Render Markdown through Gitea's sanitizer for repository-aware links."""
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        response = await client.post(
            f"{GITEA_URL}/api/v1/markdown",
            headers=_headers,
            json={"Text": text, "Mode": "gfm", "Context": context},
        )
        response.raise_for_status()

    # Gitea's renderer emits links for its configured origin without the
    # portal's reverse-proxy prefix. Keep repository-relative links in-app.
    return response.text.replace("http://localhost:3001/", "/gitea/")


async def list_contents(owner: str, name: str, path: str = "") -> list[dict]:
    return await _get(f"/repos/{owner}/{name}/contents/{path}")


async def get_file_content(owner: str, name: str, path: str) -> str | None:
    import base64
    data = await _get(f"/repos/{owner}/{name}/contents/{path}")
    if isinstance(data, dict) and data.get("content"):
        return base64.b64decode(data["content"]).decode(errors="replace")
    return None


# ── commits ──────────────────────────────────────────────────────────────

async def list_commits(owner: str, name: str, limit: int = 20) -> list[dict]:
    return await _get(f"/repos/{owner}/{name}/commits", {"limit": limit})


# ── actions / workflows ─────────────────────────────────────────────────

async def list_workflows(owner: str, name: str) -> list[dict]:
    data = await _get(f"/repos/{owner}/{name}/actions/workflows")
    return data.get("workflows", [])


async def list_workflow_runs(owner: str, name: str, limit: int = 30) -> list[dict]:
    data = await _get(f"/repos/{owner}/{name}/actions/runs", {"limit": limit})
    return data.get("workflow_runs", [])


async def list_all_workflow_runs(limit: int = 50) -> list[dict]:
    """All runs across repos visible to the token."""
    data = await _get("/user/actions/runs", {"limit": limit})
    return data.get("workflow_runs", [])


async def list_workflow_jobs(owner: str, name: str, run_id: int) -> list[dict]:
    data = await _get(f"/repos/{owner}/{name}/actions/runs/{run_id}/jobs")
    return data.get("jobs", [])


async def get_run(owner: str, name: str, run_id: int) -> dict:
    return await _get(f"/repos/{owner}/{name}/actions/runs/{run_id}")


# ── issues & pulls ───────────────────────────────────────────────────────

async def list_issues(owner: str, name: str, state: str = "open", limit: int = 20) -> list[dict]:
    return await _get(f"/repos/{owner}/{name}/issues", {"state": state, "limit": limit})


async def get_issue(owner: str, name: str, number: int) -> dict:
    return await _get(f"/repos/{owner}/{name}/issues/{number}")


async def add_issue_comment(owner: str, name: str, number: int, body: str) -> dict:
    return await _request(
        "POST",
        f"/repos/{owner}/{name}/issues/{number}/comments",
        json={"body": body},
    )


async def list_labels(owner: str, name: str) -> list[dict]:
    return await _get(f"/repos/{owner}/{name}/labels", {"limit": 100})


async def create_label(owner: str, name: str, label: str, color: str, description: str) -> dict:
    return await _request(
        "POST",
        f"/repos/{owner}/{name}/labels",
        json={"name": label, "color": color, "description": description},
    )


async def add_issue_labels(owner: str, name: str, number: int, label_ids: list[int]) -> list[dict]:
    return await _request(
        "POST",
        f"/repos/{owner}/{name}/issues/{number}/labels",
        json={"labels": label_ids},
    )


async def list_pulls(owner: str, name: str, state: str = "open", limit: int = 20) -> list[dict]:
    return await _get(f"/repos/{owner}/{name}/pulls", {"state": state, "limit": limit})


async def create_pull(
    owner: str,
    name: str,
    *,
    title: str,
    body: str,
    head: str,
    base: str,
) -> dict:
    """Create a pull request. Draft intent is expressed by the caller's title."""
    return await _request(
        "POST",
        f"/repos/{owner}/{name}/pulls",
        json={
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "allow_maintainer_edit": True,
        },
    )


# ── activity feed ────────────────────────────────────────────────────────

async def list_activity(username: str = "agent", limit: int = 30) -> list[dict]:
    return await _get(f"/users/{username}/activities/feeds", {"limit": limit})


# ── aggregated stats ─────────────────────────────────────────────────────

async def get_stats() -> dict:
    """Quick aggregated stats across all repos."""
    repos = await list_repos(limit=100)
    total = len(repos)

    total_stars = sum(r.get("stars_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    total_size = sum(r.get("size", 0) for r in repos)

    now = datetime.now(UTC)
    active_today = 0
    active_week = 0
    for r in repos:
        updated = r.get("updated_at", "")
        if updated:
            try:
                dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if now - dt < timedelta(days=1):
                    active_today += 1
                if now - dt < timedelta(days=7):
                    active_week += 1
            except (ValueError, TypeError):
                pass

    return {
        "total_repos": total,
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_size_kb": total_size,
        "active_today": active_today,
        "active_week": active_week,
    }


async def get_actions_stats() -> dict:
    """Aggregate action run stats."""
    runs = await list_all_workflow_runs(limit=100)
    total = len(runs)
    success = sum(1 for r in runs if r.get("status") == "success")
    failure = sum(1 for r in runs if r.get("status") == "failure")
    running = sum(1 for r in runs if r.get("status") in ("running", "waiting"))
    queued = sum(1 for r in runs if r.get("status") == "queued")
    return {
        "total": total,
        "success": success,
        "failure": failure,
        "running": running,
        "queued": queued,
    }
