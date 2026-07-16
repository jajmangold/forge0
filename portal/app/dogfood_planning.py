"""Validation and prompt rendering for Forge0 planning contracts."""
from __future__ import annotations

from typing import Any


class DogfoodError(RuntimeError):
    """A self-extension run violated a safety boundary or could not proceed."""


def validate_shared_contracts(plan: dict[str, Any]) -> list[str]:
    """Validate and normalize the planner-owned shared contract ledger."""
    if "shared_contracts" not in plan:
        return []
    raw_contracts = plan.get("shared_contracts", [])
    if not isinstance(raw_contracts, list):
        raise DogfoodError("Planner shared_contracts must be an array")
    if len(raw_contracts) > 12:
        raise DogfoodError("Planner shared_contracts must contain at most 12 entries")
    contracts: list[str] = []
    seen: set[str] = set()
    for raw_contract in raw_contracts:
        if not isinstance(raw_contract, str):
            raise DogfoodError("Planner shared_contracts entries must be strings")
        contract = raw_contract.strip()
        if not contract:
            raise DogfoodError("Planner shared_contracts entries must be non-empty")
        if len(contract) > 200:
            raise DogfoodError("Planner shared_contracts entries must be at most 200 characters")
        if contract in seen:
            raise DogfoodError("Planner shared_contracts must not contain duplicates")
        seen.add(contract)
        contracts.append(contract)
    plan["shared_contracts"] = contracts
    return contracts


def render_shared_contract_ledger(plan: dict[str, Any]) -> str:
    """Render one self-contained shared contract block for coder prompts."""
    contracts = plan.get("shared_contracts", [])
    entries = "\n".join(f"- {contract}" for contract in contracts) if contracts else "(none)"
    return f"Shared contract ledger:\n{entries}"
