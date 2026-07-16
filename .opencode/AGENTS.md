# Forge0 Agent Platform

AI agent-driven development platform using OpenCode's native primitives — skills, agents, rules, and permissions.

## Core Principle: Think Before You Act

**Use sequential thinking for EVERYTHING.** Before any action:
1. Analyze the problem
2. Consider alternatives
3. Choose the best approach
4. Execute
5. Verify results

This applies to:
- Writing code
- Reviewing code
- Debugging
- Planning
- Architecture decisions
- Security analysis

## MCP Tools

Every agent has access to these tools:

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **sequential-thinking** | Structured problem-solving | Every decision, every action |
| **context7** | Library/framework docs | When using any API or library |
| **searxng** | Web search | Research, find examples, check docs |
| **gitea** | Git hosting API | Issues, PRs, wikis, repos, actions |

### Sequential Thinking

Use the `sequentialthinking` tool for:
- Breaking down complex problems
- Planning multi-step tasks
- Analyzing code before changes
- Debugging issues
- Making architectural decisions
- Reviewing pull requests

**Every non-trivial action should start with sequential thinking.**

### Context7

Use `context7` tools when:
- Using any library or framework
- Looking up API documentation
- Finding code examples
- Checking version compatibility

### SearXNG

Use `searxng` tools when:
- Researching best practices
- Finding examples of similar problems
- Checking for known issues
- Looking up documentation

### Gitea

Use `gitea` tools for:
- Reading project wikis
- Checking issues and PRs
- Viewing git history
- Understanding project context
- Coordinating with other work

## LSP Integration

OpenCode has LSP servers enabled for real-time diagnostics:

| Language | LSP Server | Extensions |
|----------|------------|------------|
| Python | pyright | .py, .pyi |
| Python | ruff | .py, .pyi |
| JavaScript/TypeScript | typescript | .ts, .tsx, .js, .jsx |
| YAML | yaml-ls | .yaml, .yml |
| Bash | bash | .sh, .bash, .zsh |

### Benefits
- Real-time error detection
- Type checking
- Code navigation
- Auto-completion
- Diagnostics feedback to agents

### Commands

Always run these before committing:
```bash
# Type checking
pyright src/

# Linting
ruff check src/

# Formatting
ruff format src/
```

## Project Context

**ALWAYS load project context before starting work.** This includes:

### 1. Wiki
```bash
# List wiki pages
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/wiki/pages" | jq

# Read specific page
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/wiki/pages/{page_name}" | jq
```

### 2. Documentation
```bash
# Read README
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/contents/README.md" | jq -r '.content' | base64 -d

# List docs/
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/contents/docs" | jq
```

### 3. Issues and PRs
```bash
# Open issues
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/issues?state=open" | jq

# Recent PRs
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/pulls?state=all&limit=10" | jq
```

### 4. Git History
```bash
# Recent commits
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/commits?limit=20" | jq
```

### 5. Fleet Context
```bash
# All repos in the org
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/orgs/forge0/repos" | jq
```

## Architecture

Every repo in Forge0 gets these files:

```
.opencode/
├── opencode.json          # Agent definitions + permissions + MCP
├── agents/
│   ├── planner.md         # Requirements analyst (read-only)
│   ├── coder.md           # Software engineer (full access)
│   ├── reviewer.md        # Code reviewer (read-only + trailmark)
│   ├── security.md        # Security auditor (read-only + trailmark)
│   ├── test-writer.md     # Test engineer (write tests + run)
│   └── orchestrator.md    # Workflow coordinator (full access)
└── skills/
    ├── spec-driven/       # Full dev workflow
    ├── edit-format/       # SEARCH/REPLACE editing
    ├── trailmark/         # Code property graph analysis
    ├── openevolve/        # Evolutionary code optimization
    ├── optillm/           # LLM inference optimization
    ├── security-scan/     # Gitleaks, semgrep, bandit
    ├── test-gen/          # Test generation
    ├── git-flow/          # Git automation
    └── project-context/   # Load wikis, docs, issues, fleet

AGENTS.md                   # Project conventions (root)
```

## Agent Roles

| Agent | Mode | Permissions | Purpose |
|-------|------|-------------|---------|
| **build** | primary | full | Standard development |
| **plan** | primary | read-only | Analysis and planning |
| **planner** | subagent | read-only | Requirements analysis |
| **coder** | subagent | full | Code implementation |
| **reviewer** | subagent | read-only + trailmark | Code review |
| **security** | subagent | read-only + trailmark | Security audit |
| **test-writer** | subagent | write tests | Test generation |
| **orchestrator** | subagent | full + delegate | Workflow coordination |

## Workflow

### 1. Spec-Driven Development

```
User Issue → [Load Context] → [Planner] → spec.md → [Coder] → code → [Reviewer] → PR
```

### 2. Security Audit

```
Code → [TrailMark] → graph → [Security] → findings → [TrailMark augment] → overlay
```

### 3. Code Optimization

```
Code → [OpenEvolve] → evolution → optimized code
```

### 4. LLM Enhancement

```
Request → [OptiLLM] → optimized response
```

## Skills

### Core Development
- **spec-driven** — Full development workflow
- **edit-format** — SEARCH/REPLACE block editing
- **git-flow** — Branch strategy, commits, PRs
- **project-context** — Load wikis, docs, issues, fleet status

### Security & Analysis
- **trailmark** — Code property graph (structure, entrypoints, data flow, complexity, trust boundaries)
- **security-scan** — Gitleaks, semgrep, bandit integration

### Optimization
- **openevolve** — Evolutionary code optimization
- **optillm** — LLM inference optimization (20+ techniques)
- **optuna-optimize** — Hyperparameter optimization with Optuna

### Quality
- **test-gen** — Comprehensive test generation
- **wandb-tracking** — Experiment tracking with W&B

### Governance
- **governance** — Enforce work item hygiene, git hygiene, auto-documentation, prevent sprawl
- **docker-governance** — Base image extension, package registry, build cache optimization, anti-thrashing

## Configuration

### opencode.json

Defines agents with constrained permissions and MCP tools:

```json
{
  "mcp": {
    "searxng": { "type": "local", "command": [...] },
    "context7": { "type": "remote", "url": "..." },
    "sequential-thinking": { "type": "local", "command": [...] },
    "gitea": { "type": "local", "command": [...] }
  },
  "agent": {
    "planner": { "permission": { "edit": "deny" } },
    "coder": { "permission": { "edit": "allow" } }
  }
}
```

### AGENTS.md

Project conventions, always loaded:

```markdown
# Project Name

## Conventions
- Use type hints
- Follow PEP 8
- Write docstrings

## Commands
- pytest — run tests
- ruff check — lint
- mypy — type check
```

## Getting Started

1. Create `.opencode/` directory
2. Add `opencode.json` with agent definitions and MCP servers
3. Create agent markdown files
4. Add skill definitions
5. Create `AGENTS.md` with project conventions
6. **Load project context before any work**

## Critical Constraints

### Cost Limits
- Max tokens per task: 100,000
- Max cost per task: $5.00
- Max iterations: 50
- Timeout: 30 minutes

### Quality Gates
- All tests must pass
- No lint errors
- No type errors
- Security scan clean
- TrailMark analysis clean

### Anti-Patterns
- **No forked base images** — extend official bases
- **No :latest tags** — pin all versions
- **No raw owning pointers** — use RAII/smart pointers
- **No infinite loops** — stuck detection required
- **No cost overruns** — budget tracking required

## Agent Infrastructure

### State Persistence
Save and resume agent state via Gitea issues:
```python
from app.state import AgentState

state = AgentState(owner, repo, issue_number)
await state.save("coder", {"phase": "implementation", "progress": {}})
await state.load("coder")
```

### Stuck Detection
Detect when agent is looping:
```python
from app.stuck_detection import StuckDetector, Action

detector = StuckDetector(max_iterations=50, cost_limit=5.0)
is_stuck = detector.record(Action(tool="bash", input={"command": "pytest"}))
if is_stuck:
    # Break out of loop
```

### Observation-Driven Self-Correction
Agent sees its own output and fixes issues:
```python
from app.self_correction import SelfCorrector

corrector = SelfCorrector(max_retries=3)
corrected_code, feedbacks = await corrector.observe_and_correct(code, file_path, "py")
```

### Agent Coordination
Multiple agents working together:
```python
from app.coordination import AgentCoordinator, AgentRole

coordinator = AgentCoordinator(owner, repo)
task = await coordinator.create_task("Implement auth", "Add JWT auth")
await coordinator.assign_task(task.id, AgentRole.CODER)
await coordinator.complete_task(task.id, result)
```

### Rollback Mechanism
Auto-revert on test failure:
```python
from app.rollback import RollbackManager

rollback = RollbackManager(repo_path)
checkpoint = await rollback.create_checkpoint("Before changes")
await rollback.rollback(checkpoint)
```

## References

- OpenCode Skills: https://opencode.ai/docs/skills
- OpenCode Agents: https://opencode.ai/docs/agents
- OpenCode Rules: https://opencode.ai/docs/rules
- OpenCode MCP: https://opencode.ai/docs/mcp-servers
- TrailMark: https://github.com/trailofbits/trailmark
- OpenEvolve: https://github.com/algorithmicsuperintelligence/openevolve
- OptiLLM: https://github.com/algorithmicsuperintelligence/optillm
- Context7: https://mcp.context7.com/mcp
- Sequential Thinking: https://www.npmjs.com/package/@modelcontextprotocol/server-sequential-thinking
- Gitea MCP: https://www.npmjs.com/package/@boringstudio_org/gitea-mcp
