"""Portal route and safety regression tests."""

import subprocess
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app import auth, gitea
from app.coordination import AgentCoordinator, AgentLock, AgentRole, TaskStatus
from app.main import app
from app.rollback import RollbackManager, SafeCodeChanger
from app.stuck_detection import Action, CostTracker, StuckDetector
from fastapi import HTTPException
from fastapi.testclient import TestClient

client = TestClient(app)


def configure_oauth(monkeypatch) -> None:
    monkeypatch.setenv("GITEA_OAUTH_CLIENT_ID", "portal-client")
    monkeypatch.setenv("GITEA_OAUTH_CLIENT_SECRET", "portal-secret")
    monkeypatch.setenv("FORGE0_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("FORGE0_ALLOWED_USERS", "josh")


def test_healthcheck() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_oauth_protects_pages_and_apis(monkeypatch) -> None:
    configure_oauth(monkeypatch)

    page = client.get("/actions?status=failed", follow_redirects=False)
    api = client.post("/api/chat/owner/repo", json={"query": "hello"})

    assert page.status_code == 302
    assert page.headers["location"] == "/auth/login?next=%2Factions%3Fstatus%3Dfailed"
    assert api.status_code == 401
    assert api.json() == {"detail": "Authentication required"}


def test_oauth_login_uses_pkce_and_signed_state(monkeypatch) -> None:
    configure_oauth(monkeypatch)

    response = client.get("/auth/login?next=/dogfood", follow_redirects=False)
    query = parse_qs(urlsplit(response.headers["location"]).query)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:3001/gitea/login/oauth/authorize?"
    )
    assert query["client_id"] == ["portal-client"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid profile email"]
    assert auth.STATE_COOKIE in response.cookies
    saved = auth.unsign(response.cookies[auth.STATE_COOKIE], "test-session-secret", auth.STATE_MAX_AGE)
    assert saved is not None
    assert saved["next"] == "/dogfood"
    assert saved["nonce"] == query["state"][0]


def test_oauth_callback_creates_session_for_allowed_gitea_user(monkeypatch) -> None:
    configure_oauth(monkeypatch)
    oauth_client = TestClient(app)
    login = oauth_client.get("/auth/login?next=/actions", follow_redirects=False)
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]

    with patch(
        "app.main.auth.exchange_code",
        new=AsyncMock(return_value={"preferred_username": "josh", "email": "jajmangold@gmail.com"}),
    ):
        response = oauth_client.get(
            f"/auth/callback?code=valid-code&state={state}", follow_redirects=False
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/actions"
    session = auth.unsign(
        response.cookies[auth.SESSION_COOKIE], "test-session-secret", auth.SESSION_MAX_AGE
    )
    assert session is not None
    assert session["login"] == "josh"
    assert "valid-code" not in response.headers["set-cookie"]


def test_oauth_rejects_tampered_state_and_unapproved_users(monkeypatch) -> None:
    configure_oauth(monkeypatch)
    oauth_client = TestClient(app)
    login = oauth_client.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]

    tampered = oauth_client.get(
        f"/auth/callback?code=code&state={state}x", follow_redirects=False
    )
    assert tampered.status_code == 400

    config = auth.AuthConfig.from_env()
    assert config is not None
    with pytest.raises(HTTPException) as rejected:
        auth.normalize_identity({"preferred_username": "agent"}, config)
    assert rejected.value.status_code == 403


def test_signed_session_expires_and_detects_tampering() -> None:
    expired = auth.sign({"login": "josh", "iat": int(time.time()) - auth.SESSION_MAX_AGE - 1}, "secret")
    valid = auth.sign({"login": "josh", "iat": int(time.time())}, "secret")

    assert auth.unsign(expired, "secret", auth.SESSION_MAX_AGE) is None
    assert auth.unsign(f"{valid}x", "secret", auth.SESSION_MAX_AGE) is None
    assert auth.unsign("not-base64.unsigned", "secret", auth.SESSION_MAX_AGE) is None


def test_empty_allowlist_denies_every_account(monkeypatch) -> None:
    configure_oauth(monkeypatch)
    monkeypatch.setenv("FORGE0_ALLOWED_USERS", "")
    config = auth.AuthConfig.from_env()

    assert config is not None
    with pytest.raises(HTTPException) as rejected:
        auth.normalize_identity({"preferred_username": "josh"}, config)
    assert rejected.value.status_code == 403


def test_auto_login_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("GITEA_AUTO_LOGIN", "false")

    response = client.get("/gitea-login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://localhost:3001/gitea/user/login?redirect_to=%2Fgitea%2F"
    )


def test_gitea_login_preserves_safe_destination(monkeypatch) -> None:
    monkeypatch.setenv("GITEA_AUTO_LOGIN", "false")

    response = client.get(
        "/gitea-login?next=/gitea/owner/repo/src/branch/main/README.md",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].endswith(
        "redirect_to=%2Fgitea%2Fowner%2Frepo%2Fsrc%2Fbranch%2Fmain%2FREADME.md"
    )


def test_gitea_login_rejects_external_destination(monkeypatch) -> None:
    monkeypatch.setenv("GITEA_AUTO_LOGIN", "false")

    response = client.get("/gitea-login?next=https://example.com", follow_redirects=False)

    assert response.headers["location"] == (
        "http://localhost:3001/gitea/user/login?redirect_to=%2Fgitea%2F"
    )


def test_integrated_gitea_login_is_enabled_for_loopback_default(monkeypatch) -> None:
    monkeypatch.delenv("GITEA_AUTO_LOGIN", raising=False)
    login_response = Mock()
    login_response.headers.get_list.return_value = [
        "i_like_gitea=session-value; Path=/gitea; HttpOnly; SameSite=Lax"
    ]
    with patch("app.main.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=login_response
        )
        response = client.get(
            "/gitea-login?next=/gitea/owner/repo",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3001/gitea/owner/repo"
    assert "i_like_gitea=session-value" in response.headers["set-cookie"]


def test_gitea_proxy_forwards_the_canonical_public_origin() -> None:
    upstream = Mock(
        content=b"ok",
        status_code=200,
        headers=httpx.Headers({"content-type": "text/plain"}),
    )
    with patch("app.main.httpx.AsyncClient") as client_class:
        request = AsyncMock(return_value=upstream)
        client_class.return_value.__aenter__.return_value.request = request
        response = client.get("/gitea/example", headers={"host": "localhost:3999"})

    assert response.status_code == 200
    forwarded = request.await_args.kwargs["headers"]
    assert forwarded["Host"] == "localhost:3001"
    assert forwarded["X-Forwarded-Host"] == "localhost:3001"
    assert forwarded["X-Forwarded-Proto"] == "http"


def test_chat_rejects_empty_queries() -> None:
    response = client.post("/api/chat/owner/repo", json={"query": "", "history": []})

    assert response.status_code == 422


def test_chat_reports_missing_llm_configuration(monkeypatch) -> None:
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)

    with patch("app.chat.load_project_context", new=AsyncMock(return_value="context")):
        response = client.post("/api/chat/owner/repo", json={"query": "What is this?"})

    assert response.status_code == 503
    assert "OPENCODE_API_KEY" in response.json()["detail"]


def test_chat_template_renders_messages_as_text() -> None:
    response = client.get("/repo/owner/repo/chat")

    assert response.status_code == 200
    assert "messageContent.textContent = content" in response.text
    assert "div.innerHTML = `<div class=\"message-content\">" not in response.text


def test_dashboard_renders_usable_navigation_and_compact_metrics() -> None:
    with (
        patch("app.main.gitea.list_repos", new=AsyncMock(return_value=[])),
        patch(
            "app.main.gitea.get_actions_stats",
            new=AsyncMock(return_value={"running": 0, "queued": 1, "success": 2, "failure": 0}),
        ),
        patch(
            "app.main.gitea.get_stats",
            new=AsyncMock(return_value={"total_repos": 0, "active_today": 0, "active_week": 0}),
        ),
    ):
        response = client.get("/")

    assert response.status_code == 200
    assert 'aria-label="Primary navigation"' in response.text
    assert 'id="commandPalette"' in response.text
    assert 'id="connectionNotice"' in response.text
    assert 'data-refresh-url="/partials/stats"' in response.text
    assert "unpkg.com/htmx" not in response.text
    assert "await fetch(element.dataset.refreshUrl" in response.text
    assert "Build, review, and ship with context." in response.text
    assert 'class="stats"' in response.text


def test_actions_table_has_mobile_labels() -> None:
    run = {
        "status": "success",
        "name": "verify",
        "repository": None,
        "head_branch": "main",
        "event": "push",
        "updated_at": "2026-07-16T00:00:00Z",
    }
    with patch("app.main.gitea.list_all_workflow_runs", new=AsyncMock(return_value=[run])):
        response = client.get("/actions")

    assert response.status_code == 200
    assert 'data-label="Status"' in response.text
    assert 'data-label="Repository"' in response.text
    assert "refreshes automatically" in response.text


def test_repository_failure_uses_safe_app_shell_error() -> None:
    unavailable = AsyncMock(side_effect=RuntimeError("sensitive upstream detail"))
    with (
        patch("app.main.gitea.get_repo", new=unavailable),
        patch("app.main.gitea.list_commits", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_workflow_runs", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_issues", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_pulls", new=AsyncMock(return_value=[])),
    ):
        response = client.get("/repo/owner/missing")

    assert response.status_code == 404
    assert "Repository not found" in response.text
    assert "sensitive upstream detail" not in response.text
    assert 'aria-label="Primary navigation"' in response.text


@pytest.mark.asyncio
async def test_readme_falls_back_to_common_file_when_endpoint_is_missing() -> None:
    missing = Mock(status_code=404)
    with (
        patch("app.gitea.httpx.AsyncClient") as client_class,
        patch("app.gitea.get_file_content", new=AsyncMock(return_value="# Project\n")) as content,
    ):
        client_class.return_value.__aenter__.return_value.get = AsyncMock(return_value=missing)
        readme = await gitea.get_readme("owner", "repo")

    assert readme == "# Project\n"
    content.assert_awaited_once_with("owner", "repo", "README.md")


@pytest.mark.asyncio
async def test_markdown_rendering_uses_gitea_sanitizer_and_repairs_proxy_links() -> None:
    rendered = Mock(text='<h1>Project</h1><a href="http://localhost:3001/owner/repo/src/docs">Docs</a>')
    rendered.raise_for_status = Mock()
    with patch("app.gitea.httpx.AsyncClient") as client_class:
        post = AsyncMock(return_value=rendered)
        client_class.return_value.__aenter__.return_value.post = post
        result = await gitea.render_markdown("# Project", "owner/repo")

    assert (
        '<a href="/gitea-login?next=%2Fgitea%2Fowner%2Frepo%2Fsrc%2Fdocs">Docs</a>'
        in result
    )
    post.assert_awaited_once_with(
        f"{gitea.GITEA_URL}/api/v1/markdown",
        headers=gitea._headers,
        json={"Text": "# Project", "Mode": "gfm", "Context": "owner/repo"},
    )


@pytest.mark.asyncio
async def test_remove_issue_label_uses_the_specific_label_endpoint() -> None:
    with patch("app.gitea._request", new=AsyncMock(return_value=None)) as request:
        await gitea.remove_issue_label("owner", "repo", 7, 13)

    request.assert_awaited_once_with(
        "DELETE",
        "/repos/owner/repo/issues/7/labels/13",
    )


def test_repository_renders_sanitized_markdown() -> None:
    repo = {"full_name": "owner/repo", "name": "repo", "owner": {"login": "owner"},
            "default_branch": "main", "description": "", "stars_count": 0, "forks_count": 0,
            "open_issues_count": 0, "size": 12, "language": "Python",
            "updated_at": "2026-07-16T00:00:00Z"}
    with (
        patch("app.main.gitea.get_repo", new=AsyncMock(return_value=repo)),
        patch("app.main.gitea.list_commits", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_workflow_runs", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_issues", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_pulls", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.list_contents", new=AsyncMock(return_value=[])),
        patch("app.main.gitea.get_readme", new=AsyncMock(return_value="# Project")),
        patch("app.main.gitea.render_markdown", new=AsyncMock(return_value="<h1>Project</h1>")),
    ):
        response = client.get("/repo/owner/repo")

    assert response.status_code == 200
    assert "<h1>Project</h1>" in response.text
    assert "&lt;h1&gt;Project&lt;/h1&gt;" not in response.text


def test_stuck_detector_catches_repeated_action() -> None:
    detector = StuckDetector(max_same_tool=10)
    action = Action(tool="read", input={"path": "README.md"})

    assert detector.record(action) is False
    assert detector.record(action) is False
    assert detector.record(action) is True
    assert detector.suggest_action().startswith("REPEAT")


def test_cost_tracker_reports_budget() -> None:
    tracker = CostTracker(budget=2.0)
    tracker.add("research", "worker", 0.75)

    assert tracker.remaining() == 1.25
    assert tracker.get_report()["by_agent"] == {"research": 0.75}


@pytest.mark.asyncio
async def test_coordinator_keeps_a_stable_task_id() -> None:
    coordinator = AgentCoordinator("owner", "repo")

    with patch.object(coordinator, "_create_issue", new=AsyncMock(return_value=42)):
        task = await coordinator.create_task("Implement", "Build the feature")

    assert task.id == "task-1"
    assert task.issue_number == 42

    with patch.object(coordinator, "_update_issue_status", new=AsyncMock()) as update:
        await coordinator.assign_task(task.id, AgentRole.CODER)

    assert task.status == TaskStatus.IN_PROGRESS
    update.assert_awaited_once_with(task)


@pytest.mark.asyncio
async def test_agent_lock_expires_across_day_boundaries() -> None:
    lock = AgentLock("owner", "repo")
    lock.locks["file.py"] = {
        "agent": "first",
        "acquired_at": datetime.now(UTC) - timedelta(days=2),
        "timeout": 3600,
    }

    assert await lock.acquire("file.py", "second") is True


@pytest.mark.asyncio
async def test_rollback_restores_preexisting_dirty_state(tmp_path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("committed\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)

    tracked.write_text("user change\n")
    manager = RollbackManager(str(tmp_path))
    checkpoint = await manager.create_checkpoint("before agent")
    assert checkpoint is not None
    assert tracked.read_text() == "user change\n"

    tracked.write_text("agent change\n")
    assert await manager.rollback(checkpoint) is True
    assert tracked.read_text() == "user change\n"


def test_safe_code_changer_rejects_path_traversal(tmp_path) -> None:
    changer = SafeCodeChanger(str(tmp_path))

    with pytest.raises(ValueError, match="outside repository"):
        changer._resolve_path("../outside.txt")
