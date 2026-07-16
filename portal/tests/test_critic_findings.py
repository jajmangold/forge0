import json

import pytest
from app.critic_findings import (
    MAX_FEEDBACK_CHARS,
    MAX_FIELD_CHARS,
    MAX_FINDINGS,
    build_evidence_spans,
    render_evidence_spans,
    validate_critic_response,
)


def finding(**changes):
    value = {
        "severity": "low",
        "file": "portal/app/dogfood.py",
        "concern": "Concern",
        "evidence": "Evidence",
        "recommendation": "Recommendation",
    }
    value.update(changes)
    return value


def response(**changes):
    value = {"pass": True, "feedback": "Looks good", "findings": []}
    value.update(changes)
    return value


@pytest.mark.parametrize("missing", ["pass", "feedback", "findings"])
def test_requires_top_level_fields(missing) -> None:
    value = response()
    del value[missing]
    with pytest.raises(ValueError, match="missing"):
        validate_critic_response(value)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [("pass", 1), ("feedback", None), ("findings", {}), ("findings", "bad")],
)
def test_rejects_top_level_type_errors(field, invalid) -> None:
    with pytest.raises(ValueError):
        validate_critic_response(response(**{field: invalid}))


def test_enforces_feedback_and_finding_count_limits() -> None:
    with pytest.raises(ValueError, match="feedback exceeds"):
        validate_critic_response(response(feedback="x" * (MAX_FEEDBACK_CHARS + 1)))
    with pytest.raises(ValueError, match="findings exceeds"):
        validate_critic_response(response(findings=[finding()] * (MAX_FINDINGS + 1)))


@pytest.mark.parametrize("missing", ["severity", "file", "concern", "evidence", "recommendation"])
def test_requires_finding_fields(missing) -> None:
    item = finding()
    del item[missing]
    with pytest.raises(ValueError, match="missing"):
        validate_critic_response(response(findings=[item]))


@pytest.mark.parametrize("field", ["file", "concern", "evidence", "recommendation"])
def test_rejects_finding_type_and_size_errors(field) -> None:
    with pytest.raises(ValueError):
        validate_critic_response(response(findings=[finding(**{field: 3})]))
    with pytest.raises(ValueError, match="exceeds"):
        validate_critic_response(response(findings=[finding(**{field: "x" * (MAX_FIELD_CHARS + 1)})]))


@pytest.mark.parametrize("field", ["concern", "evidence", "recommendation"])
def test_rejects_blank_required_finding_text(field) -> None:
    with pytest.raises(ValueError, match="blank"):
        validate_critic_response(response(findings=[finding(**{field: " \n\t"})]))


def test_enforces_severity_and_changed_file_scope() -> None:
    with pytest.raises(ValueError, match="severity"):
        validate_critic_response(response(findings=[finding(severity="critical")]))
    with pytest.raises(ValueError, match="changed-file"):
        validate_critic_response(
            response(findings=[finding(file="outside.py")]),
            changed_files={"portal/app/dogfood.py"},
        )


def test_blank_file_is_a_repository_global_finding() -> None:
    result = validate_critic_response(
        response(findings=[finding(file="")]), changed_files={"portal/app/dogfood.py"}
    )
    assert result["findings"][0]["file"] == ""


def test_semantic_pass_and_fail_rules() -> None:
    with pytest.raises(ValueError, match="high-severity"):
        validate_critic_response(response(findings=[finding(severity="high")]))
    with pytest.raises(ValueError, match="requires"):
        validate_critic_response(response(**{"pass": False}, feedback="", findings=[]))
    assert validate_critic_response(
        response(**{"pass": False}, feedback="defect", findings=[])
    )["pass"] is False


def test_normalizes_escapes_sorts_and_round_trips() -> None:
    result = validate_critic_response(
        response(
            feedback="  review\nneeded  ",
            findings=[
                finding(severity="low", file="z.py", concern="Z"),
                finding(
                    severity="medium",
                    file="a.py",
                    concern=" <b>`unsafe`</b> ",
                    evidence="line\n  two",
                ),
            ],
        ),
        changed_files={"a.py", "z.py"},
    )
    assert result["feedback"] == "review needed"
    assert [item["severity"] for item in result["findings"]] == ["medium", "low"]
    assert result["findings"][0]["concern"] == "&lt;b&gt;&#96;unsafe&#96;&lt;/b&gt;"
    assert result["findings"][0]["evidence"] == "line two"
    assert json.loads(json.dumps(result)) == result


def test_evidence_spans_are_deterministic_bounded_and_source_prefixed() -> None:
    spans = build_evidence_spans("+short\n" + ("x" * 401), "read-only\n")

    assert spans == {
        "D0001": "+short",
        "D0002": "x" * 400,
        "D0003": "x",
        "E0001": "read-only",
    }
    assert render_evidence_spans(spans).startswith("[D0001] +short\n[D0002] ")


def test_acceptance_reviews_resolve_only_known_span_ids() -> None:
    value = response(
        acceptance_reviews=[
            {"criterion_index": 1, "pass": True, "evidence_span_ids": ["D0001", "E0001"]}
        ]
    )
    result = validate_critic_response(
        value,
        expected_criterion_count=1,
        acceptance_evidence_spans={"D0001": "+safe <change>", "E0001": "existing `contract`"},
    )

    assert result["acceptance_reviews"] == [
        {
            "criterion_index": 1,
            "pass": True,
            "evidence": "+safe &lt;change&gt;\nexisting &#96;contract&#96;",
            "evidence_span_ids": ["D0001", "E0001"],
        }
    ]
    value["acceptance_reviews"][0]["evidence_span_ids"] = ["D9999"]
    with pytest.raises(ValueError, match="unknown span D9999"):
        validate_critic_response(
            value,
            expected_criterion_count=1,
            acceptance_evidence_spans={"D0001": "+safe"},
        )
