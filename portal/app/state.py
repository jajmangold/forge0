"""State persistence - Save and resume agent state via Gitea issues."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx

GITEA_INTERNAL = os.getenv("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")


class AgentState:
    """Persist agent state in Gitea issue comments."""
    
    def __init__(self, owner: str, repo: str, issue_number: int):
        self.owner = owner
        self.repo = repo
        self.issue_number = issue_number
        self.headers = {"Authorization": f"token {GITEA_TOKEN}"}
    
    async def save(self, agent_name: str, state: dict[str, Any]):
        """Save agent state as issue comment."""
        state_data = {
            "agent": agent_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "state": state,
        }
        
        comment_body = f"## Agent State: {agent_name}\n\n```json\n{json.dumps(state_data, indent=2)}\n```"
        
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            await client.post(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues/{self.issue_number}/comments",
                headers=self.headers,
                json={"body": comment_body},
            )
    
    async def load(self, agent_name: str) -> dict[str, Any] | None:
        """Load latest agent state from issue comments."""
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues/{self.issue_number}/comments",
                headers=self.headers,
                params={"limit": 50},
            )
            
            if resp.status_code != 200:
                return None
            
            comments = resp.json()
            
            # Find latest state for this agent
            for comment in reversed(comments):
                body = comment.get("body", "")
                if f"## Agent State: {agent_name}" in body:
                    # Extract JSON
                    start = body.find("```json\n") + 8
                    end = body.find("\n```", start)
                    if start > 8 and end > start:
                        json_str = body[start:end]
                        data = json.loads(json_str)
                        return data.get("state")
            
            return None
    
    async def save_checkpoint(self, agent_name: str, phase: str, progress: dict):
        """Save a checkpoint for resuming work."""
        await self.save(agent_name, {
            "phase": phase,
            "progress": progress,
            "checkpoint": True,
        })
    
    async def get_latest_checkpoint(self, agent_name: str) -> dict | None:
        """Get latest checkpoint for resuming work."""
        state = await self.load(agent_name)
        if state and state.get("checkpoint"):
            return state
        return None


class WorkflowState:
    """Track overall workflow state."""
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.headers = {"Authorization": f"token {GITEA_TOKEN}"}
    
    async def create_task_issue(self, title: str, description: str, labels: list[str] | None = None) -> int:
        """Create a new task issue."""
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.post(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues",
                headers=self.headers,
                json={
                    "title": title,
                    "body": description,
                    "labels": labels or [],
                },
            )
            
            if resp.status_code == 201:
                return resp.json()["number"]
            return -1
    
    async def update_task_status(self, issue_number: int, status: str):
        """Update task status via label."""
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            # Get current labels
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels",
                headers=self.headers,
            )
            
            if resp.status_code == 200:
                current_labels = [label["name"] for label in resp.json()]
                # Remove old status labels
                new_labels = [label for label in current_labels if not label.startswith("status:")]
                new_labels.append(f"status:{status}")
                
                await client.put(
                    f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels",
                    headers=self.headers,
                    json={"labels": new_labels},
                )
    
    async def add_comment(self, issue_number: int, body: str):
        """Add comment to issue."""
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            await client.post(
                f"{GITEA_INTERNAL}/api/v1/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments",
                headers=self.headers,
                json={"body": body},
            )
