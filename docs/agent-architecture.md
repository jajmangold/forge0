# Forge0 Agent Architecture

## Overview

Forge0 uses OpenCode's native primitives — **skills**, **agents**, **rules**, and **permissions** — to build an AI agent-driven development platform. No custom orchestration engine needed.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    OpenCode Runtime                       │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   AGENTS.md   │  │  opencode.json│  │    Skills    │  │
│  │  (Rules)      │  │  (Agents)     │  │  (Reusable)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
        │                 │                  │
        ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                    Agent Pool                             │
├─────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │ Planner │  │ Coder   │  │Reviewer │  │ Security│   │
│  │ (read)  │  │ (full)  │  │ (read)  │  │ (read)  │   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │TestWrit │  │Orchestr │  │ Explorer│  │ Scout   │   │
│  │ (write) │  │ (full)  │  │ (read)  │  │ (read)  │   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. AGENTS.md (Rules)

Always-loaded context for every agent session. Contains:
- Project conventions
- Build/lint/test commands
- Architecture overview
- Coding standards

### 2. opencode.json (Agent Definitions)

Defines specialized agents with constrained permissions:
- **planner** — Read-only, analyzes requirements
- **coder** — Full tool access, implements code
- **reviewer** — Read-only, reviews code quality
- **security** — Read-only, checks vulnerabilities
- **test-writer** — Can write tests, run test suites
- **orchestrator** — Coordinates workflow, delegates tasks

### 3. Skills (Reusable Behavior)

On-demand modules loaded via the `skill` tool:
- **spec-driven** — Full development workflow
- **edit-format** — SEARCH/REPLACE block editing
- **security-scan** — Run security tools
- **test-gen** — Generate test suites
- **git-flow** — Branch strategy, commits, PRs

## Workflow

### Spec-Driven Development Flow

```
User Issue → [Planner Agent]
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
    [Spec]  [Arch]  [Tasks]
         │      │      │
         └──────┼──────┘
                ▼
         [Coder Agent]
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
    [Edit]  [Test]  [Commit]
         │      │      │
         └──────┼──────┘
                ▼
         [Reviewer Agent]
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
    [Review] [Fix]  [PR]
         │      │      │
         └──────┼──────┘
                ▼
         [Security Agent]
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
    [Scan]  [Report] [Merge]
```

### Agent Permissions

| Agent | read | edit | bash | skill | task |
|-------|------|------|------|-------|------|
| planner | allow | deny | deny | allow | allow |
| coder | allow | allow | allow | allow | deny |
| reviewer | allow | deny | deny | allow | deny |
| security | allow | deny | deny | allow | deny |
| test-writer | allow | allow | allow | allow | deny |
| orchestrator | allow | allow | allow | allow | allow |

### Skill Permissions

| Skill | Access | Description |
|-------|--------|-------------|
| spec-driven | allow | Full development workflow |
| edit-format | allow | SEARCH/REPLACE editing |
| security-scan | allow | Run security tools |
| test-gen | allow | Generate tests |
| git-flow | allow | Git automation |

## Implementation

### File Structure

```
.opencode/
├── opencode.json          # Agent definitions
├── agents/
│   ├── planner.md         # Planner agent
│   ├── coder.md           # Coder agent
│   ├── reviewer.md        # Reviewer agent
│   ├── security.md        # Security agent
│   ├── test-writer.md     # Test writer agent
│   └── orchestrator.md    # Orchestrator agent
└── skills/
    ├── spec-driven/
    │   └── SKILL.md       # Development workflow
    ├── edit-format/
    │   └── SKILL.md       # File editing
    ├── security-scan/
    │   └── SKILL.md       # Security scanning
    ├── test-gen/
    │   └── SKILL.md       # Test generation
    └── git-flow/
        └── SKILL.md       # Git automation

AGENTS.md                   # Project conventions (root)
```

## Benefits

1. **No custom engine** — Leverages OpenCode's battle-tested primitives
2. **Permission-based safety** — Agents can only do what they're allowed
3. **Modular skills** — Reusable behavior modules
4. **Observation-driven** — Agents see their own consequences
5. **Git-native** — Everything tracked in version control
6. **Portable** — Works with any OpenCode provider

## References

- OpenCode Skills: https://opencode.ai/docs/skills
- OpenCode Agents: https://opencode.ai/docs/agents
- OpenCode Rules: https://opencode.ai/docs/rules
- OpenCode Permissions: https://opencode.ai/docs/permissions
