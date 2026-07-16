"""LLM client — provider-agnostic, OpenAI-compatible API."""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


class LLMResponseError(RuntimeError):
    """The upstream LLM returned a successful but invalid response."""


@dataclass
class ChatResult:
    """Response from a chat completion call with usage tracking."""
    content: str
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"


@dataclass
class LLMConfig:
    """Configuration for LLM API access."""
    api_key: str
    base_url: str
    planner_model: str
    worker_model: str
    critic_model: str
    timeout: float = 180.0
    max_attempts: int = 3

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Load config from environment variables."""
        api_key = os.getenv("OPENCODE_API_KEY", "")
        if not api_key:
            raise ValueError("OPENCODE_API_KEY environment variable is required")

        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1"),
            planner_model=os.getenv("LLM_PLANNER_MODEL", "mimo-v2.5-pro"),
            worker_model=os.getenv("LLM_WORKER_MODEL", "mimo-v2.5"),
            critic_model=os.getenv("LLM_CRITIC_MODEL", "mimo-v2.5"),
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "180")),
            max_attempts=max(1, int(os.getenv("LLM_MAX_ATTEMPTS", "3"))),
        )


_MODEL_ALIASES = {
    "planner": None,   # resolved from config at runtime
    "worker": None,
    "critic": None,
}


class LLMClient:
    """Async LLM client for any OpenAI-compatible endpoint."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def _resolve_model(self, model: str | None) -> str:
        """Resolve model alias to actual model name."""
        if model is None:
            return self.config.planner_model
        if model == "planner":
            return self.config.planner_model
        if model == "worker":
            return self.config.worker_model
        if model == "critic":
            return self.config.critic_model
        return model

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request and return the response text."""
        result = await self.chat_with_usage(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result.content

    async def chat_with_usage(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
    ) -> ChatResult:
        """Send a chat completion request and return full result with usage."""
        resolved_model = self._resolve_model(model)

        body = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            body["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            for attempt in range(self.config.max_attempts):
                try:
                    response = await client.post(
                        f"{self.config.base_url}/chat/completions",
                        json=body,
                        headers=headers,
                    )
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as exc:
                    retryable = exc.response.status_code in {429, 500, 502, 503, 504}
                    if not retryable or attempt + 1 >= self.config.max_attempts:
                        raise
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt + 1 >= self.config.max_attempts:
                        raise
                await asyncio.sleep(min(2**attempt, 4))

        if response is None:
            raise LLMResponseError("The LLM service returned no response")

        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError("The LLM service returned an invalid response") from exc
        # MiMo models may return content in 'reasoning_content' when max_tokens is too low
        content = message.get("content") or message.get("reasoning_content", "")
        if not isinstance(content, str):
            raise LLMResponseError("The LLM service returned non-text content")
        usage = data.get("usage", {})
        raw_finish_reason = choice.get("finish_reason", "stop")
        finish_reason = raw_finish_reason if isinstance(raw_finish_reason, str) else "stop"

        return ChatResult(
            content=content,
            usage=usage,
            model=resolved_model,
            raw=data,
            finish_reason=finish_reason,
        )
