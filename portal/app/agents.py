"""Agent base class and concrete agent implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .llm_client import LLMClient


@dataclass
class AgentResult:
    """Result from an agent execution."""
    success: bool = True
    output: str = ""
    error: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CriticResult:
    """Result from a critic evaluation."""
    passed: bool = False
    feedback: str = ""
    checks: dict[str, bool] = field(default_factory=dict)


class Agent(ABC):
    """Base class for all agents.
    Every agent has a role, an LLM client, and an execute method."""

    role: str = ""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def run(self, **kwargs) -> AgentResult:
        """Run the agent. Delegates to execute(). Catches errors."""
        try:
            return await self.execute(**kwargs)
        except Exception as e:
            return AgentResult(success=False, error=str(e))

    @abstractmethod
    async def execute(self, **kwargs) -> AgentResult:
        """Execute the agent's task. Subclasses implement this."""
        ...


class ResearchAgent(Agent):
    """Research agent — searches the web via SearXNG and synthesizes findings."""

    role = "research"

    def __init__(self, llm: LLMClient, search_fn=None):
        super().__init__(llm)
        self.search_fn = search_fn

    async def execute(self, topic: str, context: str = "", **kwargs) -> AgentResult:
        """Research a topic by searching the web and synthesizing results."""
        # Search
        query = f"{topic} best practices comparison 2025 2026"
        results = []
        if self.search_fn:
            results = await self.search_fn(query)

        # Format search results for LLM
        search_text = "\n".join(
            f"- {r.get('title', '?')}: {r.get('content', '')[:200]}"
            for r in results[:10]
        )

        # Synthesize with LLM
        prompt = f"""You are a research agent. Synthesize these search results into findings.

Topic: {topic}
Context: {context or 'General research'}

Search results:
{search_text or 'No results found.'}

Provide:
1. Key findings (bullet points)
2. Recommendations
3. Sources used"""

        synthesis = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model="planner",
        )

        return AgentResult(
            success=True,
            output=synthesis,
            sources=[
                {"title": r.get("title", ""), "url": r.get("url", "")}
                for r in results[:10]
            ],
        )


class CriticAgent(Agent):
    """Critic agent — evaluates artifacts against criteria."""

    role = "critic"

    async def execute(self, artifact: str, criteria: list[str], **kwargs) -> AgentResult:
        """Not used directly — use evaluate() instead."""
        result = await self.evaluate(artifact=artifact, criteria=criteria)
        return AgentResult(
            success=result.passed,
            output=result.feedback,
        )

    async def evaluate(self, artifact: str, criteria: list[str]) -> CriticResult:
        """Evaluate an artifact against a list of criteria."""
        criteria_text = "\n".join(f"- {c}" for c in criteria)

        prompt = f"""You are a critic agent. Evaluate this artifact against the criteria.

Artifact:
{artifact[:3000]}

Criteria:
{criteria_text}

Respond with ONLY a JSON object:
{{"pass": true/false, "feedback": "explanation"}}"""

        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model="critic",
            temperature=0.1,
        )

        # Parse JSON response
        import json
        try:
            data = json.loads(response.strip().strip("`").strip("json"))
            return CriticResult(
                passed=data.get("pass", False),
                feedback=data.get("feedback", ""),
            )
        except (json.JSONDecodeError, KeyError):
            # If parsing fails, treat as fail with raw response
            return CriticResult(
                passed=False,
                feedback=response,
            )


class RequirementsAgent(Agent):
    """Requirements agent — conducts structured elicitation."""

    role = "requirements"

    async def execute(self, user_request: str, context: str = "", **kwargs) -> AgentResult:
        """Generate structured requirements from a user request."""
        prompt = f"""You are a requirements agent. Generate a structured requirement specification.

User request: {user_request}
Context: {context or 'New project'}

Generate a requirement.md with YAML frontmatter and markdown body.
Include: description, users, MVP features with acceptance criteria, non-goals, constraints.

Respond with ONLY the requirement.md content."""

        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model="planner",
        )

        return AgentResult(success=True, output=response)


class ArchitectureAgent(Agent):
    """Architecture agent — proposes tech stack and patterns."""

    role = "architecture"

    async def execute(self, requirement: str, **kwargs) -> AgentResult:
        """Propose architecture based on requirements."""
        prompt = f"""You are an architecture agent. Propose technical decisions for this project.

Requirement:
{requirement[:2000]}

Generate an architecture.md with:
1. Tech stack (framework, database, hosting)
2. Project structure
3. Patterns (auth, API design, state management)
4. Rationale for each choice

Respond with ONLY the architecture.md content."""

        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model="planner",
        )

        return AgentResult(success=True, output=response)
