"""Agent coordination - Multiple agents working together."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

GITEA_INTERNAL = os.getenv("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")


class AgentRole(Enum):
    """Agent roles."""
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    SECURITY = "security"
    TEST_WRITER = "test-writer"
    ORCHESTRATOR = "orchestrator"


class TaskStatus(Enum):
    """Task status."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """A task for an agent."""
    id: str
    title: str
    description: str
    assigned_to: AgentRole | None = None
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    issue_number: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentLock:
    """Lock mechanism for concurrent access."""
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.headers = {"Authorization": f"token {GITEA_TOKEN}"}
        self.locks: dict[str, dict] = {}
    
    async def acquire(self, resource: str, agent: str, timeout: int = 3600) -> bool:
        """Acquire a lock on a resource."""
        # Check if locked
        if resource in self.locks:
            lock = self.locks[resource]
            if lock["agent"] != agent:
                # Check if lock expired
                elapsed = (datetime.now(UTC) - lock["acquired_at"]).total_seconds()
                if elapsed < lock["timeout"]:
                    return False
        
        # Acquire lock
        self.locks[resource] = {
            "agent": agent,
            "acquired_at": datetime.now(UTC),
            "timeout": timeout,
        }
        return True
    
    async def release(self, resource: str, agent: str):
        """Release a lock."""
        if resource in self.locks and self.locks[resource]["agent"] == agent:
            del self.locks[resource]
    
    def is_locked(self, resource: str) -> bool:
        """Check if resource is locked."""
        if resource not in self.locks:
            return False
        
        lock = self.locks[resource]
        elapsed = (datetime.now(UTC) - lock["acquired_at"]).total_seconds()
        return elapsed < lock["timeout"]


class AgentCoordinator:
    """Coordinate multiple agents working on the same project."""
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.lock = AgentLock(owner, repo)
        self.tasks: dict[str, Task] = {}
        self.headers = {"Authorization": f"token {GITEA_TOKEN}"}
    
    async def create_task(
        self,
        title: str,
        description: str,
        assigned_to: AgentRole | None = None,
        dependencies: list[str] | None = None,
    ) -> Task:
        """Create a new task."""
        task_id = f"task-{len(self.tasks) + 1}"
        task = Task(
            id=task_id,
            title=title,
            description=description,
            assigned_to=assigned_to,
            dependencies=dependencies or [],
        )
        self.tasks[task_id] = task
        
        # Create Gitea issue for tracking
        task.issue_number = await self._create_issue(task)
        
        return task
    
    async def assign_task(self, task_id: str, agent: AgentRole):
        """Assign a task to an agent."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.assigned_to = agent
            task.status = TaskStatus.IN_PROGRESS
            task.updated_at = datetime.now(UTC)
            
            # Update Gitea issue
            await self._update_issue_status(task)
    
    async def complete_task(self, task_id: str, result: Any):
        """Mark a task as completed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.updated_at = datetime.now(UTC)
            
            # Update Gitea issue
            await self._update_issue_status(task)
    
    async def fail_task(self, task_id: str, error: str):
        """Mark a task as failed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.error = error
            task.updated_at = datetime.now(UTC)
            
            # Update Gitea issue
            await self._update_issue_status(task)
    
    def get_ready_tasks(self) -> list[Task]:
        """Get tasks ready to be worked on."""
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check dependencies
            deps_met = all(
                self.tasks.get(dep, Task(id="", title="", description="")).status == TaskStatus.COMPLETED
                for dep in task.dependencies
            )
            
            if deps_met:
                ready.append(task)
        
        return ready
    
    def get_task_status(self) -> dict[str, Any]:
        """Get overall task status."""
        return {
            "total": len(self.tasks),
            "pending": sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING),
            "in_progress": sum(1 for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS),
            "completed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED),
        }
    
    async def _create_issue(self, task: Task) -> int | None:
        """Create Gitea issue for task."""
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.post(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues",
                headers=self.headers,
                json={
                    "title": f"[Agent] {task.title}",
                    "body": task.description,
                },
            )
            
            if resp.status_code == 201:
                return resp.json()["number"]
            return None
    
    async def _update_issue_status(self, task: Task):
        """Update Gitea issue status."""
        if task.issue_number is None:
            return

        body = f"Agent task status: **{task.status.value}**"
        if task.assigned_to:
            body += f"\n\nAssigned to: `{task.assigned_to.value}`"
        if task.status == TaskStatus.COMPLETED:
            body += f"\n\nResult: {task.result}"
        elif task.status == TaskStatus.FAILED:
            body += f"\n\nError: {task.error}"

        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            response = await client.post(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues/{task.issue_number}/comments",
                headers=self.headers,
                json={"body": body},
            )
            response.raise_for_status()
