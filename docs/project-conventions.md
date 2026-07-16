# Forge0 Project Conventions

Standard folder structure for all Forge0-managed projects.

## Repository Layout

```
project-name/
  .forge0/                        # Workflow metadata (machine-readable)
    project.yaml                  # Project config & status
    workflow.yaml                 # Current phase & state
    knowledge/                    # Accumulated project knowledge
      decisions.md                # Architecture decisions log
      assumptions.md              # Agent assumptions (approved/rejected)
    specs/                        # Per-feature specifications
      REQ-001-initial-build/      # Feature directory (named after requirement)
        requirement.md            # Structured spec
        architecture.md           # Tech decisions for this feature
        tasks/                    # Task breakdown
          TASK-001-setup-project.md
          TASK-002-implement-auth.md
          TASK-003-create-api.md
  
  AGENTS.md                       # Agent instructions (project-specific)
  README.md                       # Auto-generated project overview
  
  src/                            # Source code
  tests/                          # Tests
  public/                         # Static assets (if applicable)
  .github/                        # CI/CD workflows
    workflows/
      ci.yaml                     # Lint + test on PR
```

## .forge0/project.yaml

```yaml
id: "proj-20260715-001"
name: "Portfolio Website"
type: greenfield                    # greenfield | feature | enhancement
status: active                      # pending | active | paused | complete
created: 2026-07-15T19:30:00Z
updated: 2026-07-15T19:30:00Z

# LLM config (overrides env vars for this project)
llm:
  primary_model: kimi-k2.7-code
  critic_model: deepseek-v4-flash

# Tech stack (determined during architecture phase)
stack:
  framework: nextjs
  language: typescript
  database: sqlite
  hosting: docker
```

## .forge0/workflow.yaml

```yaml
current_phase: requirements         # intake | requirements | architecture | tasks | implementation | review
phase_status: in-progress           # pending | in-progress | complete | failed

phases:
  intake:
    status: complete
    completed_at: 2026-07-15T19:30:00Z
  
  requirements:
    status: in-progress
    started_at: 2026-07-15T19:31:00Z
    artifacts:
      - path: specs/REQ-001-initial-build/requirement.md
        status: draft               # draft | in-review | approved | complete
  
  architecture:
    status: pending
  
  tasks:
    status: pending
  
  implementation:
    status: pending
  
  review:
    status: pending
```

## .forge0/knowledge/decisions.md

```markdown
# Architecture Decisions

## 2026-07-15: Use Next.js App Router
- **Decision:** Next.js 14+ with App Router
- **Rationale:** Server components for SEO, API routes for backend, good DX
- **Alternatives considered:** Remix, SvelteKit
- **Approved by:** user

## 2026-07-15: SQLite for MVP
- **Decision:** SQLite via Drizzle ORM
- **Rationale:** Zero infra, easy migration to Postgres later, good for single-server
- **Alternatives considered:** PostgreSQL, Supabase
- **Approved by:** user
```

## .forge0/knowledge/assumptions.md

```markdown
# Agent Assumptions

## 2026-07-15: Auth uses email/password
- **Assumption:** User wants email/password auth, not OAuth
- **Status:** approved (user confirmed)
- **Context:** User said "simple login"

## 2026-07-15: No mobile app needed
- **Assumption:** This is web-only, no native mobile
- **Status:** approved (user confirmed)
- **Context:** User said "website", not "app"
```

## Spec Directory Naming

Format: `REQ-{NNN}-{kebab-case-title}/`

- `REQ-001-initial-build/`
- `REQ-002-add-authentication/`
- `REQ-003-payment-integration/`

Task files within: `TASK-{NNN}-{kebab-case-description}.md`

## Task File Format

```markdown
---
id: TASK-001
title: "Setup Project"
requirement: REQ-001
status: pending           # pending | in-progress | complete | failed
dependencies: []          # other task IDs
complexity: simple        # simple | moderate | complex
created: 2026-07-15
---

## Description

Initialize the Next.js project with TypeScript, Tailwind CSS, and basic folder structure.

## Acceptance Criteria

- [ ] `npx create-next-app` runs successfully
- [ ] TypeScript configured with strict mode
- [ ] Tailwind CSS working
- [ ] Basic folder structure matches architecture.md
- [ ] `npm run dev` starts without errors
- [ ] Landing page renders at localhost:3000

## Files to Create/Modify

- `package.json`
- `tsconfig.json`
- `tailwind.config.ts`
- `src/app/layout.tsx`
- `src/app/page.tsx`

## Notes

Use the App Router pattern from architecture.md.
```

## AGENTS.md (per-project)

Each project gets an `AGENTS.md` at the root. This follows the emerging standard (adopted by 40,000+ projects) and tells any AI agent how to work within this project.

```markdown
# AGENTS.md

## Project Context
[Brief description from requirement.md]

## Tech Stack
[From architecture.md]

## Conventions
- Language: TypeScript (strict)
- Style: Tailwind CSS
- Testing: Vitest
- Linting: ESLint + Prettier
- Commits: Conventional Commits format

## Workflow
This project is managed by Forge0. See `.forge0/` for specs and workflow state.
Do not skip phases. Follow the task order in `.forge0/specs/*/tasks/`.

## Key Files
- `.forge0/workflow.yaml` — current phase
- `.forge0/specs/` — requirements and tasks
- `AGENTS.md` — this file
```

## Gitea Integration

- Each project is a Gitea repo under the `agent` user
- Tasks from `TASK-*.md` are mirrored as Gitea issues
- Issue labels: `task`, `REQ-NNN`, `complexity:simple|moderate|complex`
- PRs are created when all tasks for a requirement are complete
- Actions run lint + tests on every push

## Portal Integration

The portal reads `.forge0/workflow.yaml` to show:
- Which phase each project is in
- What artifacts exist
- What's pending human input
- Task progress (from issue status)
