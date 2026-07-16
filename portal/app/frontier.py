"""Small, deterministic Pareto-front utilities shared by experiment harnesses."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, TypedDict


class Objective(TypedDict):
    name: str
    direction: Literal["minimize", "maximize"]


def dominates(
    left: Mapping[str, float],
    right: Mapping[str, float],
    objectives: Iterable[Objective],
) -> bool:
    """Return whether ``left`` Pareto-dominates ``right``."""
    at_least_as_good = True
    strictly_better = False
    for objective in objectives:
        name = objective["name"]
        left_value = float(left[name])
        right_value = float(right[name])
        if objective["direction"] == "minimize":
            at_least_as_good &= left_value <= right_value
            strictly_better |= left_value < right_value
        else:
            at_least_as_good &= left_value >= right_value
            strictly_better |= left_value > right_value
    return at_least_as_good and strictly_better


def pareto_front(
    candidates: Iterable[Mapping[str, Any]],
    objectives: list[Objective],
) -> list[dict[str, Any]]:
    """Return stable, non-dominated feasible candidates.

    A candidate is expected to contain a ``metrics`` mapping. Candidates marked
    ``feasible=false`` never enter the archive. Missing/non-numeric metrics are
    likewise excluded instead of silently becoming attractive extrema.
    """
    eligible: list[dict[str, Any]] = []
    for raw in candidates:
        candidate = dict(raw)
        if not candidate.get("feasible", True):
            continue
        metrics = candidate.get("metrics")
        if not isinstance(metrics, Mapping):
            continue
        try:
            for objective in objectives:
                float(metrics[objective["name"]])
        except (KeyError, TypeError, ValueError):
            continue
        eligible.append(candidate)

    return [
        candidate
        for index, candidate in enumerate(eligible)
        if not any(
            dominates(other["metrics"], candidate["metrics"], objectives)
            for other_index, other in enumerate(eligible)
            if other_index != index
        )
    ]
