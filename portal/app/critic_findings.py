"""Bounded validation and normalization for structured critic findings."""
from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from typing import Any

MAX_FEEDBACK_CHARS = 2_000
MAX_FIELD_CHARS = 1_000
MAX_FINDINGS = 10
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True, slots=True)
class CriticFinding:
    severity: str
    file: str
    concern: str
    evidence: str
    recommendation: str


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
    value: Any, *, changed_files: set[str] | None = None
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
    return {"pass": passed, "feedback": feedback, "findings": [asdict(item) for item in findings]}
