"""Async Gitea API client."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

GITEA_URL = os.getenv("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")

_headers = {"Authorization": f"token {GITEA_TOKEN}"}


async def _get(path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(timeout=15, verify=False) as c:
        r = await c.get(f"{GITEA_URL}/api/v1{path}", headers=_headers, params=params or {})
        r.raise_for_status()
        return r.json()


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
    return None


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


async def list_pulls(owner: str, name: str, state: str = "open", limit: int = 20) -> list[dict]:
    return await _get(f"/repos/{owner}/{name}/pulls", {"state": state, "limit": limit})


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

    now = datetime.now(timezone.utc)
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
