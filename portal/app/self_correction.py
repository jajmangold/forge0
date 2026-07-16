"""Observation-driven self-correction - Agent sees its own output and fixes issues."""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass
class Feedback:
    """Feedback from running tools."""
    tool: str
    success: bool
    output: str
    errors: list[str]
    metrics: dict[str, Any]


class SelfCorrector:
    """Agent self-correction based on observation."""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.feedback_history: list[Feedback] = []
    
    async def observe_and_correct(
        self,
        code: str,
        file_path: str,
        language: str,
    ) -> tuple[str, list[Feedback]]:
        """Observe code and self-correct."""
        feedbacks = []
        current_code = code
        
        for attempt in range(self.max_retries):
            # Run all checks
            feedbacks.extend(await self._run_checks(current_code, file_path, language))
            
            # Get failed checks
            failed = [f for f in feedbacks if not f.success]
            
            if not failed:
                break
            
            # Self-correct based on feedback
            current_code = await self._correct(current_code, failed)
        
        self.feedback_history.extend(feedbacks)
        return current_code, feedbacks
    
    async def _run_checks(self, code: str, file_path: str, language: str) -> list[Feedback]:
        """Run all checks on code."""
        feedbacks = []
        
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix=f".{language}", delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # Language-specific checks
            if language in ("py", "python"):
                feedbacks.append(await self._run_pyright(temp_path))
                feedbacks.append(await self._run_ruff(temp_path))
                feedbacks.append(await self._run_pytest(temp_path))
            elif language in ("rs", "rust"):
                feedbacks.append(await self._run_clippy(temp_path))
                feedbacks.append(await self._run_cargo_test(temp_path))
            elif language in ("js", "ts", "javascript", "typescript"):
                feedbacks.append(await self._run_eslint(temp_path))
                feedbacks.append(await self._run_tsc(temp_path))
                feedbacks.append(await self._run_vitest(temp_path))
        finally:
            os.unlink(temp_path)
        
        return [f for f in feedbacks if f is not None]
    
    async def _run_pyright(self, path: str) -> Feedback:
        """Run pyright type checker."""
        try:
            result = await asyncio.create_subprocess_exec(
                "pyright", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode()
            errors = [line for line in output.split('\n') if 'error' in line.lower()]
            
            return Feedback(
                tool="pyright",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"error_count": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="pyright", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_ruff(self, path: str) -> Feedback:
        """Run ruff linter."""
        try:
            result = await asyncio.create_subprocess_exec(
                "ruff", "check", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode()
            errors = [line for line in output.split('\n') if line.strip()]
            
            return Feedback(
                tool="ruff",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"lint_errors": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="ruff", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_pytest(self, path: str) -> Feedback:
        """Run pytest."""
        try:
            result = await asyncio.create_subprocess_exec(
                "pytest", path, "-v",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode()
            errors = [line for line in output.split('\n') if 'FAILED' in line]
            
            return Feedback(
                tool="pytest",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"tests_failed": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="pytest", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_clippy(self, path: str) -> Feedback:
        """Run clippy."""
        try:
            result = await asyncio.create_subprocess_exec(
                "cargo", "clippy", "--", "-D", "warnings",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode() + stderr.decode()
            errors = [line for line in output.split('\n') if 'error' in line.lower()]
            
            return Feedback(
                tool="clippy",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"clippy_errors": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="clippy", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_cargo_test(self, path: str) -> Feedback:
        """Run cargo test."""
        try:
            result = await asyncio.create_subprocess_exec(
                "cargo", "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode() + stderr.decode()
            errors = [line for line in output.split('\n') if 'FAILED' in line]
            
            return Feedback(
                tool="cargo_test",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"tests_failed": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="cargo_test", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_eslint(self, path: str) -> Feedback:
        """Run eslint."""
        try:
            result = await asyncio.create_subprocess_exec(
                "eslint", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode()
            errors = [line for line in output.split('\n') if 'error' in line.lower()]
            
            return Feedback(
                tool="eslint",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"eslint_errors": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="eslint", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_tsc(self, path: str) -> Feedback:
        """Run TypeScript compiler."""
        try:
            result = await asyncio.create_subprocess_exec(
                "tsc", "--noEmit", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode() + stderr.decode()
            errors = [line for line in output.split('\n') if 'error' in line.lower()]
            
            return Feedback(
                tool="tsc",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"type_errors": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="tsc", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _run_vitest(self, path: str) -> Feedback:
        """Run vitest."""
        try:
            result = await asyncio.create_subprocess_exec(
                "vitest", "run", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            output = stdout.decode()
            errors = [line for line in output.split('\n') if 'FAIL' in line]
            
            return Feedback(
                tool="vitest",
                success=result.returncode == 0,
                output=output,
                errors=errors,
                metrics={"tests_failed": len(errors)},
            )
        except Exception as e:
            return Feedback(tool="vitest", success=False, output=str(e), errors=[str(e)], metrics={})
    
    async def _correct(self, code: str, feedbacks: list[Feedback]) -> str:
        """Self-correct code based on feedback."""
        # Build correction prompt
        error_summary = []
        for f in feedbacks:
            error_summary.append(f"## {f.tool}\n{chr(10).join(f.errors[:5])}")
        
        prompt = f"""Fix the following errors in this code:

```{code}
```

Errors:
{chr(10).join(error_summary)}

Return ONLY the corrected code, no explanation."""
        
        # Call LLM for correction
        api_key = os.getenv("OPENCODE_API_KEY", "")
        base_url = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
        model = os.getenv("LLM_WORKER_MODEL", "mimo-v2.5")
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                corrected = data["choices"][0]["message"]["content"]
                # Extract code block if present
                if "```" in corrected:
                    start = corrected.find("```") + 3
                    end = corrected.rfind("```")
                    corrected = corrected[start:end]
                return corrected.strip()
        
        return code
    
    def get_report(self) -> dict[str, Any]:
        """Get self-correction report."""
        return {
            "total_checks": len(self.feedback_history),
            "passed": sum(1 for f in self.feedback_history if f.success),
            "failed": sum(1 for f in self.feedback_history if not f.success),
            "by_tool": {
                tool: {
                    "total": sum(1 for f in self.feedback_history if f.tool == tool),
                    "passed": sum(1 for f in self.feedback_history if f.tool == tool and f.success),
                }
                for tool in set(f.tool for f in self.feedback_history)
            },
        }
