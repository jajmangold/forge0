"""Bounded validation and normalization for structured critic findings."""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from typing import Any

MAX_FEEDBACK_CHARS = 2_000
MAX_FIELD_CHARS = 1_000
MAX_FINDINGS = 10
MAX_ACCEPTANCE_CRITERIA = 20
MAX_ACCEPTANCE_EVIDENCE_CHARS = 500
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True, slots=True)
class CriticFinding:
    severity: str
    file: str
    concern: str
    evidence: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class AcceptanceReview:
    criterion_index: int
    passed: bool
    evidence: str


def extract_acceptance_criteria(text: str) -> list[str]:
    """Extract a bounded bullet list from the sole level 1-3 acceptance heading."""
    if not isinstance(text, str):
        raise ValueError("issue text must be a string")
    lines = text.splitlines()
    headings = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"#{1,3}\s+acceptance criteria\s*", line, re.IGNORECASE)
    ]
    if len(headings) != 1:
        raise ValueError("issue must contain exactly one Acceptance Criteria heading")
    criteria: list[str] = []
    for line in lines[headings[0] + 1 :]:
        if re.match(r"^#{1,6}\s+", line):
            break
        match = re.match(r"^\s*[-*+]\s+(.+?)\s*$", line)
        if match:
            criteria.append(" ".join(match.group(1).split()))
    if not criteria:
        raise ValueError("Acceptance Criteria must contain at least one bullet")
    if len(criteria) > MAX_ACCEPTANCE_CRITERIA:
        raise ValueError(f"Acceptance Criteria exceeds {MAX_ACCEPTANCE_CRITERIA} bullets")
    return criteria


def _acceptance_reviews(
    value: Any, expected_count: int, evidence_text: str | None
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise ValueError(f"acceptance_reviews must contain exactly {expected_count} entries")
    normalized: list[AcceptanceReview] = []
    seen: set[int] = set()
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"acceptance_reviews[{position}] must be an object")
        if set(item) != {"criterion_index", "pass", "evidence"}:
            raise ValueError(
                f"acceptance_reviews[{position}] must contain exactly criterion_index, pass, and evidence"
            )
        index = item["criterion_index"]
        if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= expected_count:
            raise ValueError(f"acceptance_reviews[{position}].criterion_index is out of range")
        if index in seen:
            raise ValueError(f"acceptance_reviews contains duplicate criterion index {index}")
        seen.add(index)
        passed = item["pass"]
        if not isinstance(passed, bool):
            raise ValueError(f"acceptance_reviews[{position}].pass must be a boolean")
        raw_evidence = item["evidence"]
        if not isinstance(raw_evidence, str):
            raise ValueError(f"acceptance_reviews[{position}].evidence must be a string")
        raw_evidence = raw_evidence.strip()
        if not raw_evidence or len(raw_evidence) > MAX_ACCEPTANCE_EVIDENCE_CHARS:
            raise ValueError(f"acceptance_reviews[{position}].evidence must be 1-500 characters")
        if evidence_text is not None and raw_evidence not in evidence_text:
            raise ValueError(f"acceptance_reviews[{position}].evidence is not an exact supplied quote")
        evidence = html.escape(raw_evidence, quote=True).replace("`", "&#96;")
        normalized.append(AcceptanceReview(index, passed, evidence))
    normalized.sort(key=lambda review: review.criterion_index)
    return [
        {"criterion_index": review.criterion_index, "pass": review.passed, "evidence": review.evidence}
        for review in normalized
    ]


def _text(value: Any, name: str, *, limit: int, allow_blank: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    normalized = " ".join(value.split())
    if not normalized and not allow_blank:
        raise ValueError(f"{name} must not be blank")
    return html.escape(normalized, quote=True).replace("`", "&#96;")


def _finding(value: Any, changed_files: set[str] | None, index: int) -> CriticFinding:
    if not isinstance(value, dict):
        raise ValueError(f"findings[{index}] must be an object")
    required = {"severity", "file", "concern", "evidence", "recommendation"}
    missing = required - value.keys()
    if missing:
        raise ValueError(f"findings[{index}] is missing {', '.join(sorted(missing))}")
    severity = value["severity"]
    if not isinstance(severity, str) or severity not in SEVERITY_ORDER:
        raise ValueError(f"findings[{index}].severity must be high, medium, or low")
    raw_file = value["file"]
    if not isinstance(raw_file, str):
        raise ValueError(f"findings[{index}].file must be a string")
    if len(raw_file) > MAX_FIELD_CHARS:
        raise ValueError(f"findings[{index}].file exceeds {MAX_FIELD_CHARS} characters")
    file_name = " ".join(raw_file.split())
    if file_name and changed_files is not None and file_name not in changed_files:
        raise ValueError(f"findings[{index}].file is outside the changed-file set")
    return CriticFinding(
        severity=severity,
        file=html.escape(file_name, quote=True).replace("`", "&#96;"),
        concern=_text(value["concern"], f"findings[{index}].concern", limit=MAX_FIELD_CHARS),
        evidence=_text(value["evidence"], f"findings[{index}].evidence", limit=MAX_FIELD_CHARS),
        recommendation=_text(
            value["recommendation"], f"findings[{index}].recommendation", limit=MAX_FIELD_CHARS
        ),
    )


def validate_critic_response(
    value: Any,
    *,
    changed_files: set[str] | None = None,
    expected_criterion_count: int | None = None,
    acceptance_evidence_text: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic JSON-serializable critic response or raise ValueError."""
    if not isinstance(value, dict):
        raise ValueError("critic response must be an object")
    missing = {"pass", "feedback", "findings"} - value.keys()
    if missing:
        raise ValueError(f"critic response is missing {', '.join(sorted(missing))}")
    passed = value["pass"]
    if not isinstance(passed, bool):
        raise ValueError("pass must be a boolean")
    feedback = _text(
        value["feedback"], "feedback", limit=MAX_FEEDBACK_CHARS, allow_blank=True
    )
    raw_findings = value["findings"]
    if not isinstance(raw_findings, list):
        raise ValueError("findings must be an array")
    if len(raw_findings) > MAX_FINDINGS:
        raise ValueError(f"findings exceeds {MAX_FINDINGS} entries")
    findings = [_finding(item, changed_files, index) for index, item in enumerate(raw_findings)]
    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER[item.severity],
            item.file,
            item.concern,
            item.evidence,
            item.recommendation,
        )
    )
    if passed and any(item.severity == "high" for item in findings):
        raise ValueError("pass cannot be true with a high-severity finding")
    if not passed and not feedback and not findings:
        raise ValueError("a failing critic requires feedback or a finding")
    result = {"pass": passed, "feedback": feedback, "findings": [asdict(item) for item in findings]}
    if expected_criterion_count is not None:
        reviews = _acceptance_reviews(
            value.get("acceptance_reviews"), expected_criterion_count, acceptance_evidence_text
        )
        if passed and any(review["pass"] is not True for review in reviews):
            raise ValueError("pass cannot be true when an acceptance review fails")
        result["acceptance_reviews"] = reviews
    return result
