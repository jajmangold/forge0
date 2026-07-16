from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from app import main
from app.experiment_queue import ExperimentQueue, ExperimentSubmission
from app.frontier import dominates, pareto_front
from app.research import ResearchRequest, ResearchService, _plain_text, _public_host
from fastapi.testclient import TestClient
from pydantic import ValidationError

OBJECTIVES = [
    {"name": "latency", "direction": "minimize"},
    {"name": "quality", "direction": "maximize"},
]


def test_pareto_front_preserves_tradeoffs_and_excludes_failures():
    candidates = [
        {"id": "fast", "metrics": {"latency": 1, "quality": 7}},
        {"id": "quality", "metrics": {"latency": 2, "quality": 9}},
        {"id": "dominated", "metrics": {"latency": 3, "quality": 7}},
        {"id": "broken", "feasible": False, "metrics": {"latency": 0, "quality": 100}},
    ]
    assert dominates(candidates[0]["metrics"], candidates[2]["metrics"], OBJECTIVES)
    assert [item["id"] for item in pareto_front(candidates, OBJECTIVES)] == ["fast", "quality"]


def test_manifest_only_allows_static_method_harness_pairs():
    valid = ExperimentSubmission(method="optuna", harness="rrc-swiglu-launch")
    assert valid.resource == "v100"
    with pytest.raises(ValidationError, match="must use"):
        ExperimentSubmission(method="optuna", harness="sage-expression")
    with pytest.raises(ValidationError, match="unsupported parameters"):
        ExperimentSubmission(
            method="optuna",
            harness="rrc-swiglu-launch",
            parameters={"command": "rm -rf /"},
        )
    with pytest.raises(ValidationError, match="between 1 and 4"):
        ExperimentSubmission(
            method="openevolve",
            harness="rrc-swiglu-evolve",
            parameters={"iterations": 10},
        )
    with pytest.raises(ValidationError, match="120 wall seconds"):
        ExperimentSubmission(
            method="sage",
            harness="sage-expression",
            budget={"wall_seconds": 300},
            parameters={"expression": "factor(x^2 - 1)"},
        )


def test_queue_claims_one_resource_and_recovers_expired_lease(tmp_path):
    queue = ExperimentQueue(tmp_path / "queue.sqlite3")
    first = queue.enqueue(ExperimentSubmission(method="optuna", harness="rrc-swiglu-launch"))
    second = queue.enqueue(
        ExperimentSubmission(
            method="sage",
            harness="sage-expression",
            parameters={"expression": "factor(x^2 - 1)"},
        )
    )
    claimed = queue.claim("v100", "worker-a", lease_seconds=60)
    assert claimed and claimed.id == first.id
    assert queue.claim("v100", "worker-b") is None
    sage = queue.claim("sage", "sage-a")
    assert sage and sage.id == second.id
    queue.finish(sage.id, "sage-a", result={"value": "(x - 1)*(x + 1)"})
    assert queue.get(sage.id).status == "succeeded"  # type: ignore[union-attr]

    expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    with queue._connect() as connection:
        connection.execute(
            "UPDATE experiments SET lease_expires_at=? WHERE id=?", (expired, first.id)
        )
    recovered = queue.claim("v100", "worker-b")
    assert recovered and recovered.id == first.id


def test_research_source_helpers_strip_markup_and_reject_localhost():
    assert _plain_text("<style>x</style><p>A &amp; B</p>") == "A & B"
    assert not _public_host("localhost")


@pytest.mark.asyncio
async def test_research_runs_once_then_reuses_durable_cache(tmp_path, monkeypatch):
    calls = {"search": 0, "llm": 0, "wiki": 0}
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")

    async def fake_search(query: str, num_results: int):
        calls["search"] += 1
        return [
            {
                "title": f"Official {query}",
                "url": f"https://docs.example.com/{calls['search']}",
                "content": "Documented evidence",
                "score": 1.0,
                "engine": "example",
            }
        ]

    async def fake_fetch(url: str, max_bytes: int = 262_144):
        return f"Fetched evidence from {url}"

    async def fake_chat(self, *, messages, model, temperature, max_tokens):
        calls["llm"] += 1
        return "Finding with [source](https://docs.example.com/1)."

    async def fake_wiki(owner: str, repo: str, title: str, content: str):
        calls["wiki"] += 1
        assert "researched:" in content
        return {"html_url": f"https://gitea.example/{title}"}

    monkeypatch.setattr("app.research.search_web", fake_search)
    monkeypatch.setattr("app.research._fetch_excerpt", fake_fetch)
    monkeypatch.setattr("app.research.LLMClient.chat", fake_chat)
    monkeypatch.setattr("app.research.gitea.upsert_wiki_page", fake_wiki)

    service = ResearchService(tmp_path / "research.sqlite3")
    request = ResearchRequest(topic="bounded agent research", max_queries=3)
    first = await service.run(request)
    second = await service.run(request)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert first["metrics"]["unique_domains"] == 1
    assert len(first["source_frontier"]) == 1
    assert calls == {"search": 3, "llm": 1, "wiki": 1}
    with service._connect() as connection:
        payload = json.loads(connection.execute("SELECT result_json FROM research_cache").fetchone()[0])
    assert payload["wiki"]["title"].startswith("Research-")


def test_lab_page_and_api_use_the_durable_queue(tmp_path, monkeypatch):
    monkeypatch.delenv("GITEA_OAUTH_CLIENT_ID", raising=False)
    queue = ExperimentQueue(tmp_path / "experiments.sqlite3")
    monkeypatch.setattr(main, "_experiment_queue", queue)
    client = TestClient(main.app)

    page = client.get("/lab")
    queued = client.post(
        "/api/experiments",
        json={
            "method": "sage",
            "harness": "sage-expression",
            "parameters": {"expression": "factor(x^2 - 1)"},
        },
    )

    assert page.status_code == 200
    assert "Research lab" in page.text
    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    assert client.get(f"/api/experiments/{queued.json()['id']}").status_code == 200


def test_experiment_detail_shows_candidates_frontier_budgets_and_wandb(tmp_path, monkeypatch):
    monkeypatch.delenv("GITEA_OAUTH_CLIENT_ID", raising=False)
    queue = ExperimentQueue(tmp_path / "experiments.sqlite3")
    monkeypatch.setattr(main, "_experiment_queue", queue)
    record = queue.enqueue(ExperimentSubmission(method="optuna", harness="rrc-swiglu-launch"))
    assert queue.claim("v100", "worker-1") is not None
    queue.finish(
        record.id,
        "worker-1",
        result={
            "elapsed_seconds": 4.25,
            "objectives": OBJECTIVES,
            "candidates": [
                {"id": "fast", "feasible": True, "metrics": {"latency": 1, "quality": 7}},
                {"id": "quality", "feasible": True, "metrics": {"latency": 2, "quality": 9}},
                {"id": "dominated", "feasible": True, "metrics": {"latency": 3, "quality": 7}},
            ],
            "frontier": [{"id": "fast"}, {"id": "quality"}],
            "wandb": {"mode": "offline", "run_id": record.id},
        },
    )

    response = TestClient(main.app).get(f"/experiments/{record.id}")

    assert response.status_code == 200
    for expected in (
        "4.25s",
        "v100",
        "fast",
        "quality",
        "dominated",
        "Frontier",
        "minimize",
        "maximize",
        "wall seconds",
        "offline",
        record.id,
    ):
        assert expected in response.text


def test_experiment_detail_bounds_failure_output(tmp_path, monkeypatch):
    monkeypatch.delenv("GITEA_OAUTH_CLIENT_ID", raising=False)
    queue = ExperimentQueue(tmp_path / "experiments.sqlite3")
    monkeypatch.setattr(main, "_experiment_queue", queue)
    record = queue.enqueue(
        ExperimentSubmission(
            method="sage",
            harness="sage-expression",
            parameters={"expression": "factor(x^2 - 1)"},
        )
    )
    assert queue.claim("sage", "sage-1") is not None
    queue.finish(record.id, "sage-1", error="bounded failure " + "x" * 2000)

    response = TestClient(main.app).get(f"/experiments/{record.id}")

    assert response.status_code == 200
    assert "failed" in response.text
    assert "bounded failure" in response.text
    assert "x" * 1001 not in response.text
    assert "factor(x^2 - 1)" not in response.text


def test_experiment_detail_unknown_id_is_useful_404(tmp_path, monkeypatch):
    monkeypatch.delenv("GITEA_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.setattr(main, "_experiment_queue", ExperimentQueue(tmp_path / "experiments.sqlite3"))

    response = TestClient(main.app).get("/experiments/exp-missing")

    assert response.status_code == 404
    assert "Experiment not found" in response.text
    assert "Research lab" in response.text
