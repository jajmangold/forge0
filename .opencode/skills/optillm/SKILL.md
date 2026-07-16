---
name: optillm
description: OpenAI API-compatible optimizing inference proxy — 20+ techniques to improve LLM accuracy on reasoning, coding, and math tasks without training
license: Apache-2.0
compatibility: opencode
metadata:
  audience: developers
  workflow: inference
  source: https://github.com/algorithmicsuperintelligence/optillm
---

## What I do

OptiLLM is an OpenAI API-compatible optimizing inference proxy that implements 20+ state-of-the-art techniques to dramatically improve LLM accuracy on reasoning tasks — without requiring any model training or fine-tuning.

Use it to:
- **Improve reasoning accuracy** — 2-10x better accuracy on math, coding, logical reasoning
- **Optimize code generation** — better solutions from the same base model
- **Add MCP tools** — connect to external tools and data sources
- **Enable memory** — unbounded context length with file-backed persistence
- **Privacy protection** — anonymize PII in requests/responses

## When to use me

- LLM outputs need higher accuracy on reasoning tasks
- You want to improve code quality without retraining
- Need to connect LLMs to external tools (MCP)
- Require unbounded context with memory
- Need PII protection in LLM interactions

## Installation

```bash
pip install optillm
```

## Quick Start

```bash
# Start the proxy server
export OPENAI_API_KEY="your-key-here"
optillm

# Use with any OpenAI client - just change model name
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1")

# Add prefix for optimization technique
response = client.chat.completions.create(
    model="moa-gpt-4o-mini",  # Mixture of Agents
    messages=[{"role": "user", "content": "Solve: 2x + 3 = 7"}]
)
```

## Optimization Techniques

### Reasoning Enhancement

| Technique | Slug | Description |
|-----------|------|-------------|
| MARS | `mars` | Multi-agent reasoning with diverse exploration |
| CePO | `cepo` | Planning + self-reflection + self-improvement |
| CoT Reflection | `cot_reflection` | Chain-of-thought with thinking/reflection/output |
| PlanSearch | `plansearch` | Search over candidate plans |
| ReRead | `re2` | Process queries twice for better reasoning |
| Self-Consistency | `self_consistency` | Advanced self-consistency method |
| Z3 Solver | `z3` | Theorem prover for logical reasoning |
| R* Algorithm | `rstar` | Problem-solving with rollouts |
| LEAP | `leap` | Learn task-specific principles from examples |

### Sampling & Selection

| Technique | Slug | Description |
|-----------|------|-------------|
| Best of N | `bon` | Generate N responses, select best |
| Mixture of Agents | `moa` | Combine multiple critique responses |
| MCTS | `mcts` | Monte Carlo Tree Search for decisions |
| PV Game | `pvg` | Prover-verifier game approach |

### Decoding

| Technique | Slug | Description |
|-----------|------|-------------|
| CoT Decoding | N/A | Elicit reasoning without explicit prompting |
| Entropy Decoding | N/A | Adaptive sampling based on uncertainty |
| Thinkdeeper | N/A | Reasoning effort parameter for reasoning models |
| AutoThink | N/A | Query complexity + steering vectors |

## Plugins

| Plugin | Slug | Description |
|--------|------|-------------|
| System Prompt Learning | `spl` | Learn problem-solving strategies |
| Deep Think | `deepthink` | Gemini-like Deep Think approach |
| Long-Context CePO | `longcepo` | Divide-and-conquer for infinite context |
| Majority Voting | `majority_voting` | Select most frequent answer |
| MCP Client | `mcp` | Connect to MCP servers |
| Router | `router` | Route requests to different approaches |
| Chain-of-Code | `coc` | CoT + code execution + simulation |
| Memory | `memory` | Unbounded context with persistence |
| Privacy | `privacy` | Anonymize PII data |
| Read URLs | `readurls` | Fetch URL content into context |
| Execute Code | `executecode` | Python code interpreter |
| JSON | `json` | Structured outputs with Pydantic |
| GenSelect | `genselect` | Generate and select best candidates |
| Web Search | `web_search` | Google search via Chrome automation |
| Deep Research | `deep_research` | Comprehensive research reports |
| Proxy | `proxy` | Load balancing across providers |

## Usage Patterns

### Prefix Model Name

```python
# Add technique prefix to model name
response = client.chat.completions.create(
    model="moa-gpt-4o",           # Mixture of Agents
    messages=[...]
)

response = client.chat.completions.create(
    model="bon-gpt-4o",           # Best of N
    messages=[...]
)

response = client.chat.completions.create(
    model="mars-gemini/gemini-2.5-pro",  # MARS with Gemini
    messages=[...]
)
```

### Use extra_body

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    extra_body={"optillm_approach": "moa"}
)
```

### Use Prompt Tags

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{
        "role": "user",
        "content": "<optillm_approach>re2</optillm_approach> How many r's in strawberry?"
    }]
)
```

### Combine Techniques

```python
# Pipeline: A then B (sequential)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    extra_body={"optillm_approach": "cot_reflection&re2"}
)

# Parallel: A and B simultaneously (multiple responses)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    extra_body={"optillm_approach": "moa|bon"}
)
```

## MCP Integration

### Configuration

```json
// ~/.optillm/mcp_config.json
{
  "mcpServers": {
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "description": "Local filesystem access"
    },
    "github": {
      "transport": "sse",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_TOKEN}"
      },
      "description": "GitHub repository management"
    }
  }
}
```

### Available MCP Servers

- **Filesystem**: File operations
- **Git**: Repository operations
- **SQLite**: Database access
- **Brave Search**: Web search
- **GitHub**: Repository/issue management

## Forge0 Integration

### As OpenCode Provider

```json
// opencode.json
{
  "provider": {
    "optillm": {
      "type": "openai",
      "base_url": "http://optillm:8000/v1",
      "api_key": "${OPTILLM_API_KEY}"
    }
  },
  "agent": {
    "build": {
      "model": "optillm/moa-mimo-v2.5",
      "description": "Coding agent with Mixture of Agents optimization"
    },
    "plan": {
      "model": "optillm/cepo-mimo-v2.5-pro",
      "description": "Planning agent with CePO optimization"
    }
  }
}
```

### As OpenEvolve Backend

```python
# config.yaml for OpenEvolve
llm:
  api_base: "http://optillm:8000/v1"
  model: "moa-gemini-2.5-pro"  # Use OptiLLM optimization
```

### MCP Tools for Agents

```json
{
  "mcpServers": {
    "gitea": {
      "transport": "sse",
      "url": "http://gitea:3000/api/mcp",
      "description": "Gitea repository operations"
    },
    "trailmark": {
      "transport": "stdio",
      "command": "trailmark",
      "args": ["mcp-server"],
      "description": "Code graph analysis"
    }
  }
}
```

### Privacy-Protected Agent

```python
# Anonymize PII in agent interactions
response = client.chat.completions.create(
    model="privacy-moa-gpt-4o",
    messages=[{
        "role": "user",
        "content": "Analyze code for user@example.com's project"
    }]
)
# PII is anonymized in processing, deanonymized in response
```

### Memory-Enabled Agent

```python
# Unbounded context with persistence
response = client.chat.completions.create(
    model="memory-moa-gpt-4o",
    messages=[{
        "role": "user",
        "content": "Remember: project uses FastAPI with SQLAlchemy"
    }]
)
# Memory persists across requests via OPTILLM_MEMORY_FILE
```

## Configuration

### Command Line

```bash
optillm \
  --approach moa \
  --model gpt-4o \
  --port 8000 \
  --best-of-n 5 \
  --mcts-simulations 3
```

### Environment Variables

```bash
export OPTILLM_APPROACH=moa
export OPTILLM_MODEL=gpt-4o
export OPTILLM_PORT=8000
export OPTILLM_BEST_OF_N=5
```

### Docker

```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e OPTILLM_APPROACH=moa \
  ghcr.io/algorithmicsuperintelligence/optillm:latest
```

## Proven Results

| Technique | Base Model | Improvement | Benchmark |
|-----------|-----------|-------------|-----------|
| MARS | Gemini 2.5 Flash Lite | +30.0 points | AIME 2025 |
| CePO | Llama 3.3 70B | +18.6 points | Math-L5 |
| AutoThink | DeepSeek-R1-1.5B | +9.34 points | GPQA-Diamond |
| LongCePO | Llama 3.3 70B | +13.6 points | InfiniteBench |
| MOA | GPT-4o-mini | Matches GPT-4 | Arena-Hard-Auto |
| PlanSearch | GPT-4o-mini | +20% pass@5 | LiveCodeBench |

## Cost Estimation

| Model | Cost per Iteration |
|-------|-------------------|
| o3 | ~$0.15-0.60 |
| o3-mini | ~$0.03-0.12 |
| Gemini-2.5-Pro | ~$0.08-0.30 |
| Gemini-2.5-Flash | ~$0.01-0.05 |
| Local models | Nearly free |

## Rules

- **Start with `auto` approach** — let OptiLLM choose the best technique
- **Use prefixes for specific techniques** — `moa-`, `bon-`, `mars-`
- **Combine techniques** — `&` for pipeline, `|` for parallel
- **Monitor costs** — multiple calls increase cost
- **Enable plugins as needed** — memory, privacy, MCP
- **Use local inference** — for cost-sensitive workloads

## References

- Source: https://github.com/algorithmicsuperintelligence/optillm
- License: Apache-2.0
- LiteLLM: https://docs.litellm.ai/
- MCP: https://modelcontextprotocol.io/
