"""Orchestration engine — deterministic workflow state machine."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Canonical phase order
PHASE_ORDER = [
    "intake",
    "requirements",
    "architecture",
    "decomposition",
    "tdd",
    "review",
]

# Phase → agent type mapping
PHASE_AGENT_MAP = {
    "intake": "intake",
    "requirements": "requirements",
    "architecture": "architecture",
    "decomposition": "decomposition",
    "tdd": "implementation",
    "review": "critic",
}


@dataclass
class WorkflowState:
    """Manages the .forge0/workflow.yaml state file."""
    current_phase: str = "intake"
    phase_status: str = "pending"
    phases: dict[str, dict[str, Any]] = field(default_factory=dict)
    _path: Path = field(default=Path("."), repr=False)

    @classmethod
    def load(cls, project_path: Path) -> WorkflowState:
        """Load workflow state from .forge0/workflow.yaml.
        Creates default if file doesn't exist."""
        forge0 = project_path / ".forge0"
        workflow_file = forge0 / "workflow.yaml"

        if workflow_file.exists():
            data = yaml.safe_load(workflow_file.read_text())
            return cls(
                current_phase=data.get("current_phase", "intake"),
                phase_status=data.get("phase_status", "pending"),
                phases=data.get("phases", {}),
                _path=project_path,
            )

        # Create default state
        forge0.mkdir(parents=True, exist_ok=True)
        state = cls(
            current_phase="intake",
            phase_status="pending",
            phases={},
            _path=project_path,
        )
        state.save()
        return state

    def save(self) -> None:
        """Persist state to .forge0/workflow.yaml."""
        forge0 = self._path / ".forge0"
        forge0.mkdir(parents=True, exist_ok=True)
        workflow_file = forge0 / "workflow.yaml"

        data = {
            "current_phase": self.current_phase,
            "phase_status": self.phase_status,
            "phases": self.phases,
        }
        workflow_file.write_text(yaml.dump(data, default_flow_style=False))

    def advance(self) -> None:
        """Move to the next phase. Raises ValueError if already at final phase."""
        if self.current_phase == "review" and self.phase_status == "complete":
            raise ValueError("Cannot advance: already at final phase (review)")

        try:
            idx = PHASE_ORDER.index(self.current_phase)
        except ValueError:
            raise ValueError(f"Unknown phase: {self.current_phase}")

        if idx >= len(PHASE_ORDER) - 1:
            raise ValueError("Cannot advance: already at final phase")

        # Mark current phase as complete
        self.phases.setdefault(self.current_phase, {})["status"] = "complete"
        self.current_phase = PHASE_ORDER[idx + 1]
        self.phase_status = "pending"
        self.phases.setdefault(self.current_phase, {})["status"] = "pending"
        self.save()


class OrchestrationEngine:
    """Deterministic orchestration engine.
    Reads workflow state and dispatches to the correct agent."""

    def get_agent_type(self, phase: str) -> str:
        """Return the agent type for a given phase."""
        return PHASE_AGENT_MAP.get(phase, phase)

    def can_transition(self, from_phase: str, to_phase: str) -> bool:
        """Check if a phase transition is valid."""
        try:
            from_idx = PHASE_ORDER.index(from_phase)
            to_idx = PHASE_ORDER.index(to_phase)
        except ValueError:
            return False

        # Only allow forward transitions by exactly one step
        return to_idx == from_idx + 1

    def get_next_phase(self, current_phase: str) -> str | None:
        """Return the next phase, or None if at the end."""
        try:
            idx = PHASE_ORDER.index(current_phase)
            if idx < len(PHASE_ORDER) - 1:
                return PHASE_ORDER[idx + 1]
        except ValueError:
            pass
        return None
