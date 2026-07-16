"""Chat with project - conversational interface to any repo."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .llm_client import LLMClient, LLMConfig, LLMResponseError

router = APIRouter()

GITEA_INTERNAL = os.getenv("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")


class ChatMessage(BaseModel):
    """Validated project-chat request."""

    query: str = Field(min_length=1, max_length=8_000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=40)


async def load_project_context(owner: str, repo: str, query: str) -> str:
    """Load relevant context from Gitea based on the query."""
    context_parts = []
    
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        headers = {"Authorization": f"token {GITEA_TOKEN}"}
        
        # 1. Load README
        try:
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{owner}/{repo}/readme",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", "")
                if content:
                    import base64
                    readme = base64.b64decode(content).decode("utf-8", errors="replace")
                    context_parts.append(f"## README\n{readme[:3000]}")
        except Exception:
            pass
        
        # 2. Load repo structure
        try:
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{owner}/{repo}/git/trees/HEAD?recursive=true",
                headers=headers
            )
            if resp.status_code == 200:
                tree = resp.json().get("tree", [])
                files = [t["path"] for t in tree if t["type"] == "blob"]
                # Filter to relevant files based on query
                context_parts.append(f"## File Structure\n{chr(10).join(files[:100])}")
        except Exception:
            pass
        
        # 3. Load open issues
        try:
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{owner}/{repo}/issues?state=open&limit=10",
                headers=headers
            )
            if resp.status_code == 200:
                issues = resp.json()
                if issues:
                    issue_list = "\n".join([
                        f"- #{i['number']}: {i['title']}" 
                        for i in issues
                    ])
                    context_parts.append(f"## Open Issues\n{issue_list}")
        except Exception:
            pass
        
        # 4. Load recent commits
        try:
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{owner}/{repo}/commits?limit=10",
                headers=headers
            )
            if resp.status_code == 200:
                commits = resp.json()
                if commits:
                    commit_list = "\n".join([
                        f"- {c['sha'][:7]}: {c['commit']['message'].split(chr(10))[0]}"
                        for c in commits
                    ])
                    context_parts.append(f"## Recent Commits\n{commit_list}")
        except Exception:
            pass
        
        # 5. Try to load files mentioned in query
        query_lower = query.lower()
        for file_path in ["README.md", "requirements.txt", "pyproject.toml", 
                          "Cargo.toml", "package.json", "Dockerfile"]:
            if any(keyword in query_lower for keyword in file_path.lower().split(".")):
                try:
                    resp = await client.get(
                        f"{GITEA_INTERNAL}/api/v1/repos/{owner}/{repo}/contents/{file_path}",
                        headers=headers
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("content", "")
                        if content:
                            import base64
                            file_content = base64.b64decode(content).decode("utf-8", errors="replace")
                            context_parts.append(f"## {file_path}\n{file_content[:2000]}")
                except Exception:
                    pass
        
        # 6. Load wiki if it exists
        try:
            resp = await client.get(
                f"{GITEA_INTERNAL}/api/v1/repos/{owner}/{repo}/wiki/pages",
                headers=headers
            )
            if resp.status_code == 200:
                pages = resp.json()
                if pages:
                    wiki_summary = "\n".join([f"- {p['title']}" for p in pages[:10]])
                    context_parts.append(f"## Wiki Pages\n{wiki_summary}")
        except Exception:
            pass
    
    return "\n\n".join(context_parts) if context_parts else "No context found."


async def stream_chat_response(
    owner: str, 
    repo: str, 
    query: str, 
    history: list[dict[str, str]],
) -> str:
    """Stream chat response from LLM."""
    # Load project context
    context = await load_project_context(owner, repo, query)
    
    # Build messages
    system_prompt = f"""You are a helpful assistant for the project {owner}/{repo}.

Project Context:
{context}

Answer questions about this project. Be concise and helpful.
When referencing files, use the format: `path/to/file.py`
When referencing issues, use the format: #123
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})
    
    client = LLMClient(LLMConfig.from_env())
    return await client.chat(
        messages=messages,
        model="worker",
        temperature=0.3,
        max_tokens=4096,
    )


@router.get("/repo/{owner}/{name:path}/chat", response_class=HTMLResponse)
async def chat_page(request: Request, owner: str, name: str):
    """Chat page for a project."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    
    return templates.TemplateResponse(request, "chat.html", {
        "owner": owner,
        "repo": name,
    })


@router.post("/api/chat/{owner}/{repo}")
async def chat_message(owner: str, repo: str, body: ChatMessage) -> dict[str, str]:
    """Handle chat message."""
    history: list[dict[str, str]] = []
    for item in body.history:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            history.append({"role": role, "content": content[:8_000]})

    try:
        response = await stream_chat_response(owner, repo, body.query.strip(), history)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="The configured LLM service is unavailable") from exc

    return {"response": response}
