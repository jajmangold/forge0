"""Deterministic discovery of recurring self-extension engine failures."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FailureCandidate:
    fingerprint: str
    signature: str
    run_ids: tuple[str, ...]

    @property
    def occurrences(self) -> int:
        return len(self.run_ids)


def normalize_failure(error: str) -> str:
    """Remove per-run identifiers while retaining the actionable failure shape."""
    normalized = error.lower()
    normalized = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", normalized)
    normalized = re.sub(r"\b\d{4}-\d{2}-\d{2}t\S+", "<time>", normalized)
    normalized = re.sub(r"\b\d+\b", "<n>", normalized)
    normalized = " ".join(normalized.split())
    return normalized[:300]


def discover_failure_candidates(
    records: Iterable[Any], *, minimum_occurrences: int = 2, limit: int = 3
) -> list[FailureCandidate]:
    groups: dict[str, list[str]] = {}
    for record in records:
        status = getattr(record, "status", "")
        status_value = getattr(status, "value", status)
        error = str(getattr(record, "error", ""))
        if status_value != "failed" or not error or "operator review" in error.lower():
            continue
        signature = normalize_failure(error)
        if signature:
            groups.setdefault(signature, []).append(str(getattr(record, "id", "unknown")))
    candidates = [
        FailureCandidate(
            fingerprint=hashlib.sha256(signature.encode()).hexdigest()[:16],
            signature=signature,
            run_ids=tuple(run_ids),
        )
        for signature, run_ids in groups.items()
        if len(run_ids) >= minimum_occurrences
    ]
    candidates.sort(key=lambda item: (-item.occurrences, item.fingerprint))
    return candidates[:limit]
