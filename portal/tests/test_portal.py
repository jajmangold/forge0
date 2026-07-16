"""Portal route and safety regression tests."""

import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.coordination import AgentCoordinator, AgentLock, AgentRole, TaskStatus
from app.main import app
from app.rollback import RollbackManager, SafeCodeChanger
from app.stuck_detection import Action, CostTracker, StuckDetector
from fastapi.testclient import TestClient

client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auto_login_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GITEA_AUTO_LOGIN", raising=False)

    response = client.get("/gitea-login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/gitea/user/login"


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
