"""Experiment tracking with Weights & Biases."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False


class ExperimentTracker:
    """Track agent experiments with W&B."""
    
    def __init__(self, project: str = "forge0", entity: str | None = None):
        self.project = project
        self.entity = entity
        self.run = None
    
    @contextmanager
    def track(self, name: str, tags: list[str] | None = None, config: dict | None = None):
        """Context manager to track an experiment."""
        if not WANDB_AVAILABLE:
            yield self
            return
        
        try:
            self.run = wandb.init(
                project=self.project,
                name=name,
                entity=self.entity,
                tags=tags or [],
                config=config or {},
            )
            yield self
        finally:
            if self.run:
                wandb.finish()
    
    def log(self, metrics: dict[str, Any]):
        """Log metrics."""
        if self.run:
            wandb.log(metrics)
    
    def log_artifact(self, path: str, name: str, artifact_type: str = "artifact"):
        """Log a file as an artifact."""
        if self.run:
            artifact = wandb.Artifact(name, type=artifact_type)
            artifact.add_file(path)
            wandb.log_artifact(artifact)
    
    def log_code(self, directory: str, name: str = "code"):
        """Log a directory of code as an artifact."""
        if self.run:
            artifact = wandb.Artifact(name, type="code")
            artifact.add_dir(directory)
            wandb.log_artifact(artifact)


# Global tracker instance
tracker = ExperimentTracker()


def track_agent_run(agent_name: str, task_id: int):
    """Decorator to track an agent run."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with tracker.track(
                name=f"{agent_name}-task-{task_id}",
                tags=[f"agent:{agent_name}", f"task:{task_id}"],
                config={"agent": agent_name, "task_id": task_id},
            ):
                result = await func(*args, **kwargs)
                tracker.log({
                    "success": getattr(result, "success", True),
                    "agent": agent_name,
                    "task_id": task_id,
                })
                return result
        return wrapper
    return decorator
