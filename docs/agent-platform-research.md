# AI Agent Development Platform Research

## Executive Summary

Research into 10+ AI agent-driven development platforms reveals consistent patterns for building successful agent systems. This document synthesizes findings from OpenHands, SWE-agent, Aider, Devin, Cursor, Copilot Workspace, and others to inform Forge0's architecture.

## Key Findings

### 1. The Agent Loop Pattern

Every successful platform uses a core loop:

```
while not finished:
    1. Observe (read state, files, errors)
    2. Think (plan next action)
    3. Act (edit file, run command, create PR)
    4. Verify (check result, run tests)
    5. Decide (continue, retry, or finish)
```

**Critical insight**: Agents must see their own consequences (stdout, exit codes, diffs) to self-correct. This is observation-driven learning.

### 2. Spec-Driven Development (GitHub SpecKit)

The most successful systems use **specs before code**:

| Artifact | Purpose | Key Rule |
|----------|---------|----------|
| `constitution.md` | Project principles | Immutable, triggers consistency propagation |
| `spec.md` | Requirements | **Must not** mention tech stacks — only "what" and "why" |
| `plan.md` | Architecture | **Must** provide tech choices for the spec |
| `tasks.md` | Implementation | Strict checkbox format with IDs, labels, file paths |

**The spec/plan separation is critical**: The same `spec.md` can have multiple `plan.md` files (React plan, Vue plan, etc.) without changing functional requirements.

### 3. Edit Formats (Aider's Empirical Testing)

| Format | Description | Best For |
|--------|-------------|----------|
| `whole` | Return entire modified file | Small files, simple changes |
| `diff` | SEARCH/REPLACE blocks with git-style markers | Most models |
| `udiff` | Simplified unified diff | GPT-4 Turbo (reduces laziness) |
| `editor-diff` | Streamlined for architect mode | Multi-model workflows |

**SEARCH/REPLACE Block Format**:
````
src/module.py
```python
<<<<<<< SEARCH
def old_function():
    pass
=======
def new_function():
    return True
>>>>>>> REPLACE
```
````

### 4. Context Management

**Four Buckets** (from LangChain's framework):

1. **Write Context** — Save outside the context window
   - Scratchpads during task execution
   - Cross-session memories

2. **Select Context** — Pull only relevant info
   - Always-loaded files: `CLAUDE.md`, `.cursorrules`, `AGENTS.md`
   - RAG on code for relevance
   - RAG on tools for better selection

3. **Compress Context** — Keep only needed tokens
   - Summarization at 95% context usage
   - Trimming old messages
   - Post-process tool calls

4. **Isolate Context** — Split across sub-agents
   - Each sub-agent has its own context window
   - Tradeoff: up to 15x more tokens than single-agent

### 5. Git Automation Patterns

**Branch Strategy**: `agent/<ticket>-<short-desc>`
- Tells reviewers this is machine-generated code
- Enables branch protection rules for agent work
- Makes it easy to find all agent-created branches

**PR Creation Pattern**:
```python
pr_description = f"""## Summary
{one_line_summary}

## Changes
{bullet_list_of_changes}

## Test Plan
{how_to_verify}

## Related Issues
{linked_issue_numbers}

## AI Review
{automated_review_summary}
"""
```

**Conventional Commits** (for changelog generation):
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation
- `test:` — Adding tests
- `refactor:` — Code restructuring
- `BREAKING CHANGE:` — Incompatible changes

### 6. Quality Gates (Tiered Pipeline)

```
┌─────────────────────────────────────────┐
│  Tier 1: Fast (< 30s)                  │
│  - Syntax check (AST parse)             │
│  - Lint (ruff/eslint)                   │
│  - Format check (prettier/black)        │
├─────────────────────────────────────────┤
│  Tier 2: Medium (1-3 min)              │
│  - Unit test execution                  │
│  - Type checking (mypy/pyright)         │
│  - Commit message format validation     │
├─────────────────────────────────────────┤
│  Tier 3: Deep (3-10 min)               │
│  - Integration tests                    │
│  - Security scan (semgrep/gitleaks)     │
│  - Dependency vulnerability check       │
├─────────────────────────────────────────┤
│  Tier 4: Pre-merge (on approval)        │
│  - Full test suite                      │
│  - Performance regression               │
│  - Architecture consistency check       │
└─────────────────────────────────────────┘
```

### 7. Error Recovery & Resilience

**Build/Test Failure Recovery**:
```
attempt 1: run build → failure
    ↓ capture error output
attempt 2: run build + error context → failure  
    ↓ capture both errors
attempt 3: analyze error patterns, suggest fix
    ↓ if still failing, escalate to human
```

**Infinite Loop Detection**:
| Detection Method | Implementation |
|-----------------|----------------|
| **Max iterations** | Hard cap on agent turns (e.g., 50) |
| **Token budget** | Track cumulative tokens; abort at threshold |
| **Cost tracking** | Estimate cost per turn; kill if $N exceeded |
| **Deduplication** | If agent produces same output 3x, force exit |
| **Time-based** | Wall-clock timeout per task |

**Cost Overruns**:
```python
per_task_budget = $0.50
max_tokens_per_task = 100,000

# Before each LLM call:
if cumulative_cost > per_task_budget:
    return TaskResult(status="budget_exceeded", summary=scratchpad)
if cumulative_tokens > max_tokens_per_task:
    return TaskResult(status="token_limit", summary=scratchpad)
```

### 8. Agent Memory Systems

**File-Based Memory** (Gitea-native):
```markdown
# .agent/memory/progress.md
## Current Task
Implementing user authentication with JWT tokens

## Decisions Made
- Using bcrypt for password hashing (2024-07-10)
- JWT expiry set to 24h (short-lived) + refresh tokens

## Blockers
- Waiting on DB migration for user_sessions table

## Completed This Session
- [x] Created /api/auth/login endpoint
- [x] Added password validation middleware
- [x] Wrote unit tests for auth module

## Next Session Priority
1. Add /api/auth/refresh endpoint
2. Write integration tests
3. Update API docs
```

**Gitea Issues as Persistent Memory**:
```python
async def log_decision_to_issue(decision: dict, repo: str, token: str):
    """Store architectural decisions as Gitea issues with labels"""
    await create_issue(
        repo=repo,
        title=f"[Decision] {decision['title']}",
        body=decision['rationale'],
        labels=["decision", f"component:{decision['component']}"],
        token=token
    )
```

**Git as Recovery Mechanism**:
```python
class AgentSession:
    def commit_checkpoint(self, message: str):
        """Descriptive commits allow revert and state restoration"""
        subprocess.run(["git", "add", "-A"])
        subprocess.run(["git", "commit", "-m", f"[agent] {message}"])
    
    def rollback_to_last_good(self):
        """Revert bad changes from current session"""
        subprocess.run(["git", "reset", "--hard", "HEAD~1"])
```

### 9. Security Scanning

**Integrated Security Pipeline**:
```yaml
# .gitea/workflows/security.yaml
name: Security Scan
on:
  pull_request:
  push:
    branches: [main]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      # Secret scanning
      - name: Gitleaks
        run: |
          gitleaks detect --source . --report-format json \
            --report-path gitleaks.json --redact
          if [ -s gitleaks.json ]; then
            echo "::error::Secrets detected!"
            exit 1
          fi
      
      # SAST - Multi-tool
      - name: Semgrep
        run: |
          semgrep scan \
            --config=p/owasp-top-ten \
            --config=p/secrets \
            --config=p/python \
            --json --output semgrep.json ./src/
      
      - name: Bandit (Python)
        run: |
          bandit -r ./src -f json -o bandit.json -l -i \
            --severity-level medium \
            --confidence-level medium
```

**Security Hardening for Agent Itself**:
```python
# Prompt injection protection
INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"disregard (all|your) (previous|prior|system)",
    r"you are now",
    r"act as",
    r"<\|.*?\|>",
    r"\[INST\]",
    r"###\s*(system|instruction)",
]

def sanitize_code_input(code: str) -> str:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            raise SecurityError(f"Prompt injection detected: {pattern}")
    if len(code) > 50000:
        raise SecurityError("Code exceeds token budget")
    return code
```

### 10. Multi-Agent Orchestration

**Three Dominant Paradigms**:

| Paradigm | Framework | Coordination | Best For |
|----------|-----------|-------------|----------|
| **Role-based crews** | CrewAI | Predefined roles + sequential/hierarchical process | Clear workflows with known steps |
| **Directed graph** | LangGraph | Nodes (functions) + conditional edges + state schema | Maximum control, compliance, production |
| **Conversational** | AutoGen/AG2 | GroupChat with speaker selection | Unknown flows, parallelism, .NET+Python |

**Agent Communication Patterns**:

1. **Handoff** (OpenAI Swarm pattern)
   - Agents don't share memory; they pass state through return values
   - Simple but fragile — no centralized coordination

2. **Shared State Graph** (LangGraph)
   - State is the single source of truth
   - Nodes are pure functions: read state → compute → write partial update
   - Supports checkpointing (persistence across restarts)

3. **Supervisor Pattern** (LangGraph)
   - One agent decides which sub-agents to invoke
   - Sub-agents return results to supervisor
   - Supervisor synthesizes final output

## Gitea-Specific Implementation

### Gitea Actions (CI)

**Workflow Location**: `.gitea/workflows/*.yaml`

**Example Agent Workflow**:
```yaml
name: AI Code Review Agent
on:
  pull_request:
    types: [opened, synchronize]
  issue_comment:
    types: [created]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run PR Review
        if: contains(github.event.comment.body, '/review')
        env:
          OPENAI_KEY: ${{ secrets.OPENAI_KEY }}
          GITEA_TOKEN: ${{ secrets.GITEA_TOKEN }}
        run: python scripts/review.py --pr ${{ github.event.issue.number }}
```

### Gitea Webhooks

**Available Events**:
- Repository: `create`, `delete`, `fork`, `push`, `wiki`, `repository`, `release`, `package`, `status`
- Issues: `issues`, `issue_assign`, `issue_label`, `issue_milestone`, `issue_comment`
- Pull Requests: `pull_request`, `pull_request_assign`, `pull_request_label`, `pull_request_comment`, `pull_request_review`, `pull_request_review_approved`, `pull_request_review_rejected`, `pull_request_review_comment`, `pull_request_sync`, `pull_request_review_request`
- Workflows: `workflow_run`, `workflow_job`

**Triggering Agent Workflows**:
```python
@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Gitea-Signature", "")
    
    # Verify HMAC signature
    expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return {"error": "invalid signature"}, 401
    
    event = request.headers.get("X-Gitea-Event")
    data = await request.json()
    
    if event == "pull_request" and data["action"] == "opened":
        await trigger_review_agent(data["pull_request"]["number"])
```

### Gitea API for Automation

**Key Endpoints**:
```bash
# Issues
POST   /repos/{owner}/{repo}/issues                    # Create issue
PATCH  /repos/{owner}/{repo}/issues/{index}            # Update issue
POST   /repos/{owner}/{repo}/issues/{index}/comments   # Add comment

# Pull Requests
POST   /repos/{owner}/{repo}/pulls                     # Create PR
GET    /repos/{owner}/{repo}/pulls/{index}/files       # Get changed files
POST   /repos/{owner}/{repo}/pulls/{index}/reviews     # Submit review
POST   /repos/{owner}/{repo}/pulls/{index}/comments    # Review comment

# Repository
GET    /repos/{owner}/{repo}/contents/{filepath}       # Get file content
PUT    /repos/{owner}/{repo}/contents/{filepath}       # Create/update file
GET    /repos/{owner}/{repo}/git/trees/{sha}           # Get tree
GET    /repos/{owner}/{repo}/commits/{sha}/diff        # Get commit diff
```

## Gap Analysis: Forge0 vs Best Practices

### Current Forge0 Architecture
1. Gitea (git hosting, issues, PRs, Actions)
2. Portal (FastAPI + HTMX dashboard)
3. SearXNG (web search)
4. LLM client (OpenAI-compatible)
5. Orchestration engine (phase-based state machine)
6. Agent base classes (Research, Critic, Requirements, Architecture)

### Missing Patterns (Prioritized by Impact)

**High Impact, Low Effort (Quick Wins)**:
1. ✅ AGENTS.md in repos (always-loaded context)
2. ✅ Branch strategy (agent/* prefix)
3. ✅ Conventional commits
4. ✅ Token budget tracking
5. ✅ Max iterations guard
6. ✅ Autosubmit on error

**High Impact, Medium Effort**:
1. Spec document structure (spec.md, plan.md, tasks.md)
2. Clarify loop (ask questions before planning)
3. SEARCH/REPLACE edit format
4. Context compression
5. Lint/type-check gates
6. Security scanning (gitleaks, semgrep)

**High Impact, High Effort**:
1. Tree-sitter repo-map
2. Mutation testing
3. Gitea Actions integration
4. Multi-agent supervisor pattern
5. Cross-session memory

### Recommended Next Steps

1. **Immediate** (This Week):
   - Implement SEARCH/REPLACE edit format
   - Add token budget tracking
   - Create AGENTS.md template
   - Implement max iterations guard

2. **Short-term** (Next 2 Weeks):
   - Spec document structure
   - Clarify loop
   - Lint/type-check gates
   - Branch strategy

3. **Medium-term** (Next Month):
   - Security scanning
   - Gitea Actions integration
   - Multi-agent supervisor pattern
   - Cross-session memory

## References

- OpenHands: Event-sourced architecture, CodeAct pattern
- SWE-agent: ACI design philosophy, bash scripts in YAML manifests
- Aider: Repo-map (tree-sitter), edit formats, auto-commit
- Devin: Fleet management, parallel execution
- Cursor: Background Agent, multi-agent architecture
- GitHub Copilot Workspace: SpecKit, specification-first thinking
- LangGraph: Shared state graph, supervisor pattern
- CrewAI: Role-based crews, predefined roles
- PR-Agent: Multi-modal code review, self-reflection pipeline

## Conclusion

The research reveals that successful AI agent development platforms share these core patterns:

1. **Observation-driven self-correction** — Agents see their own consequences
2. **Autosubmit on error** — Ship partial work rather than crash
3. **Verification loops before completion** — Must re-run tests before declaring done
4. **Spec-first thinking** — Requirements before code, every time
5. **Context management** — Always-loaded files, compression, isolation
6. **Git-native workflows** — Branch prefixes, conventional commits, structured PRs
7. **Tiered quality gates** — Fast lint → medium test → deep security
8. **Memory persistence** — File-based + issue-based + git history

For Forge0, the immediate priorities are:
1. Implement the agent loop pattern with stuck detection
2. Add SEARCH/REPLACE edit format
3. Create AGENTS.md template
4. Implement token budget tracking
5. Add conventional commits

The current orchestration engine is on the right track, but needs to be more observation-driven. The phase machine approach is good, but agents need to see their own output and self-correct.
