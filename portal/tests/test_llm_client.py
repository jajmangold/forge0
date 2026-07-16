"""Tests for the LLM client — written BEFORE implementation (TDD)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLLMClientConfig:
    """Test LLM client configuration loading."""

    def test_reads_config_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key-123")
        monkeypatch.setenv("OPENCODE_BASE_URL", "https://test.api/v1")
        monkeypatch.setenv("LLM_PLANNER_MODEL", "test-planner")
        monkeypatch.setenv("LLM_WORKER_MODEL", "test-worker")

        from app.llm_client import LLMConfig

        config = LLMConfig.from_env()
        assert config.api_key == "test-key-123"
        assert config.base_url == "https://test.api/v1"
        assert config.planner_model == "test-planner"
        assert config.worker_model == "test-worker"

    def test_default_base_url(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
        monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)

        from app.llm_client import LLMConfig

        config = LLMConfig.from_env()
        assert "opencode.ai" in config.base_url

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)

        from app.llm_client import LLMConfig

        with pytest.raises(ValueError, match="OPENCODE_API_KEY"):
            LLMConfig.from_env()


class TestLLMClientChatCompletion:
    """Test chat completion calls."""

    @pytest.fixture
    def config(self):
        from app.llm_client import LLMConfig
        return LLMConfig(
            api_key="test-key",
            base_url="https://test.api/v1",
            planner_model="test-planner",
            worker_model="test-worker",
            critic_model="test-critic",
        )

    @pytest.mark.asyncio
    async def test_sends_correct_request_format(self, config):
        from app.llm_client import LLMClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mock_response.raise_for_status = MagicMock()

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="test-model",
            )

        assert result == "Hello!"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/chat/completions" in call_args[0][0]
        body = call_args[1]["json"]
        assert body["model"] == "test-model"
        assert body["messages"][0]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_uses_planner_model_by_default(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "result"}}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await client.chat(messages=[{"role": "user", "content": "test"}])

        body = mock_client.post.call_args[1]["json"]
        assert body["model"] == "test-planner"

    @pytest.mark.asyncio
    async def test_worker_model_alias(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "result"}}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await client.chat(
                messages=[{"role": "user", "content": "test"}],
                model="worker",
            )

        body = mock_client.post.call_args[1]["json"]
        assert body["model"] == "test-worker"

    @pytest.mark.asyncio
    async def test_raises_on_api_error(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = RuntimeError("500")
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="500"):
                await client.chat(messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_retries_a_transient_timeout(self, config):
        import httpx
        from app.llm_client import LLMClient

        config.max_attempts = 2
        client = LLMClient(config)
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "recovered"}}]}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("app.llm_client.httpx.AsyncClient") as mock_cls,
            patch("app.llm_client.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[httpx.ReadTimeout("slow"), mock_response])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat(messages=[{"role": "user", "content": "test"}])

        assert result == "recovered"
        assert mock_client.post.await_count == 2
        sleep.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_includes_auth_header(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "ok"}}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await client.chat(messages=[{"role": "user", "content": "test"}])

        headers = mock_client.post.call_args[1]["headers"]
        assert "test-key" in headers["Authorization"]

    @pytest.mark.asyncio
    async def test_temperature_and_max_tokens_passed(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "ok"}}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await client.chat(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=1024,
            )

        body = mock_client.post.call_args[1]["json"]
        assert body["temperature"] == 0.3
        assert body["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_rejects_malformed_success_response(self, config):
        from app.llm_client import LLMClient, LLMResponseError

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"choices": []}
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(LLMResponseError, match="invalid response"):
                await client.chat(messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_finish_reason_captured_from_response(self, config):
        """Test that finish_reason is captured from the provider response."""
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {"content": "truncated response"},
                        "finish_reason": "length",
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat_with_usage(
                messages=[{"role": "user", "content": "test"}]
            )

        assert result.finish_reason == "length"
        assert result.content == "truncated response"

    @pytest.mark.asyncio
    async def test_finish_reason_defaults_to_stop(self, config):
        """Test that finish_reason defaults to 'stop' for backwards compatibility."""
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {"content": "complete response"},
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat_with_usage(
                messages=[{"role": "user", "content": "test"}]
            )

        assert result.finish_reason == "stop"
        assert result.content == "complete response"

    @pytest.mark.asyncio
    async def test_non_string_finish_reason_defaults_to_stop(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "complete"}, "finish_reason": None}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat_with_usage(messages=[{"role": "user", "content": "test"}])

        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_finish_reason_stop_normal_response(self, config):
        """Test that finish_reason is 'stop' for normal completion."""
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {"content": "normal response"},
                        "finish_reason": "stop",
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat_with_usage(
                messages=[{"role": "user", "content": "test"}]
            )

        assert result.finish_reason == "stop"
        assert result.content == "normal response"


class TestLLMClientCostTracking:
    """Test cost tracking per call."""

    @pytest.fixture
    def config(self):
        from app.llm_client import LLMConfig
        return LLMConfig(
            api_key="test-key",
            base_url="https://test.api/v1",
            planner_model="test-planner",
            worker_model="test-worker",
            critic_model="test-critic",
        )

    @pytest.mark.asyncio
    async def test_tracks_usage_in_response(self, config):
        from app.llm_client import LLMClient

        client = LLMClient(config)

        with patch("app.llm_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await client.chat_with_usage(
                messages=[{"role": "user", "content": "test"}]
            )

        assert result.content == "ok"
        assert result.usage["prompt_tokens"] == 100
        assert result.usage["completion_tokens"] == 50
