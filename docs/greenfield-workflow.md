# Forge0 Greenfield Workflow

How Forge0 handles a user requesting a new project from scratch.

## The Problem

User says: "I need a website." What happens next?

The naive approach is to start coding immediately. This produces garbage — wrong tech stack, missing features, no tests, no architecture. The user gets something that "works" but can't evolve.

## The Approach: Spec-Driven Development

Borrowing from McKinsey QuantumBlack's two-layer model, LangGraph's graph-based agent patterns, and the agent-driven-dev-framework:

**Deterministic orchestration** controls *what* phase we're in and *when* to transition.
**Bounded agents** do the creative work *within* each phase.

Agents don't decide what comes next. A workflow engine does.

## Phases

```
┌────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────┐
│ INTAKE  │──▶│ REQUIREMENTS │──▶│ARCHITECTURE  │──▶│ DECOMPOSITION│──▶│     TDD      │──▶│   REVIEW     │──▶│ MERGE  │
│ (auto)  │   │ (agent+user) │   │   (agent)    │   │   (agent)    │   │  (agents)    │   │   (human)    │   │ (auto) │
└────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └────────┘
    │              │                    │                  │                  │                  │                │
    ▼              ▼                    ▼                  ▼                  ▼                  ▼                ▼
 project      requirement.md      architecture.md    decomposition.md   test→code→commit    PR review        main
 record       + user confirm      + user override    + TASK-*.md        per function        + critic         branch
```

### Phase 0: INTAKE (automatic)

User posts a request on the portal. System creates a project record with a unique ID. No agent involvement yet.

**Trigger:** User clicks "New Project" and types a description.
**Output:** Project record in `pending` state.
**Gate:** Automatic — proceeds to Requirements.

### Phase 1: REQUIREMENTS (agent + user conversation)

A requirements agent engages the user in a structured conversation. Not a form — a conversation. But the agent follows a protocol (see `requirements-elicitation.md`).

**Input:** User's initial request text.
**Process:**
1. Agent asks clarifying questions (2-3 at a time, not 20 at once)
2. Agent synthesizes answers into structured sections
3. Agent flags contradictions or gaps
4. Agent presents a summary for confirmation

**Output:** `requirement.md` with YAML frontmatter:
```yaml
---
id: REQ-001
title: "Portfolio Website"
status: draft          # draft → in-review → approved → complete
created: 2026-07-15
---
```

**Evaluation:**
- Deterministic: required sections present, frontmatter valid, acceptance criteria exist
- Critic agent: are acceptance criteria testable? Any ambiguity?

**Gate:** User confirms "yes, that's what I want." If not, agent revises.

### Phase 2: ARCHITECTURE (agent, user can override)

Architecture agent reads the approved requirements and proposes technical decisions.

**Input:** Approved `requirement.md`.
**Process:**
1. Agent proposes tech stack (framework, database, hosting)
2. Agent proposes project structure
3. Agent proposes patterns (auth, API design, state management)
4. Each choice includes rationale

**Output:** `architecture.md` with decisions and rationale.

**Evaluation:**
- Deterministic: required sections present, tech choices are valid combinations
- Critic agent: do choices match requirements? Any contradictions?

**Gate:** User can override specific choices. If no objection after review period, auto-approves.

### Phase 3: DECOMPOSITION (agent)

Decomposition Agent breaks the system into atomic functions, builds a dependency DAG, then groups functions into tasks.

**Input:** Approved `requirement.md` + `architecture.md`.
**Process:**
1. Agent identifies top-level entry points (API handlers, CLI commands)
2. Agent decomposes each into atomic functions (one purpose, one input, one output)
3. Agent builds dependency graph (which functions call which)
4. Agent validates: no circular dependencies, all leaves implementable
5. Agent groups functions into tasks (3-8 related functions per task)
6. Agent writes task specs with acceptance criteria

**Output:**
- `decomposition.md` — function registry + dependency DAG
- `TASK-*.md` files — one per task, with function list and acceptance criteria
- Gitea issues created — one per task

**Evaluation:**
- Deterministic: dependency graph is acyclic, all acceptance criteria from REQ covered, every function has a signature
- Critic agent: functions are truly atomic, tasks are appropriately scoped

**Gate:** Automatic — proceeds to TDD.

### Phase 4: TDD IMPLEMENTATION (agents)

Implementation agents pick up tasks in dependency order. For each function in the task: **write test first, then write code.** Each function+test pair is one atomic commit on the task branch.

**Input:** Task spec + architecture + decomposition.
**Process (per function):**
1. Agent writes test file (`tests/test_{module}.py`) defining the contract
2. Agent runs test (expect failure — function doesn't exist yet)
3. Agent writes implementation (`src/{module}.py`)
4. Agent runs test (expect pass)
5. Agent runs lint + type check
6. Agent commits: test + code as atomic pair

**Process (per task):**
1. Agent creates branch: `feature/REQ-NNN-task-NNN-{title}`
2. Agent implements functions one by one (test → code → commit)
3. CI runs on every push (tests must pass)
4. When all functions done, agent opens PR

**Evaluation:**
- Deterministic: all tests pass, lint clean, types correct, coverage ≥ 80%
- Test-code correspondence: every `src/` file has a matching `test_*.py`
- Critic agent: code matches task spec, follows architecture, no shortcuts

**Gate:** All tasks complete → PR ready for review.

### Phase 5: REVIEW (human)

Human reviews the complete PR: specs + architecture + tasks + code.

**Input:** PR with full context.
**Process:**
1. Human reviews (can see the reasoning behind every decision)
2. Human approves or requests changes
3. If changes: agent reworks on the branch

**Gate:** Human approves → merge to main.

## Key Design Decisions

### 1. Orchestration is deterministic

Agents don't decide what phase we're in. The workflow engine reads artifact status from frontmatter and transitions accordingly. This is the critical insight from McKinsey.

### 2. Artifacts are structured, not freeform

Every output has YAML frontmatter + defined sections. This enables:
- Machine-readable state tracking
- Automated evaluation
- Traceability (requirement → task → code → commit)

### 3. Humans enter at the right time

- Requirements phase: human is in the conversation (essential)
- Architecture phase: human can override (optional)
- Task phase: automatic (no human needed)
- Implementation phase: automatic (no human needed)
- Review phase: human reviews the complete output (essential)

### 4. Knowledge accumulates

The `.forge0/knowledge/` directory stores:
- Decisions made during architecture
- Assumptions the agent made (and were approved/rejected)
- Patterns discovered during implementation

Future projects can reference this knowledge. The system gets smarter over time.

### 5. Everything is in the repo

Specs, architecture, tasks, code — all in one repo. The repo IS the source of truth. No external project management tool needed. Gitea issues are derived from task files, not the other way around.

### 6. TDD is enforced by CI, not git hooks

Tests must exist and pass. Coverage must meet threshold. Lint must be clean. These are enforced server-side by Gitea Actions + branch protection. Git hooks are local conveniences, not enforcement mechanisms. See `enforcement-and-quality-gates.md`.

### 7. One branch per task, not per function

A task contains 3-8 related functions. One branch, one PR, one CI run. Atomicity is at the COMMIT level (each commit is one function+test pair), not the branch level. This keeps branch count manageable while maintaining traceability.

### 8. Python + pytest is the standard

All agent-written code is Python. Tests use pytest. This eliminates ambiguity and lets agents focus on one language, one framework, one toolchain. Non-Python code is tested through pytest (via subprocess). See `development-methodology.md`.

## Portal UX

The portal shows:
- **Project list** with phase indicators (colored dots)
- **Conversation view** for requirements elicitation
- **Artifact viewer** for reviewing specs/architecture
- **Task board** derived from Gitea issues
- **PR link** when ready for review

The user never needs to touch Gitea directly. The portal is their interface. But everything is backed by Gitea underneath — repos, issues, PRs, actions.
