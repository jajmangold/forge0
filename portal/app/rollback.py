"""Rollback mechanism - Auto-revert on test failure."""
from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass
class Checkpoint:
    """A checkpoint for rollback."""
    id: str
    commit_sha: str
    branch: str
    message: str
    created_at: datetime
    files_changed: list[str]


class RollbackManager:
    """Manage rollbacks for code changes."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.checkpoints: list[Checkpoint] = []
    
    async def create_checkpoint(self, message: str) -> Checkpoint | None:
        """Create a checkpoint before making changes."""
        try:
            # Stage all changes
            await self._run_git("add", "-A")
            
            # Get current commit
            result = await self._run_git("rev-parse", "HEAD")
            commit_sha = result.strip()
            
            # Get current branch
            result = await self._run_git("branch", "--show-current")
            branch = result.strip()
            
            # Get changed files
            result = await self._run_git("diff", "--cached", "--name-only")
            files_changed = [f for f in result.strip().split("\n") if f]
            
            # Create checkpoint
            checkpoint = Checkpoint(
                id=f"checkpoint-{len(self.checkpoints) + 1}",
                commit_sha=commit_sha,
                branch=branch,
                message=message,
                created_at=datetime.now(timezone.utc),
                files_changed=files_changed,
            )
            self.checkpoints.append(checkpoint)
            
            return checkpoint
            
        except Exception as e:
            print(f"Failed to create checkpoint: {e}")
            return None
    
    async def rollback(self, checkpoint: Checkpoint | None = None) -> bool:
        """Rollback to a checkpoint."""
        try:
            if checkpoint:
                # Rollback to specific checkpoint
                await self._run_git("reset", "--hard", checkpoint.commit_sha)
            elif self.checkpoints:
                # Rollback to last checkpoint
                last = self.checkpoints[-1]
                await self._run_git("reset", "--hard", last.commit_sha)
            else:
                # No checkpoints, rollback all uncommitted changes
                await self._run_git("checkout", "--", ".")
            
            return True
            
        except Exception as e:
            print(f"Failed to rollback: {e}")
            return False
    
    async def auto_rollback_on_failure(
        self,
        func,
        *args,
        **kwargs,
    ) -> tuple[Any, bool]:
        """Execute function with auto-rollback on failure."""
        # Create checkpoint
        checkpoint = await self.create_checkpoint("Before operation")
        
        try:
            result = await func(*args, **kwargs)
            return result, True
            
        except Exception as e:
            # Rollback on failure
            await self.rollback(checkpoint)
            raise e
    
    async def _run_git(self, *args: str) -> str:
        """Run git command."""
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=self.repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Git command failed: {stderr.decode()}")
        
        return stdout.decode()


class SafeCodeChanger:
    """Make code changes safely with rollback."""
    
    def __init__(self, repo_path: str = "."):
        self.rollback_manager = RollbackManager(repo_path)
    
    async def edit_file(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> bool:
        """Edit file with rollback on failure."""
        # Create checkpoint
        checkpoint = await self.rollback_manager.create_checkpoint(f"Edit {file_path}")
        
        try:
            # Read current content
            path = Path(file_path)
            if not path.exists():
                return False
            
            current_content = path.read_text()
            
            # Verify old content matches
            if old_content not in current_content:
                return False
            
            # Replace content
            new_file_content = current_content.replace(old_content, new_content, 1)
            
            # Write new content
            path.write_text(new_file_content)
            
            return True
            
        except Exception as e:
            # Rollback on failure
            await self.rollback_manager.rollback(checkpoint)
            return False
    
    async def create_file(
        self,
        file_path: str,
        content: str,
    ) -> bool:
        """Create file with rollback on failure."""
        # Create checkpoint
        checkpoint = await self.rollback_manager.create_checkpoint(f"Create {file_path}")
        
        try:
            path = Path(file_path)
            
            # Check if file already exists
            if path.exists():
                return False
            
            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            path.write_text(content)
            
            return True
            
        except Exception as e:
            # Rollback on failure
            await self.rollback_manager.rollback(checkpoint)
            return False
    
    async def delete_file(
        self,
        file_path: str,
    ) -> bool:
        """Delete file with rollback on failure."""
        # Create checkpoint
        checkpoint = await self.rollback_manager.create_checkpoint(f"Delete {file_path}")
        
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                return False
            
            # Delete file
            path.unlink()
            
            return True
            
        except Exception as e:
            # Rollback on failure
            await self.rollback_manager.rollback(checkpoint)
            return False
