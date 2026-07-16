"""SearXNG search client for the research agent."""
from __future__ import annotations

import os
from typing import Any

import httpx

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")


async def search(
    query: str,
    engines: str | None = None,
    categories: str | None = None,
    language: str = "en",
    page: int = 1,
    time_range: str | None = None,
) -> list[dict[str, Any]]:
    """Search SearXNG and return results.

    Args:
        query: Search query string
        engines: Comma-separated engine names (e.g. "google,duckduckgo,github")
        categories: Comma-separated categories (e.g. "general,it,science")
        language: Language code (default: "en")
        page: Result page number
        time_range: Time range filter (day, week, month, year)

    Returns:
        List of result dicts with keys: title, url, content, engine, score
    """
    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "language": language,
        "pageno": page,
    }
    if engines:
        params["engines"] = engines
    if categories:
        params["categories"] = categories
    if time_range:
        params["time_range"] = time_range

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{SEARXNG_URL}/search",
            params=params,
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        r.raise_for_status()
        data = r.json()

    return data.get("results", [])


async def search_web(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """General web search."""
    results = await search(query, categories="general")
    return results[:num_results]


async def search_code(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search code repositories (GitHub, StackOverflow, etc.)."""
    results = await search(query, engines="github,stackoverflow,gitlab")
    return results[:num_results]


async def search_docs(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search documentation sites (MDN, ArchWiki, etc.)."""
    results = await search(query, engines="mdn,archwiki,wikipedia")
    return results[:num_results]


async def search_packages(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search package registries (PyPI, npm, DockerHub)."""
    results = await search(query, engines="pypi,npm,docker_hub")
    return results[:num_results]


async def search_academic(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search academic sources (arXiv, Google Scholar)."""
    results = await search(query, categories="science")
    return results[:num_results]


async def deep_research(
    topic: str,
    context: str = "",
    num_rounds: int = 3,
) -> dict[str, Any]:
    """Multi-round deep research on a topic.

    Performs multiple search queries to build comprehensive understanding.
    Returns structured findings suitable for wiki storage.

    Args:
        topic: Research topic (e.g. "payment integration for Node.js SaaS")
        context: Additional context about why this research is needed
        num_rounds: Number of search rounds (each round = different angle)

    Returns:
        Dict with keys: topic, queries, results_by_query, raw_results
    """
    all_results: dict[str, list[dict]] = {}
    queries_used: list[str] = []

    # Round 1: Direct topic search
    q1 = topic
    all_results[q1] = await search_web(q1, num_results=15)
    queries_used.append(q1)

    # Round 2: Best practices / comparison
    if num_rounds >= 2:
        q2 = f"{topic} best practices comparison 2025 2026"
        all_results[q2] = await search_web(q2, num_results=10)
        queries_used.append(q2)

    # Round 3: Problems / alternatives
    if num_rounds >= 3:
        q3 = f"{topic} alternatives pros cons"
        all_results[q3] = await search_web(q3, num_results=10)
        queries_used.append(q3)

    # Round 4: Code examples (if relevant)
    if num_rounds >= 4:
        q4 = f"{topic} example implementation tutorial"
        all_results[q4] = await search_code(q4, num_results=10)
        queries_used.append(q4)

    # Collect all unique results
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for results in all_results.values():
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

    # Sort by relevance score
    unique_results.sort(key=lambda r: r.get("score", 0), reverse=True)

    return {
        "topic": topic,
        "context": context,
        "queries": queries_used,
        "results_by_query": {q: len(r) for q, r in all_results.items()},
        "total_results": len(unique_results),
        "top_results": unique_results[:20],
    }
