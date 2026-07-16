"""Chat with project - conversational interface to any repo."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

router = APIRouter()

GITEA_INTERNAL = os.getenv("GITEA_URL", "http://gitea:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")


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
    history: list[dict]
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
When referencing issues, use: #{issue_number}
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})
    
    # Call LLM
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
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4096,
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return f"Error: {response.status_code} - {response.text}"


@router.get("/repo/{owner}/{name:path}/chat", response_class=HTMLResponse)
async def chat_page(request: Request, owner: str, name: str):
    """Chat page for a project."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "owner": owner,
        "repo": name,
    })


@router.post("/api/chat/{owner}/{repo}")
async def chat_message(owner: str, repo: str, body: dict):
    """Handle chat message."""
    query = body.get("query", "")
    history = body.get("history", [])
    
    response = await stream_chat_response(owner, repo, query, history)
    
    return {"response": response}
