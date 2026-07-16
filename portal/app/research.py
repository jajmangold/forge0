"""Bounded, evidence-first deep research with durable wiki caching."""
from __future__ import annotations

import asyncio
import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from . import gitea
from .frontier import Objective, pareto_front
from .llm_client import LLMClient, LLMConfig
from .search import search_web


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    context: str = Field(default="", max_length=4000)
    owner: str = Field(default="agent", pattern=r"^[A-Za-z0-9_.-]+$")
    repo: str = Field(default="forge0", pattern=r"^[A-Za-z0-9_.-]+$")
    max_queries: int = Field(default=4, ge=2, le=6)
    max_sources: int = Field(default=16, ge=4, le=30)
    refresh: bool = False
    publish_wiki: bool = True


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(topic: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:70]
    return value or "research"


def _cache_key(request: ResearchRequest) -> str:
    material = json.dumps(
        {
            "topic": " ".join(request.topic.lower().split()),
            "context": " ".join(request.context.lower().split()),
            "owner": request.owner,
            "repo": request.repo,
            "max_queries": request.max_queries,
            "max_sources": request.max_sources,
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _public_host(hostname: str) -> bool:
    """Reject URLs that could turn source fetching into SSRF."""
    if not hostname or hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return False
    return bool(addresses)


def _plain_text(document: str) -> str:
    document = re.sub(r"(?is)<(script|style|svg).*?>.*?</\1>", " ", document)
    document = re.sub(r"(?s)<[^>]+>", " ", document)
    return re.sub(r"\s+", " ", html.unescape(document)).strip()


async def _fetch_excerpt(url: str, max_bytes: int = 262_144) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not await asyncio.to_thread(_public_host, parsed.hostname or ""):
        return ""
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
            response = await client.get(url, headers={"User-Agent": "Forge0Research/1.0"})
        if response.is_redirect:
            return ""
        response.raise_for_status()
        if int(response.headers.get("content-length", "0") or 0) > max_bytes:
            return ""
        content_type = response.headers.get("content-type", "")
        if not any(kind in content_type for kind in ("text/", "json", "xml")):
            return ""
        return _plain_text(response.text[:max_bytes])[:3000]
    except (httpx.HTTPError, ValueError):
        return ""


class ResearchService:
    """Execute bounded query plans and reuse/publish their evidence."""

    objectives: list[Objective] = [
        {"name": "relevance", "direction": "maximize"},
        {"name": "authority", "direction": "maximize"},
        {"name": "freshness", "direction": "maximize"},
    ]

    def __init__(self, path: str | Path | None = None):
        data_dir = Path(os.getenv("FORGE0_DATA_DIR", "/var/lib/forge0"))
        self.path = Path(path or data_dir / "research.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS research_cache ("
                "cache_key TEXT PRIMARY KEY, owner TEXT NOT NULL, repo TEXT NOT NULL, "
                "topic TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL, "
                "expires_at TEXT NOT NULL)"
            )

    def cached(self, request: ResearchRequest) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM research_cache WHERE cache_key=? AND expires_at>?",
                (_cache_key(request), _now()),
            ).fetchone()
        if row is None:
            return None
        result = json.loads(row["result_json"])
        result["cache_hit"] = True
        return result

    @staticmethod
    def _queries(request: ResearchRequest) -> list[str]:
        year = datetime.now(UTC).year
        queries = [
            request.topic,
            f"{request.topic} official documentation best practices {year}",
            f"{request.topic} limitations failure modes alternatives",
            f"{request.topic} benchmark evaluation evidence",
            f"{request.topic} security reliability guidance",
            f"{request.topic} recent changes {year}",
        ]
        return queries[: request.max_queries]

    async def run(self, request: ResearchRequest) -> dict[str, Any]:
        if not request.refresh:
            cached = self.cached(request)
            if cached is not None:
                return cached

        started = time.perf_counter()
        queries = self._queries(request)
        batches = await asyncio.gather(*(search_web(query, 10) for query in queries))
        unique: dict[str, dict[str, Any]] = {}
        query_domains: set[str] = set()
        for query_index, batch in enumerate(batches):
            for rank, raw in enumerate(batch):
                url = str(raw.get("url", ""))
                host = (urlsplit(url).hostname or "").lower()
                if not url or not host:
                    continue
                query_domains.add(host)
                score = float(raw.get("score") or 1 / (rank + 1))
                existing = unique.get(url)
                candidate = {
                    "title": str(raw.get("title", ""))[:500],
                    "url": url,
                    "snippet": str(raw.get("content", ""))[:1200],
                    "engine": str(raw.get("engine", "")),
                    "query_index": query_index,
                    "metrics": {
                        "relevance": score,
                        "authority": (
                            1.0
                            if any(part in host for part in ("docs.", "github.com", ".gov", ".edu"))
                            else 0.5
                        ),
                        "freshness": 1.0 if str(datetime.now(UTC).year) in str(raw) else 0.5,
                    },
                    "feasible": True,
                }
                if existing is None or score > existing["metrics"]["relevance"]:
                    unique[url] = candidate

        ranked = sorted(unique.values(), key=lambda item: item["metrics"]["relevance"], reverse=True)
        selected = ranked[: request.max_sources]
        excerpts = await asyncio.gather(*(_fetch_excerpt(item["url"]) for item in selected[:8]))
        for item, excerpt in zip(selected, excerpts, strict=False):
            item["excerpt"] = excerpt

        evidence = "\n\n".join(
            f"SOURCE {index + 1}: {item['title']}\nURL: {item['url']}\n"
            f"EVIDENCE: {(item.get('excerpt') or item['snippet'])[:3000]}"
            for index, item in enumerate(selected)
        )
        prompt = f"""Synthesize a bounded evidence review using only the supplied sources.
Topic: {request.topic}
Context: {request.context or 'General engineering research'}

Requirements:
- Distinguish sourced facts, inference, and unresolved uncertainty.
- Cite claims inline as markdown links to the supplied URLs.
- Prefer primary sources and call out conflicting evidence.
- End with concrete recommendations and a short verification plan.
- Do not invent citations or claim that snippets were full documents.

{evidence}
"""
        synthesis = await LLMClient(LLMConfig.from_env()).chat(
            messages=[{"role": "user", "content": prompt}],
            model="worker",
            temperature=0.2,
            max_tokens=6000,
        )
        elapsed = time.perf_counter() - started
        created_at = _now()
        result: dict[str, Any] = {
            "topic": request.topic,
            "context": request.context,
            "model": LLMConfig.from_env().worker_model,
            "created_at": created_at,
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "cache_hit": False,
            "queries": queries,
            "sources": selected,
            "source_frontier": pareto_front(selected, self.objectives),
            "metrics": {
                "elapsed_seconds": round(elapsed, 3),
                "unique_sources": len(unique),
                "unique_domains": len(query_domains),
                "selected_sources": len(selected),
                "fetched_excerpts": sum(bool(item.get("excerpt")) for item in selected),
            },
            "synthesis": synthesis,
        }
        if request.publish_wiki:
            title = f"Research-{_slug(request.topic)}"
            frontmatter = (
                "---\n"
                f"researched: {created_at}\n"
                f"refresh_after: {result['expires_at']}\n"
                f"model: {result['model']}\n"
                f"source_count: {len(selected)}\n"
                "---\n\n"
            )
            page = await gitea.upsert_wiki_page(
                request.owner,
                request.repo,
                title,
                frontmatter + synthesis + "\n",
            )
            result["wiki"] = {"title": title, "url": page.get("html_url", "")}

        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO research_cache VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _cache_key(request), request.owner, request.repo, request.topic,
                    json.dumps(result, sort_keys=True), created_at, result["expires_at"],
                ),
            )
        return result
