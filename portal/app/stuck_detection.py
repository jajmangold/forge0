"""Stuck detection - Detect when agent is looping and break out."""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class Action:
    """Represents an agent action."""
    tool: str
    input: dict[str, Any]
    output: Any = None
    
    @property
    def fingerprint(self) -> str:
        """Create fingerprint for deduplication."""
        data = f"{self.tool}:{self.input}"
        return hashlib.md5(data.encode()).hexdigest()


class StuckDetector:
    """Detect when agent is stuck in a loop."""
    
    def __init__(
        self,
        max_history: int = 20,
        max_repeats: int = 3,
        max_same_tool: int = 5,
        cost_limit: float = 5.0,
        iteration_limit: int = 50,
    ):
        self.history: deque[Action] = deque(maxlen=max_history)
        self.max_repeats = max_repeats
        self.max_same_tool = max_same_tool
        self.cost_limit = cost_limit
        self.iteration_limit = iteration_limit
        self.iteration_count = 0
        self.total_cost = 0.0
        self.tool_counts: dict[str, int] = {}
    
    def record(self, action: Action) -> bool:
        """Record an action and check if stuck."""
        self.iteration_count += 1
        self.history.append(action)
        
        # Track tool usage
        self.tool_counts[action.tool] = self.tool_counts.get(action.tool, 0) + 1
        
        # Check stuck conditions
        if self._check_repeating_pattern():
            return True
        if self._check_same_tool_loop():
            return True
        if self._check_iteration_limit():
            return True
        if self._check_cost_limit():
            return True
        
        return False
    
    def add_cost(self, cost: float):
        """Add to total cost."""
        self.total_cost += cost
    
    def _check_repeating_pattern(self) -> bool:
        """Check for repeating action patterns."""
        if len(self.history) < 3:
            return False
        
        # Check for A-B-A-B pattern
        recent = list(self.history)[-6:]
        fingerprints = [a.fingerprint for a in recent]
        
        # Check if last 2 actions repeat
        if len(fingerprints) >= 4:
            if fingerprints[-1] == fingerprints[-3] and fingerprints[-2] == fingerprints[-4]:
                return True
        
        # Check if same action repeated 3+ times
        if len(fingerprints) >= 3:
            if len(set(fingerprints[-3:])) == 1:
                return True
        
        return False
    
    def _check_same_tool_loop(self) -> bool:
        """Check if same tool used too many times consecutively."""
        if len(self.history) < self.max_same_tool:
            return False
        
        recent_tools = [a.tool for a in list(self.history)[-self.max_same_tool:]]
        return len(set(recent_tools)) == 1
    
    def _check_iteration_limit(self) -> bool:
        """Check if iteration limit exceeded."""
        return self.iteration_count >= self.iteration_limit
    
    def _check_cost_limit(self) -> bool:
        """Check if cost limit exceeded."""
        return self.total_cost >= self.cost_limit
    
    def get_status(self) -> dict[str, Any]:
        """Get current detector status."""
        return {
            "iterations": self.iteration_count,
            "cost": self.total_cost,
            "is_stuck": self._check_repeating_pattern() or self._check_same_tool_loop(),
            "over_budget": self._check_cost_limit(),
            "over_iterations": self._check_iteration_limit(),
        }
    
    def suggest_action(self) -> str:
        """Suggest what to do when stuck."""
        if self._check_repeating_pattern():
            return "REPEAT: Agent is repeating actions. Try a different approach."
        if self._check_same_tool_loop():
            return "LOOP: Same tool used repeatedly. Switch to a different tool."
        if self._check_iteration_limit():
            return "LIMIT: Iteration limit reached. Submit partial work."
        if self._check_cost_limit():
            return "BUDGET: Cost limit reached. Submit partial work."
        return "OK"


class CostTracker:
    """Track costs across agents."""
    
    def __init__(self, budget: float = 100.0):
        self.budget = budget
        self.spent = 0.0
        self.by_agent: dict[str, float] = {}
        self.by_model: dict[str, float] = {}
    
    def add(self, agent: str, model: str, cost: float):
        """Add cost."""
        self.spent += cost
        self.by_agent[agent] = self.by_agent.get(agent, 0) + cost
        self.by_model[model] = self.by_model.get(model, 0) + cost
    
    def remaining(self) -> float:
        """Get remaining budget."""
        return max(0, self.budget - self.spent)
    
    def is_over_budget(self) -> bool:
        """Check if over budget."""
        return self.spent >= self.budget
    
    def get_report(self) -> dict[str, Any]:
        """Get cost report."""
        return {
            "budget": self.budget,
            "spent": self.spent,
            "remaining": self.remaining(),
            "by_agent": self.by_agent,
            "by_model": self.by_model,
        }
