from __future__ import annotations

import pytest
from app.dogfood_planning import (
    DogfoodError,
    render_shared_contract_ledger,
    validate_shared_contracts,
)


def test_validate_shared_contracts_accepts_absent_without_mutation() -> None:
    plan = {"files": ["README.md"]}

    assert validate_shared_contracts(plan) == []
    assert plan == {"files": ["README.md"]}


def test_validate_shared_contracts_normalizes_present_values() -> None:
    plan = {"shared_contracts": ["  keep API stable  ", "preserve errors"]}

    assert validate_shared_contracts(plan) == ["keep API stable", "preserve errors"]
    assert plan["shared_contracts"] == ["keep API stable", "preserve errors"]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("not a list", "Planner shared_contracts must be an array"),
        ([123], "Planner shared_contracts entries must be strings"),
        (["   "], "Planner shared_contracts entries must be non-empty"),
        (["x" * 201], "Planner shared_contracts entries must be at most 200 characters"),
        (["duplicate", " duplicate "], "Planner shared_contracts must not contain duplicates"),
        ([str(index) for index in range(13)], "Planner shared_contracts must contain at most 12 entries"),
    ],
)
def test_validate_shared_contracts_preserves_exact_errors(value, message: str) -> None:
    with pytest.raises(DogfoodError) as raised:
        validate_shared_contracts({"shared_contracts": value})

    assert str(raised.value) == message


def test_render_shared_contract_ledger_is_self_contained() -> None:
    rendered = render_shared_contract_ledger({"shared_contracts": ["one", "two"]})

    assert rendered == "Shared contract ledger:\n- one\n- two"
    assert rendered.count("Shared contract ledger:") == 1


@pytest.mark.parametrize("plan", [{}, {"shared_contracts": []}])
def test_render_shared_contract_ledger_marks_empty_explicitly(plan) -> None:
    assert render_shared_contract_ledger(plan) == "Shared contract ledger:\n(none)"
