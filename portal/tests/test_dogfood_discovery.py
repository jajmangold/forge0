from dataclasses import dataclass

from app.dogfood_discovery import discover_failure_candidates, normalize_failure


@dataclass
class Record:
    id: str
    status: str
    error: str


def test_normalize_failure_removes_dynamic_ids_and_counts() -> None:
    first = normalize_failure("Run abcdef123456 failed after 12 calls")
    second = normalize_failure("Run fedcba987654 failed after 99 calls")

    assert first == second == "run <id> failed after <n> calls"


def test_discovery_requires_recurrence_and_prioritizes_frequency() -> None:
    records = [
        Record("one", "failed", "budget exhausted after 2 calls"),
        Record("two", "failed", "budget exhausted after 3 calls"),
        Record("three", "failed", "budget exhausted after 4 calls"),
        Record("four", "failed", "wrong target abcdef123456"),
        Record("five", "failed", "wrong target fedcba987654"),
        Record("six", "draft-opened", "budget exhausted after 8 calls"),
    ]

    candidates = discover_failure_candidates(records)

    assert [candidate.occurrences for candidate in candidates] == [3, 2]
    assert candidates[0].run_ids == ("one", "two", "three")


def test_discovery_excludes_publication_operator_review_failures() -> None:
    records = [
        Record("one", "failed", "Publishing interrupted; operator review is required"),
        Record("two", "failed", "Publishing interrupted; operator review is required"),
    ]

    assert discover_failure_candidates(records) == []
