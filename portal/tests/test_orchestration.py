"""Tests for the orchestration engine — written BEFORE implementation (TDD)."""

import pytest
import yaml


class TestWorkflowState:
    """Test workflow state management."""

    def test_loads_workflow_yaml(self, tmp_path):
        """Workflow state loads from .forge0/workflow.yaml."""
        forge0 = tmp_path / ".forge0"
        forge0.mkdir()
        workflow = forge0 / "workflow.yaml"
        workflow.write_text(yaml.dump({
            "current_phase": "requirements",
            "phase_status": "in-progress",
            "phases": {
                "intake": {"status": "complete"},
                "requirements": {"status": "in-progress"},
            },
        }))

        from app.orchestration import WorkflowState

        state = WorkflowState.load(tmp_path)
        assert state.current_phase == "requirements"
        assert state.phase_status == "in-progress"
        assert state.phases["intake"]["status"] == "complete"

    def test_creates_default_workflow_if_missing(self, tmp_path):
        """Creates default workflow if .forge0/workflow.yaml doesn't exist."""
        from app.orchestration import WorkflowState

        state = WorkflowState.load(tmp_path)
        assert state.current_phase == "intake"
        assert state.phase_status == "pending"

    def test_transitions_to_next_phase(self, tmp_path):
        """advance() moves to the next phase and resets status."""
        forge0 = tmp_path / ".forge0"
        forge0.mkdir()
        workflow = forge0 / "workflow.yaml"
        workflow.write_text(yaml.dump({
            "current_phase": "intake",
            "phase_status": "complete",
            "phases": {
                "intake": {"status": "complete"},
            },
        }))

        from app.orchestration import WorkflowState

        state = WorkflowState.load(tmp_path)
        state.advance()
        assert state.current_phase == "requirements"
        assert state.phase_status == "pending"

    def test_persists_state_on_save(self, tmp_path):
        """save() writes state back to workflow.yaml."""
        from app.orchestration import WorkflowState

        state = WorkflowState.load(tmp_path)
        state.current_phase = "requirements"
        state.phase_status = "in-progress"
        state.save()

        loaded = WorkflowState.load(tmp_path)
        assert loaded.current_phase == "requirements"

    def test_phase_order_is_enforced(self, tmp_path):
        """Cannot skip phases — advance() follows the defined order."""
        from app.orchestration import WorkflowState

        state = WorkflowState.load(tmp_path)
        # intake -> requirements -> architecture -> decomposition -> tdd -> review
        state.current_phase = "requirements"
        state.advance()
        assert state.current_phase == "architecture"
        state.advance()
        assert state.current_phase == "decomposition"
        state.advance()
        assert state.current_phase == "tdd"
        state.advance()
        assert state.current_phase == "review"

    def test_cannot_advance_past_review(self, tmp_path):
        """Cannot advance past the review phase."""
        from app.orchestration import WorkflowState

        state = WorkflowState.load(tmp_path)
        state.current_phase = "review"
        state.phase_status = "complete"
        with pytest.raises(ValueError, match="already at final"):
            state.advance()


class TestOrchestrationEngine:
    """Test the orchestration engine dispatch logic."""

    def test_get_agent_for_phase(self):
        """Each phase maps to the correct agent type."""
        from app.orchestration import OrchestrationEngine

        engine = OrchestrationEngine()
        assert engine.get_agent_type("requirements") == "requirements"
        assert engine.get_agent_type("architecture") == "architecture"
        assert engine.get_agent_type("decomposition") == "decomposition"
        assert engine.get_agent_type("tdd") == "implementation"
        assert engine.get_agent_type("review") == "critic"

    def test_validates_phase_transition(self):
        """Engine rejects invalid phase transitions."""
        from app.orchestration import OrchestrationEngine

        engine = OrchestrationEngine()
        assert engine.can_transition("intake", "requirements") is True
        assert engine.can_transition("requirements", "architecture") is True
        assert engine.can_transition("intake", "tdd") is False  # skip
        assert engine.can_transition("review", "intake") is False  # backward
