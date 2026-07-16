# LLM Integration Strategy

How Forge0 connects to language models. Works with any OpenAI-compatible endpoint.

## Design Principle

**Provider-agnostic.** Forge0 should work with any LLM that speaks the OpenAI chat completions API. No vendor lock-in.

## Supported Backends

| Backend | Endpoint | Use Case |
|---|---|---|
| OpenCode Go | `https://opencode.ai/zen/go/v1/chat/completions` | Cheap access to open coding models ($10/mo) |
| Ollama | `http://localhost:11434/v1` | Local models, zero cost, full privacy |
| vLLM | `http://localhost:8000/v1` | Self-hosted, high throughput |
| OpenAI | `https://api.openai.com/v1` | GPT-4o, o1, etc. |
| LiteLLM | `http://localhost:4000/v1` | Proxy to any provider |
| Any compatible | User-configured | Anything with `/v1/chat/completions` |

## Configuration

Environment variables (set in docker-compose or `.env`):

```bash
# OpenCode Go provider
OPENCODE_API_KEY=your-key-here
OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1

# Model assignments
LLM_PLANNER_MODEL=mimo-v2.5-pro    # Planning, requirements, architecture, decomposition
LLM_WORKER_MODEL=mimo-v2.5         # Implementation, code generation, tests
LLM_CRITIC_MODEL=mimo-v2.5         # Evaluation, pass/fail judgment
```

### Model Assignment Rationale

| Role | Model | Why |
|---|---|---|
| **Planner** (requirements, architecture, decomposition) | `mimo-v2.5-pro` | Higher quality reasoning for decisions that affect the whole project |
| **Worker** (implementation, code gen, tests) | `mimo-v2.5` | Fast, cheap, good enough for code generation with clear specs |
| **Critic** (evaluation, review) | `mimo-v2.5` | Simple pass/fail judgment, doesn't need the pro model |

The planner model costs ~$1.74/1M input tokens (pro) vs $0.14/1M (base). Using pro only for planning decisions keeps costs low while maintaining quality where it matters.

## OpenCode Go Models (recommended for cost)

From the OpenCode docs, these models are available:

| Model ID | Best For | Cost (input/output per 1M tokens) |
|---|---|---|
| `kimi-k2.7-code` | Code generation | $0.95 / $4.00 |
| `deepseek-v4-flash` | Fast tasks, evaluations | $0.14 / $0.28 |
| `deepseek-v4-pro` | Complex reasoning | $1.74 / $3.48 |
| `mimo-v2.5` | Ultra-cheap bulk work | $0.14 / $0.28 |
| `qwen3.7-plus` | Balanced | $0.40 / $1.60 |

**Strategy:** Use cheap models (deepseek-v4-flash, mimo-v2.5) for evaluations and simple tasks. Use capable models (kimi-k2.7-code, deepseek-v4-pro) for complex code generation and architecture.

## API Client

Simple Python client using `httpx`. No SDK dependency.

```python
# Pattern (not actual code yet)
async def chat_completion(
    messages: list[dict],
    model: str = None,
    base_url: str = None,
    api_key: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Call any OpenAI-compatible chat completions endpoint."""
    base_url = base_url or LLM_BASE_URL
    model = model or LLM_MODEL
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
```

## Agent Architecture

Each agent type has:
1. A **system prompt** defining its role and constraints
2. A **tool set** (functions it can call)
3. An **evaluation criteria** (what "good" looks like)

### Agent Types

| Agent | Model Tier | Purpose |
|---|---|---|
| Requirements | Capable | Structured elicitation, synthesis |
| Architecture | Capable | Tech stack decisions, patterns |
| Planner | Capable | Task decomposition, dependency analysis |
| Implementer | Capable | Code generation, testing |
| Critic | Cheap | Evaluation, pass/fail judgment |
| Knowledge | Cheap | Q&A against project context |
| Research | Capable (synthesis) + Cheap (monitoring) | Web research, dependency/security monitoring |

### Research Agent Tools

The Research Agent uses two external systems:

**SearXNG** — self-hosted metasearch engine (aggregates Google, DuckDuckGo, GitHub, StackOverflow, MDN, PyPI, npm, arXiv):
```
http://searxng:8080/search?q={query}&format=json
```
Used for: best practices, comparisons, tutorials, package research, security advisories.

**Context7** — library/framework documentation lookup (MCP server):
```
resolve-library-id → query-docs
```
Used for: API references, configuration syntax, code examples, usage patterns.

See `research-agents.md` for full details on when to use each tool.

### Conversation Memory

Each agent conversation maintains a message history. For the requirements agent, this is the full chat with the user. For implementation agents, it's the task context + code history.

Memory is stored per-project in `.forge0/conversations/` so agents can resume after restarts.

## Evaluation Pattern

Every agent output goes through evaluation:

1. **Deterministic checks** (fast, reliable):
   - Required sections present in output
   - YAML frontmatter valid
   - Code compiles/lints
   - Tests pass

2. **Critic agent** (judgment calls):
   - "Are these acceptance criteria testable?"
   - "Does this code match the task spec?"
   - "Are there obvious security issues?"

The critic uses a cheaper model (deepseek-v4-flash) since it's doing simpler work.

Evaluation returns structured output:
```json
{
  "pass": true/false,
  "checks": {
    "frontmatter_valid": true,
    "required_sections": true,
    "criteria_testable": false
  },
  "feedback": "Acceptance criteria #3 is ambiguous — 'fast' needs a numeric threshold"
}
```

If evaluation fails, the producing agent retries (up to 3 attempts). If all attempts fail, the workflow escalates to the user.

## Privacy & Security

- API keys are never logged or committed to repos
- All LLM calls go through the server (portal backend), not the browser
- User conversations are stored in the project repo (encrypted at rest if needed)
- Local models (Ollama) can be used for fully private operation
- OpenCode Go providers follow zero-retention policy (per their docs)

## Cost Estimation

For a typical greenfield project:

| Phase | Estimated Tokens | Estimated Cost (OpenCode Go) |
|---|---|---|
| Requirements | ~50K in, ~10K out | ~$0.05 |
| Architecture | ~30K in, ~5K out | ~$0.03 |
| Task Decomposition | ~20K in, ~5K out | ~$0.02 |
| Implementation (per task) | ~40K in, ~10K out | ~$0.06 |
| Evaluation (per task) | ~10K in, ~2K out | ~$0.01 |
| **Total (5-task project)** | **~300K in, ~70K out** | **~$0.35** |

Using deepseek-v4-flash for evaluations brings this down further.
