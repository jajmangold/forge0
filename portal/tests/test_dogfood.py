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
    GitWorkspace,
    RunRecord,
    RunStatus,
    RunStore,
)
from app.llm_client import ChatResult
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


def test_change_applier_rewrites_one_planned_existing_file(tmp_path) -> None:
    target = tmp_path / "README.md"
    target.write_text("before\n")

    changed = ChangeApplier(tmp_path, config(tmp_path), {"README.md"}).apply(
        [{"path": "README.md", "operation": "rewrite", "content": "complete replacement\n"}]
    )

    assert changed == ["README.md"]
    assert target.read_text() == "complete replacement\n"


def test_rewrite_can_preserve_but_not_introduce_secret_markers(tmp_path) -> None:
    marker = "-----BEGIN PRIVATE KEY-----"
    target = tmp_path / "README.md"
    target.write_text(f"detector = {marker!r}\n")
    applier = ChangeApplier(tmp_path, config(tmp_path), {"README.md", "docs/new.md"})

    applier.apply([{"path": "README.md", "operation": "rewrite", "content": f"kept = {marker!r}\n"}])
    with pytest.raises(DogfoodError, match="resembles a secret"):
        applier.apply([{"path": "docs/new.md", "operation": "create", "content": marker}])


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


def test_issue_file_scope_parses_bullets_and_stops_at_next_heading(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    issue = {
        "labels": [{"name": "agent:ready"}],
        "body": (
            "## File Scope\n\n- `portal/app/dogfood.py`\n- `README.md`\n\n"
            "## Acceptance Criteria\n\n- ordinary prose is not part of the scope\n"
        ),
    }

    service._validate_issue(issue)

    assert service._issue_file_scope(issue) == {"portal/app/dogfood.py", "README.md"}


@pytest.mark.parametrize(
    ("scope", "error"),
    [
        ("", "at least one"),
        ("- README.md", "backtick-wrapped"),
        ("- `README.md`\n- `README.md`", "duplicate"),
        ("- `.env`", "Protected path"),
        ("- `outside.txt`", "outside the allowlist"),
        ("- `../README.md`", "Unsafe path"),
        ("- `./README.md`", "canonical repository-relative"),
    ],
)
def test_issue_file_scope_rejects_malformed_or_unsafe_entries(tmp_path, scope: str, error: str) -> None:
    service = DogfoodService(config(tmp_path))
    issue = {
        "labels": [{"name": "agent:ready"}],
        "body": f"## File Scope\n{scope}\n\n## Acceptance Criteria\n- safe\n",
    }

    with pytest.raises(DogfoodError, match=error):
        service._validate_issue(issue)


def test_issue_file_scope_cannot_exceed_global_file_limit(tmp_path) -> None:
    service = DogfoodService(config(tmp_path, max_changed_files=1))
    issue = {
        "labels": [{"name": "agent:ready"}],
        "body": "## File Scope\n- `README.md`\n- `portal/app/dogfood.py`\n\n## Acceptance Criteria\n- safe",
    }

    with pytest.raises(DogfoodError, match="changed-file limit"):
        service._validate_issue(issue)


def test_plan_cannot_escape_issue_file_scope_and_legacy_plan_is_unchanged(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))

    assert service._validate_plan({"files": ["README.md"]}, {"README.md"}) == {"README.md"}
    assert service._validate_plan({"files": ["README.md"]}) == {"README.md"}
    with pytest.raises(DogfoodError, match="outside the issue File Scope"):
        service._validate_plan({"files": ["README.md", "portal/app/main.py"]}, {"README.md"})


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
    assert "keys named exactly old and new" in correction
    assert "that change was not applied" in correction

    targeted = service._implementation_prompt({}, {}, "<new file>", target_file="kernels/new.cu")
    assert "exactly one change" in targeted
    assert "kernels/new.cu" in targeted


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
    assert "kernels/" in loaded.allowed_paths
    assert loaded.coder_model == "planner"
    assert loaded.max_diff_lines == 500
    assert loaded.max_kernel_diff_lines == 2000
    assert loaded.max_critic_diff_chars == 160000

    service = DogfoodService(loaded)
    assert service._diff_limit(["kernels/example/kernel.cu"]) == 2000
    assert service._diff_limit(["kernels/example/kernel.cu", "portal/app/main.py"]) == 500


@pytest.mark.asyncio
async def test_stage_and_measure_preserves_bounded_diff_for_critic(tmp_path) -> None:
    workspace = GitWorkspace(tmp_path / "workspace", config(tmp_path), "token")
    workspace._git = AsyncMock(
        side_effect=["", "kernels/example/kernel.cu\n", "2\t0\tkernels/example/kernel.cu\n", "full diff"]
    )

    names, lines, diff = await workspace.stage_and_measure()

    assert names == ["kernels/example/kernel.cu"]
    assert lines == 2
    assert diff == "full diff"
    assert workspace._git.await_args_list[-1].kwargs["max_output_chars"] == 160001


@pytest.mark.asyncio
async def test_structured_completion_retries_invalid_json(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    record = RunRecord(id="json-run", owner="agent", repo="forge0", issue_number=10, issue_title="JSON")
    client = AsyncMock()
    client.chat_with_usage.side_effect = [
        ChatResult(content="not json", usage={"total_tokens": 4}),
        ChatResult(content='{"files": ["README.md"]}', usage={"total_tokens": 5}),
    ]

    result = await service._json_completion(
        client,
        record,
        messages=[{"role": "user", "content": "plan"}],
        model="planner",
        temperature=0.1,
        max_tokens=100,
        validate=service._validate_plan,
    )

    assert result == {"files": ["README.md"]}
    assert client.chat_with_usage.await_count == 2
    assert record.usage["total_tokens"] == 9
    assert record.correction_errors == ["planner: LLM response did not contain a JSON object"]
    correction = client.chat_with_usage.await_args_list[1].kwargs["messages"][-1]["content"]
    assert "valid JSON object only" in correction
    assert client.chat_with_usage.await_args_list[0].kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_structured_completion_retries_truncated_response(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    record = RunRecord(id="trunc-run", owner="agent", repo="forge0", issue_number=11, issue_title="Truncated")
    client = AsyncMock()
    client.chat_with_usage.side_effect = [
        ChatResult(content='{"files": ["README.md', usage={"total_tokens": 100}, finish_reason="length"),
        ChatResult(content='{"files": ["README.md"]}', usage={"total_tokens": 50}, finish_reason="stop"),
    ]

    result = await service._json_completion(
        client,
        record,
        messages=[{"role": "user", "content": "plan"}],
        model="planner",
        temperature=0.1,
        max_tokens=100,
        validate=service._validate_plan,
    )

    assert result == {"files": ["README.md"]}
    assert client.chat_with_usage.await_count == 2
    assert record.usage["total_tokens"] == 150
    assert len(record.correction_errors) == 1
    assert "truncated by the token limit" in record.correction_errors[0]
    correction = client.chat_with_usage.await_args_list[1].kwargs["messages"][-1]["content"]
    assert "concise" in correction.lower()
    assert "truncated" in correction.lower()


@pytest.mark.asyncio
async def test_structured_completion_exhausts_truncation_retries(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    record = RunRecord(id="exhaust-run", owner="agent", repo="forge0", issue_number=12, issue_title="Exhausted")
    client = AsyncMock()
    client.chat_with_usage.side_effect = [
        ChatResult(content='{"files": ["README.md', usage={"total_tokens": 100}, finish_reason="length"),
        ChatResult(content='{"files": ["README.md', usage={"total_tokens": 90}, finish_reason="length"),
        ChatResult(content='{"files": ["README.md', usage={"total_tokens": 80}, finish_reason="length"),
    ]

    with pytest.raises(DogfoodError, match="token limit"):
        await service._json_completion(
            client,
            record,
            messages=[{"role": "user", "content": "plan"}],
            model="planner",
            temperature=0.1,
            max_tokens=100,
            validate=service._validate_plan,
        )

    assert client.chat_with_usage.await_count == 3
    assert record.usage["total_tokens"] == 270
    assert len(record.correction_errors) == 3
    assert all("truncated by the token limit" in err for err in record.correction_errors)


@pytest.mark.asyncio
async def test_structured_completion_recovers_after_truncation(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))
    record = RunRecord(id="recover-run", owner="agent", repo="forge0", issue_number=13, issue_title="Recover")
    client = AsyncMock()
    client.chat_with_usage.side_effect = [
        ChatResult(content='{"files": ["README.md', usage={"total_tokens": 100}, finish_reason="length"),
        ChatResult(content='{"files": ["README.md"]}', usage={"total_tokens": 40}, finish_reason="stop"),
    ]

    result = await service._json_completion(
        client,
        record,
        messages=[{"role": "user", "content": "plan"}],
        model="planner",
        temperature=0.1,
        max_tokens=100,
        validate=service._validate_plan,
    )

    assert result == {"files": ["README.md"]}
    assert client.chat_with_usage.await_count == 2
    assert record.usage["total_tokens"] == 140
    assert len(record.correction_errors) == 1
    assert "truncated by the token limit" in record.correction_errors[0]


def test_complete_response_guard_rejects_implementation_truncation(tmp_path) -> None:
    service = DogfoodService(config(tmp_path))

    with pytest.raises(DogfoodError, match="significantly more concise JSON"):
        service._ensure_complete(ChatResult(content="partial", finish_reason="length"))


@pytest.mark.asyncio
async def test_verification_returns_failure_output_for_persistence(tmp_path) -> None:
    workspace = GitWorkspace(tmp_path / "workspace", config(tmp_path), "token")
    workspace.repo_path.mkdir(parents=True)

    with patch.object(workspace, "_run", new=AsyncMock(side_effect=DogfoodError("test output"))):
        results = await workspace.verify()

    assert results == [
        {
            "command": "pytest -q",
            "success": False,
            "output": "test output",
        }
    ]


def repair_workspace(tmp_path, cfg: DogfoodConfig, *, verification_success: bool = True) -> GitWorkspace:
    workspace = GitWorkspace(tmp_path / "workspace", cfg, "token")
    workspace.repo_path.mkdir(parents=True)
    (workspace.repo_path / "README.md").write_text("before\n")
    workspace.stage_and_measure = AsyncMock(return_value=(["README.md"], 2, "complete diff"))
    workspace.verify = AsyncMock(
        return_value=[
            {
                "command": "pytest -q",
                "success": verification_success,
                "output": "" if verification_success else "failure details",
            }
        ]
    )
    return workspace


def repair_client() -> AsyncMock:
    client = AsyncMock()
    client.chat_with_usage.return_value = ChatResult(
        content=json.dumps(
            {
                "commit_message": "fix(dogfood): repair candidate",
                "pr_title": "Repair candidate",
                "pr_body": "Applies critic feedback.",
                "changes": [
                    {
                        "path": "README.md",
                        "operation": "rewrite",
                        "content": "after\n",
                    }
                ],
            }
        ),
        usage={"total_tokens": 10},
    )
    return client


def repair_record(run_id: str) -> RunRecord:
    return RunRecord(
        id=run_id,
        owner="agent",
        repo="forge0",
        issue_number=42,
        issue_title="Repair",
        critic_feedback="Address the defect",
    )


@pytest.mark.asyncio
async def test_critic_repair_regenerates_verifies_and_passes(tmp_path) -> None:
    cfg = config(tmp_path, max_critic_repairs=1)
    service = DogfoodService(cfg)
    workspace = repair_workspace(tmp_path, cfg)
    record = repair_record("repair-pass")

    with (
        patch.object(service, "_comment", new=AsyncMock()),
        patch.object(service, "_json_completion", new=AsyncMock(return_value={"pass": True, "feedback": "ok"})),
    ):
        await service._repair_pass(
            record,
            workspace,
            repair_client(),
            {"title": "Repair", "body": "## Acceptance Criteria\n- fixed"},
            {"files": ["README.md"]},
            {"README.md"},
            {},
        )

    assert record.critic_repair_count == 1
    assert record.status is RunStatus.REVIEWING
    assert record.changed_files == ["README.md"]
    assert record.verification[0]["success"] is True
    assert (workspace.repo_path / "README.md").read_text() == "after\n"


@pytest.mark.asyncio
async def test_critic_repair_stops_when_verification_fails(tmp_path) -> None:
    cfg = config(tmp_path, max_critic_repairs=1)
    service = DogfoodService(cfg)
    workspace = repair_workspace(tmp_path, cfg, verification_success=False)
    record = repair_record("repair-verification-fails")

    with patch.object(service, "_comment", new=AsyncMock()):
        with pytest.raises(DogfoodError, match="Verification failed after repair"):
            await service._repair_pass(
                record, workspace, repair_client(), {}, {"files": ["README.md"]}, {"README.md"}, {}
            )

    assert record.verification[0]["output"] == "failure details"


@pytest.mark.asyncio
async def test_critic_repair_exhaustion_is_durable(tmp_path) -> None:
    cfg = config(tmp_path, max_critic_repairs=1)
    service = DogfoodService(cfg)
    workspace = repair_workspace(tmp_path, cfg)
    record = repair_record("repair-exhausted")

    with (
        patch.object(service, "_comment", new=AsyncMock()),
        patch.object(
            service,
            "_json_completion",
            new=AsyncMock(return_value={"pass": False, "feedback": "still defective"}),
        ),
    ):
        with pytest.raises(DogfoodError, match="repair exhausted"):
            await service._repair_pass(
                record, workspace, repair_client(), {}, {"files": ["README.md"]}, {"README.md"}, {}
            )

    assert record.correction_errors == ["Critic repair exhausted after 1 repair(s)"]
    assert service.store.load(record.id).correction_errors == record.correction_errors


def test_critic_repair_configuration_enforces_hard_cap(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FORGE0_DATA_DIR", os.fspath(tmp_path))
    monkeypatch.setenv("FORGE0_SELF_REPO", "agent/forge0")
    monkeypatch.setenv("FORGE0_MAX_CRITIC_REPAIRS", "3")
    with pytest.raises(ValueError, match="between 0 and 2"):
        DogfoodConfig.from_env()

    monkeypatch.setenv("FORGE0_MAX_CRITIC_REPAIRS", "2")
    assert DogfoodConfig.from_env().max_critic_repairs == 2
