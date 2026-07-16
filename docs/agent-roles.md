# Forge0 Agent Roles

Every agent in the system. What they do, when they run, what they produce.

## Agent Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION ENGINE                         │
│              (deterministic, not an LLM)                        │
│                                                                 │
│  Reads .forge0/workflow.yaml → dispatches agents → transitions  │
└────────┬──────────┬──────────┬──────────┬──────────┬────────────┘
         │          │          │          │          │
    ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼───┐ ┌───▼────┐
    │ Require│ │Architect│ │Decomp│ │Implement│ │ Critic │
    │ ments  │ │  ure   │ │ose   │ │  ation  │ │        │
    └────────┘ └────────┘ └──────┘ └────────┘ └────────┘
    
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │Pipeline│ │ Backlog │ │  Doc   │ │Knowledge│ │Research│
    │ Watcher│ │  Agent │ │  Agent │ │  Agent  │ │  Agent │
    └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

## Phase Agents (one-shot, per project)

These run during the greenfield workflow. Each is invoked once per phase.

### Requirements Agent

**When:** Phase 1 (Requirements)
**Trigger:** New project intake
**Input:** User's initial request
**Output:** `requirement.md` with structured spec

**Behavior:**
- Conducts structured interview with user (see `requirements-elicitation.md`)
- Asks 2-3 questions at a time
- Synthesizes answers into YAML frontmatter + markdown
- Presents summary for confirmation
- Iterates based on feedback

**Model:** Capable (kimi-k2.7-code or equivalent)
**Evaluation:** Critic agent checks testable criteria, required sections

---

### Architecture Agent

**When:** Phase 2 (Architecture)
**Trigger:** Requirement approved
**Input:** `requirement.md`
**Output:** `architecture.md` with tech decisions

**Behavior:**
- Reads approved requirements
- Proposes tech stack, patterns, project structure
- Each choice includes rationale and alternatives considered
- Checks `.forge0/knowledge/decisions.md` for existing conventions
- Logs new decisions to knowledge base

**Model:** Capable (kimi-k2.7-code or equivalent)
**Evaluation:** Critic agent checks decisions match requirements, no contradictions

---

### Decomposition Agent

**When:** Phase 3 (Decomposition)
**Trigger:** Architecture approved
**Input:** `requirement.md` + `architecture.md`
**Output:** `decomposition.md` (function DAG) + `TASK-*.md` files

**Behavior:**
- Identifies top-level entry points
- Decomposes into atomic functions (one purpose each)
- Builds dependency graph
- Groups functions into tasks (3-8 per task)
- Validates: no circular deps, all leaves implementable

**Model:** Capable (kimi-k2.7-code or equivalent)
**Evaluation:** Critic agent checks atomicity, dependency validity, coverage

---

### Implementation Agent

**When:** Phase 4 (Implementation)
**Trigger:** Task branch created
**Input:** Task spec + architecture + decomposition
**Output:** Code + tests (committed to task branch)

**Behavior:**
- Reads task spec (which functions to implement)
- For each function: writes test FIRST, then implementation
- Commits test+code as atomic pair
- Runs `pytest` locally before committing
- Follows conventions in AGENTS.md

**Model:** Capable (kimi-k2.7-code or equivalent)
**Evaluation:** CI runs pytest + lint + coverage. Critic agent reviews code quality.

**Sub-behavior per function:**
1. Read function spec (signature, purpose, acceptance criteria)
2. Write test file (`tests/test_{module}.py`)
3. Run test (expect failure — functions don't exist)
4. Write implementation (`src/{module}.py`)
5. Run test (expect pass)
6. Run lint + type check
7. Commit: `feat(REQ-NNN): add {function_name} with tests`

---

### Critic Agent

**When:** After every phase agent produces output
**Trigger:** Phase agent completes
**Input:** Artifact to evaluate + evaluation criteria
**Output:** Pass/fail + feedback

**Behavior:**
- Reads the artifact (requirement, architecture, code, etc.)
- Checks against evaluation criteria for that artifact type
- Returns structured result:
  ```json
  {
    "pass": true,
    "checks": { ... },
    "feedback": "..."
  }
  ```
- If fail: producing agent retries (up to 3 attempts)
- If all attempts fail: escalate to human

**Model:** Cheap (deepseek-v4-flash) — this is judgment, not generation
**Evaluation:** N/A (this IS the evaluator)

---

### Research Agent

**When:** On-demand (from other agents or user) + scheduled (weekly/monthly)
**Trigger:** Requirements elicitation, architecture decision, dependency audit, security scan
**Input:** Research question or monitoring task
**Output:** Research findings stored in wiki

**Behavior:**
- **On-demand research:** Takes a topic, searches web/docs/packages, synthesizes findings, stores in wiki
- **Dependency monitoring:** Weekly scan of all dependencies for updates, deprecations, security patches
- **Security monitoring:** Daily check of CVE databases for vulnerabilities in used packages
- **Tech landscape:** Monthly review of relevant technology trends, new tools, best practices
- All findings stored in wiki (`Research/` and `Monitoring/` sections)
- Findings include sources, freshness metadata, and recommendations

**Model:** Capable (kimi-k2.7-code) for synthesis, cheap (deepseek-v4-flash) for monitoring scans
**Evaluation:** N/A (research is informational, not a gate)
**Tools:** Web search (Brave), doc fetching, package registry APIs, CVE databases
**Documentation:** See `research-agents.md` for full details

## Continuous Agents (background, ongoing)

These run on schedules or triggers. They maintain the project after initial build.

### Pipeline Watcher Agent

**When:** On CI event (Gitea webhook)
**Trigger:** Workflow run completes (success or failure)
**Input:** CI run results (logs, exit codes, coverage)
**Output:** Comments on PR, issue updates

**Behavior:**
- **On failure:** Analyze logs, identify root cause, comment on PR with diagnosis
- **On success:** Update task issue status, check if all tasks for requirement are done
- **On coverage drop:** Comment with specific uncovered lines
- **On all tasks complete:** Trigger review phase (open PR for human review)

**Model:** Cheap (deepseek-v4-flash) for analysis, capable for suggestions
**Integration:** Gitea webhook → portal → agent

**Webhook events consumed:**
- `workflow_run` — CI run completed
- `pull_request` — PR opened/updated/merged

---

### Backlog Agent

**When:** On issue event (Gitea webhook) or weekly schedule
**Trigger:** Issue created/updated/closed, or weekly maintenance
**Input:** Current issues, requirement status, decomposition
**Output:** Issue updates, new issues, priority adjustments

**Behavior:**
- **On requirement approved:** Create task issues from decomposition
- **On task completed:** Update requirement progress, unblock dependent tasks
- **On blocker detected:** Re-prioritize affected tasks, add `blocked` label
- **Weekly:** Review stale issues (no activity > 7 days), suggest cleanup
- **Weekly:** Update project velocity metrics

**Model:** Cheap (deepseek-v4-flash)
**Integration:** Gitea webhook → portal → agent

**Issue labels managed:**
- `task` — work item
- `REQ-{NNN}` — linked requirement
- `complexity:simple|moderate|complex`
- `status:blocked|in-progress|review|done`
- `priority:p0|p1|p2`

---

### Documentation Agent

**When:** On merge event (Gitea webhook) or weekly schedule
**Trigger:** PR merged to main, or weekly maintenance
**Input:** Merged code, commit history, requirement specs
**Output:** Wiki pages, changelog, API docs

**Behavior:**
- **On merge:** Update changelog in wiki (from conventional commits)
- **On merge:** Update API docs (from docstrings/type hints)
- **On architecture change:** Update architecture.md in wiki
- **Weekly:** Update project status page (test coverage, open issues, velocity)
- **On demand:** Generate README, getting-started guide

**Model:** Cheap (deepseek-v4-flash) for formatting, capable for writing
**Integration:** Gitea webhook → portal → agent → Gitea wiki API

**Wiki pages maintained:**
- `Home` — project overview + status dashboard
- `Architecture` — tech stack, patterns, decisions
- `API-Reference` — auto-generated from code
- `Changelog` — auto-generated from commits
- `Development` — how to contribute, conventions

---

### Knowledge Agent

**When:** Called by other agents (tool call)
**Trigger:** Another agent has a question about project context
**Input:** Question about conventions, decisions, patterns
**Output:** Answer or assumption

**Behavior:**
- Searches `.forge0/knowledge/` for relevant decisions/assumptions
- Searches architecture.md for existing patterns
- Searches codebase for conventions
- Returns answer if found, or logs assumption if not

**Model:** Cheap (deepseek-v4-flash)
**Integration:** Internal tool call (not webhook-triggered)

**This is the agent McKinsey describes:** a dedicated agent that other agents call to query project context and log assumptions. It prevents each agent from filling its context window with search results.

## Agent Communication

```
User ──▶ Portal ──▶ Orchestrator ──▶ Phase Agents ──▶ Critic Agent
                       │                                    │
                       │                                    ▼
                       │                              pass/fail
                       │                                    │
                       ▼                                    │
                  Gitea API ◀───────────────────────────────┘
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
         Issues     Wiki       PRs
            ▲          ▲          ▲
            │          │          │
            └──────────┼──────────┘
                       │
                  Webhooks ──▶ Continuous Agents
```

## Agent Lifecycle

### Phase agents
1. Orchestrator reads `workflow.yaml`
2. Orchestrator invokes appropriate agent with context
3. Agent produces artifact
4. Critic agent evaluates
5. If pass: orchestrator updates `workflow.yaml`, advances phase
6. If fail: agent retries (up to 3x)
7. If all retries fail: escalate to human

### Continuous agents
1. Webhook fires (CI complete, issue updated, PR merged)
2. Portal receives webhook, identifies project
3. Portal invokes appropriate continuous agent
4. Agent takes action (comment, update, create)
5. Agent logs action to `.forge0/agent-log.md`

## Cost per Agent (estimated, using OpenCode Go)

| Agent | Model | Est. Tokens/invocation | Est. Cost |
|---|---|---|---|
| Requirements | kimi-k2.7-code | 100K | $0.15 |
| Architecture | kimi-k2.7-code | 60K | $0.09 |
| Decomposition | kimi-k2.7-code | 80K | $0.12 |
| Implementation | kimi-k2.7-code | 50K/function | $0.08 |
| Critic | deepseek-v4-flash | 20K | $0.003 |
| Pipeline Watcher | deepseek-v4-flash | 15K | $0.002 |
| Backlog Agent | deepseek-v4-flash | 10K | $0.001 |
| Documentation | deepseek-v4-flash | 30K | $0.005 |
| Knowledge | deepseek-v4-flash | 5K | $0.001 |

Total for a 5-task greenfield project: ~$0.70
