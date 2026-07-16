"""Durable, bounded queue for static experiment harnesses."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ExperimentBudget(BaseModel):
    """Hard caps; clients may only request less than these server limits."""

    trials: int = Field(default=8, ge=1, le=32)
    wall_seconds: int = Field(default=120, ge=10, le=1800)
    repetitions: int = Field(default=2, ge=1, le=5)
    max_output_bytes: int = Field(default=262_144, ge=4096, le=1_048_576)
    max_changed_lines: int = Field(default=60, ge=1, le=200)
    llm_tokens: int = Field(default=12_000, ge=1000, le=50_000)


class ExperimentSubmission(BaseModel):
    """A declarative request; no command, image, or host path is accepted."""

    method: Literal["optuna", "openevolve", "sage"]
    harness: Literal["rrc-swiglu-launch", "rrc-swiglu-evolve", "sage-expression"]
    budget: ExperimentBudget = Field(default_factory=ExperimentBudget)
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    project: str = Field(default="agent/forge0", pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

    @model_validator(mode="after")
    def harness_matches_method(self) -> ExperimentSubmission:
        allowed = {
            "optuna": "rrc-swiglu-launch",
            "openevolve": "rrc-swiglu-evolve",
            "sage": "sage-expression",
        }
        if self.harness != allowed[self.method]:
            raise ValueError(f"{self.method} jobs must use {allowed[self.method]}")
        allowed_parameters = {
            "optuna": {"block_sizes", "num_rows", "max_row_len", "iterations"},
            "openevolve": {"target", "iterations"},
            "sage": {"expression", "expected"},
        }[self.method]
        unknown = set(self.parameters) - allowed_parameters
        if unknown:
            raise ValueError(f"unsupported parameters: {', '.join(sorted(unknown))}")
        if self.method == "sage":
            expression = self.parameters.get("expression", "")
            if not isinstance(expression, str) or not expression.strip() or len(expression) > 4000:
                raise ValueError("sage expression must contain 1..4000 characters")
            if self.budget.wall_seconds > 120:
                raise ValueError("sage jobs are capped at 120 wall seconds")
        if self.method == "openevolve":
            if self.budget.wall_seconds < 120:
                raise ValueError("openevolve jobs require at least 120 wall seconds")
            if self.parameters.get("target", "cross_warp_reduction") != "cross_warp_reduction":
                raise ValueError("unsupported evolution target")
            iterations = self.parameters.get("iterations", 2)
            if not isinstance(iterations, int) or not 1 <= iterations <= 4:
                raise ValueError("openevolve iterations must be between 1 and 4")
        return self

    @property
    def resource(self) -> Literal["v100", "sage"]:
        return "sage" if self.method == "sage" else "v100"


@dataclass
class ExperimentRecord:
    id: str
    status: str
    resource: str
    manifest: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    created_at: str
    updated_at: str
    lease_owner: str | None = None
    lease_expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentQueue:
    """SQLite queue with single-statement claims and expired-lease recovery."""

    def __init__(self, path: str | Path | None = None):
        data_dir = Path(os.getenv("FORGE0_DATA_DIR", "/var/lib/forge0"))
        self.path = Path(path or data_dir / "experiments.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS experiments_status_resource "
                "ON experiments(status, resource, created_at)"
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> ExperimentRecord:
        return ExperimentRecord(
            id=row["id"],
            status=row["status"],
            resource=row["resource"],
            manifest=json.loads(row["manifest_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
        )

    def enqueue(self, submission: ExperimentSubmission) -> ExperimentRecord:
        job_id = f"exp-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
        timestamp = _now()
        manifest = submission.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO experiments VALUES (?, 'queued', ?, ?, NULL, NULL, ?, ?, NULL, NULL)",
                (job_id, submission.resource, json.dumps(manifest, sort_keys=True), timestamp, timestamp),
            )
        record = self.get(job_id)
        assert record is not None
        return record

    def get(self, job_id: str) -> ExperimentRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM experiments WHERE id = ?", (job_id,)).fetchone()
        return self._record(row) if row else None

    def list(self, limit: int = 50) -> list[ExperimentRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (min(limit, 100),)
            ).fetchall()
        return [self._record(row) for row in rows]

    def claim(self, resource: str, owner: str, lease_seconds: int = 60) -> ExperimentRecord | None:
        now = _now()
        expires = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE experiments SET status='queued', lease_owner=NULL, lease_expires_at=NULL "
                "WHERE status='running' AND resource=? AND lease_expires_at < ?",
                (resource, now),
            )
            row = connection.execute(
                "SELECT id FROM experiments WHERE status='queued' AND resource=? "
                "ORDER BY created_at LIMIT 1",
                (resource,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE experiments SET status='running', lease_owner=?, lease_expires_at=?, updated_at=? "
                "WHERE id=? AND status='queued'",
                (owner, expires, now, row["id"]),
            )
        return self.get(row["id"])

    def heartbeat(self, job_id: str, owner: str, lease_seconds: int = 60) -> None:
        expires = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE experiments SET lease_expires_at=?, updated_at=? "
                "WHERE id=? AND status='running' AND lease_owner=?",
                (expires, _now(), job_id, owner),
            )

    def finish(
        self,
        job_id: str,
        owner: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        status = "failed" if error else "succeeded"
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE experiments SET status=?, result_json=?, error=?, updated_at=?, "
                "lease_owner=NULL, lease_expires_at=NULL WHERE id=? AND lease_owner=?",
                (
                    status,
                    json.dumps(result, sort_keys=True) if result is not None else None,
                    (error or "")[:4000] or None,
                    _now(),
                    job_id,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("experiment lease was lost")
