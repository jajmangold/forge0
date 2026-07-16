"""Dependency-free queue client for pinned sandbox images."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RuntimeRecord:
    id: str
    manifest: dict[str, Any]


class RuntimeQueue:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def claim(self, resource: str, owner: str, lease_seconds: int = 180) -> RuntimeRecord | None:
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
                "SELECT id, manifest_json FROM experiments WHERE status='queued' AND resource=? "
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
        return RuntimeRecord(id=row["id"], manifest=json.loads(row["manifest_json"]))

    def finish(
        self,
        job_id: str,
        owner: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE experiments SET status=?, result_json=?, error=?, updated_at=?, "
                "lease_owner=NULL, lease_expires_at=NULL WHERE id=? AND lease_owner=?",
                (
                    "failed" if error else "succeeded",
                    json.dumps(result, sort_keys=True) if result is not None else None,
                    (error or "")[:4000] or None,
                    _now(),
                    job_id,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("sandbox lease was lost")
