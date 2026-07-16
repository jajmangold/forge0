"""Safety and API tests for Forge0's issue-to-draft-PR workflow."""

import hashlib
import hmac
import json
import os
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from app import main
from app.dogfood import (
    ChangeApplier,
    DogfoodConfig,
    DogfoodError,
    DogfoodService,
    RunRecord,
    RunStatus,
    RunStore,
)
from fastapi.testclient import TestClient


def config(tmp_path, **changes) -> DogfoodConfig:
    base = DogfoodConfig(
        data_dir=tmp_path,
        operator_token="operator-secret",
        webhook_secret="webhook-secret",
    )
    return replace(base, **changes)


def test_run_store_persists_records_and_deduplicates_active_issue(tmp_path) -> None:
    store = RunStore(tmp_path / "runs")
    record = RunRecord(id="run-1", owner="agent", repo="forge0", issue_number=7, issue_title="Improve")
    store.save(record)

    loaded = store.load("run-1")
    assert loaded is not None
    assert loaded.status is RunStatus.QUEUED
    assert store.active_for_issue("agent", "forge0", 7) is not None

    loaded.status = RunStatus.FAILED
    store.save(loaded)
    assert store.active_for_issue("agent", "forge0", 7) is None


def test_run_store_releases_interrupted_runs_after_restart(tmp_path) -> None:
    store = RunStore(tmp_path / "runs")
    interrupted = RunRecord(
        id="run-active",
        owner="agent",
        repo="forge0",
        issue_number=8,
        issue_title="Improve",
        status=RunStatus.VERIFYING,
    )
    completed = RunRecord(
        id="run-draft",
        owner="agent",
        repo="forge0",
        issue_number=9,
        issue_title="Done",
        status=RunStatus.DRAFT_OPENED,
    )
    store.save(interrupted)
    store.save(completed)

    assert store.recover_interrupted() == 1
    assert store.load("run-active").status is RunStatus.FAILED
    assert "restart" in store.load("run-active").error
    assert store.load("run-draft").status is RunStatus.DRAFT_OPENED


def test_change_applier_only_changes_planned_allowlisted_files(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("before\n")
    applier = ChangeApplier(tmp_path, config(tmp_path), {"README.md", "docs/new.md"})

    changed = applier.apply(
        [
            {"path": "README.md", "operation": "replace", "old": "before", "new": "after"},
            {"path": "docs/new.md", "operation": "create", "content": "new\n"},
        ]
    )

    assert changed == ["README.md", "docs/new.md"]
    assert readme.read_text() == "after\n"
    assert (tmp_path / "docs/new.md").read_text() == "new\n"


@pytest.mark.parametrize("path", ["../secret", ".env", "outside.txt", "/tmp/file"])
def test_change_applier_rejects_unsafe_paths(tmp_path, path: str) -> None:
    applier = ChangeApplier(tmp_path, config(tmp_path), {path})

    with pytest.raises(DogfoodError):
        applier.apply([{"path": path, "operation": "create", "content": "x"}])


def test_change_applier_rejects_symlink_targets(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "real").mkdir()
    (tmp_path / "docs/link").symlink_to(tmp_path / "real", target_is_directory=True)
    applier = ChangeApplier(tmp_path, config(tmp_path), {"docs/link/new.md"})

    with pytest.raises(DogfoodError, match="Symlink"):
        applier.apply([{"path": "docs/link/new.md", "operation": "create", "content": "x"}])


def test_change_applier_is_transactional_when_a_later_change_is_invalid(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("before\n")
    (tmp_path / "docs").mkdir()
    secondary = tmp_path / "docs/new.md"
    secondary.write_text("missing\n")
    applier = ChangeApplier(tmp_path, config(tmp_path), {"README.md", "docs/new.md"})

    with pytest.raises(DogfoodError, match="non-empty"):
        applier.apply(
            [
                {"path": "README.md", "operation": "replace", "old": "before", "new": "after"},
                {"path": "docs/new.md", "operation": "replace", "old": "missing", "new": ""},
            ]
        )

    assert readme.read_text() == "before\n"
    assert secondary.read_text() == "missing\n"


def test_issue_validation_requires_label_and_acceptance_criteria(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))

    service._validate_issue({"labels": [{"name": "agent:ready"}], "body": "## Acceptance Criteria\n- works"})
    with pytest.raises(DogfoodError, match="label"):
        service._validate_issue({"labels": [], "body": "## Acceptance Criteria\n- works"})
    with pytest.raises(DogfoodError, match="Acceptance Criteria"):
        service._validate_issue({"labels": [{"name": "agent:ready"}], "body": "Please do it"})


def test_signed_webhook_selects_only_the_configured_ready_issue(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    body = b'{"action":"opened"}'
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    payload = {
        "action": "labeled",
        "repository": {"full_name": "agent/forge0"},
        "issue": {"number": 4, "body": "## Acceptance Criteria", "labels": [{"name": "agent:ready"}]},
    }

    assert service.verify_webhook_signature(body, signature)
    assert not service.verify_webhook_signature(body + b"x", signature)
    assert service.webhook_issue(payload) == ("agent", "forge0", 4)
    payload["repository"]["full_name"] = "someone/fork"
    assert service.webhook_issue(payload) is None


def test_llm_json_parsing_commit_and_error_sanitization(monkeypatch, tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    assert service._parse_json("```json\n{\"pass\": true}\n```") == {"pass": True}
    assert service._commit_message({"commit_message": "do anything"}, 9) == "feat(dogfood): address issue 9"
    assert service._draft_title({"pr_title": "Improve it"}, "fallback") == "WIP: Improve it"
    assert service._draft_title({"pr_title": "WIP: Existing"}, "fallback") == "WIP: Existing"

    monkeypatch.delenv("GITEA_TOKEN", raising=False)
    assert service._safe_error(RuntimeError("normal failure")) == "normal failure"
    assert service._safe_error(TimeoutError()) == "TimeoutError"
    monkeypatch.setenv("GITEA_TOKEN", "sensitive")
    assert service._safe_error(RuntimeError("failed sensitive value")) == "failed [redacted] value"

    correction = service._implementation_prompt({}, {}, "<new file>", "target does not exist")
    assert "operation=create" in correction
    assert "without applying any files" in correction


def test_dogfood_routes_enforce_operator_and_webhook_secrets(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    original = main._dogfood_service
    main._dogfood_service = service
    client = TestClient(main.app)
    try:
        assert client.get("/dogfood").status_code == 200
        assert client.post("/api/dogfood/run/agent/forge0/1").status_code == 401

        payload = json.dumps({"action": "ping"}).encode()
        signature = hmac.new(b"webhook-secret", payload, hashlib.sha256).hexdigest()
        response = client.post(
            "/api/webhooks/gitea",
            content=payload,
            headers={"X-Gitea-Signature": signature, "X-Gitea-Event": "ping"},
        )
        assert response.status_code == 202
        assert response.json() == {"status": "ignored"}
    finally:
        main._dogfood_service = original


@pytest.mark.asyncio
async def test_enqueue_deduplicates_runs(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    issue = {
        "number": 3,
        "title": "Improve docs",
        "body": "## Acceptance Criteria\n- documented",
        "labels": [{"name": "agent:ready"}],
    }

    async def wait_forever(*_args) -> None:
        await __import__("asyncio").Event().wait()

    with (
        patch("app.dogfood.gitea.get_issue", new=AsyncMock(return_value=issue)),
        patch.object(service, "_execute", side_effect=wait_forever),
    ):
        first = await service.enqueue("agent", "forge0", 3)
        second = await service.enqueue("agent", "forge0", 3)
        assert first.id == second.id
        service._tasks[first.id].cancel()

    await __import__("asyncio").gather(*service._tasks.values(), return_exceptions=True)


def test_config_from_environment_uses_safe_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FORGE0_DATA_DIR", os.fspath(tmp_path))
    monkeypatch.setenv("FORGE0_SELF_REPO", "agent/forge0")
    monkeypatch.delenv("FORGE0_DOGFOOD_ALLOWED_PATHS", raising=False)

    loaded = DogfoodConfig.from_env()

    assert loaded.full_name == "agent/forge0"
    assert "portal/" in loaded.allowed_paths
