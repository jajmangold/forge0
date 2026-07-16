"""Tests for agent base class — written BEFORE implementation (TDD)."""
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestAgentBase:
    """Test the base agent class."""

    def test_agent_has_role(self):
        """Each agent has a role name."""
        from app.agents import Agent

        class TestAgent(Agent):
            role = "test"

            async def execute(self, **kwargs):
                pass

        agent = TestAgent(llm=MagicMock())
        assert agent.role == "test"

    def test_agent_requires_llm(self):
        """Agent cannot be created without an LLM client."""
        from app.agents import Agent

        class TestAgent(Agent):
            role = "test"

        with pytest.raises(TypeError):
            TestAgent()

    @pytest.mark.asyncio
    async def test_agent_run_calls_execute(self):
        """run() delegates to execute() which subclasses implement."""
        from app.agents import Agent

        class TestAgent(Agent):
            role = "test"
            execute = AsyncMock(return_value="result")

        mock_llm = MagicMock()
        agent = TestAgent(llm=mock_llm)
        result = await agent.run(context="some context")

        assert result == "result"
        agent.execute.assert_called_once_with(context="some context")

    @pytest.mark.asyncio
    async def test_agent_run_handles_error(self):
        """run() catches exceptions and returns error result."""
        from app.agents import Agent

        class TestAgent(Agent):
            role = "test"

            async def execute(self, **kwargs):
                raise RuntimeError("something broke")

        mock_llm = MagicMock()
        agent = TestAgent(llm=mock_llm)
        result = await agent.run(context="test")

        assert result.success is False
        assert "something broke" in result.error


class TestResearchAgent:
    """Test the research agent."""

    @pytest.mark.asyncio
    async def test_research_calls_searxng(self):
        """Research agent searches SearXNG for web results."""
        from app.agents import ResearchAgent

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="synthesized findings")

        mock_search = AsyncMock(return_value=[
            {"title": "Test", "url": "http://test.com", "content": "result"}
        ])

        agent = ResearchAgent(llm=mock_llm, search_fn=mock_search)
        await agent.execute(topic="payment systems", context="SaaS app")

        mock_search.assert_called_once()
        assert "payment" in mock_search.call_args[0][0].lower() or \
               "payment" in str(mock_search.call_args).lower()

    @pytest.mark.asyncio
    async def test_research_synthesizes_findings(self):
        """Research agent uses LLM to synthesize search results."""
        from app.agents import ResearchAgent

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="Stripe is recommended because...")

        mock_search = AsyncMock(return_value=[
            {"title": "Stripe Docs", "url": "http://stripe.com", "content": "Payment API"}
        ])

        agent = ResearchAgent(llm=mock_llm, search_fn=mock_search)
        result = await agent.execute(topic="payment systems")

        mock_llm.chat.assert_called_once()
        assert "Stripe" in result.output

    @pytest.mark.asyncio
    async def test_research_returns_structured_result(self):
        """Research agent returns a structured result with sources."""
        from app.agents import ResearchAgent

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="Findings here")

        mock_search = AsyncMock(return_value=[
            {"title": "Source 1", "url": "http://a.com", "content": "content"},
            {"title": "Source 2", "url": "http://b.com", "content": "content"},
        ])

        agent = ResearchAgent(llm=mock_llm, search_fn=mock_search)
        result = await agent.execute(topic="test topic")

        assert hasattr(result, "output")
        assert hasattr(result, "sources")
        assert len(result.sources) == 2


class TestCriticAgent:
    """Test the critic agent."""

    @pytest.mark.asyncio
    async def test_critic_evaluates_artifact(self):
        """Critic agent evaluates an artifact and returns pass/fail."""
        from app.agents import CriticAgent

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value='{"pass": true, "feedback": "Looks good"}')

        agent = CriticAgent(llm=mock_llm)
        result = await agent.evaluate(
            artifact="# Requirement\n\n## Description\nTest project",
            criteria=["has_description", "has_acceptance_criteria"],
        )

        assert result.passed is True
        assert "good" in result.feedback.lower()

    @pytest.mark.asyncio
    async def test_critic_returns_fail_with_feedback(self):
        """Critic returns fail with specific feedback when artifact is bad."""
        from app.agents import CriticAgent

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value='{"pass": false, "feedback": "Missing acceptance criteria"}')

        agent = CriticAgent(llm=mock_llm)
        result = await agent.evaluate(
            artifact="# Requirement\n\nJust do stuff",
            criteria=["has_acceptance_criteria"],
        )

        assert result.passed is False
        assert "criteria" in result.feedback.lower()
