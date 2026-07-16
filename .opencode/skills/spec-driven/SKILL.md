---
name: spec-driven
description: Follow a spec-first development workflow — intake requirements, create spec.md, plan architecture, decompose into tasks, implement with TDD, review, and ship
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: development
---

## What I do

Implement the full spec-driven development workflow. Every feature starts with requirements, not code.

## When to use me

- Starting a new feature or project
- User provides a high-level goal or issue
- Need structured planning before implementation

## Workflow Phases

### 1. Intake (Understand the Task)

```bash
# Read the issue/request
# Identify the core problem
# List unknowns and assumptions
# Ask clarifying questions (max 5, one at a time)
```

Output: Clear problem statement in `spec.md`

### 2. Requirements (Define What)

```markdown
# spec.md

## Problem Statement
[What we're solving and why]

## Requirements
### Functional
- [ ] Requirement 1: [clear description]
- [ ] Requirement 2: [clear description]

### Non-Functional
- Performance: [specific targets]
- Security: [specific requirements]
- Scalability: [expected load]

## Acceptance Criteria
- [ ] Criterion 1: [measurable outcome]
- [ ] Criterion 2: [measurable outcome]

## Edge Cases
- [Edge case 1]
- [Edge case 2]

## Constraints
- [Technical constraints]
- [Resource constraints]
- [Time constraints]
```

### 3. Architecture (Define How)

```markdown
# plan.md

## Architecture Decisions
- [Decision 1]: [rationale]
- [Decision 2]: [rationale]

## Components
- [Component 1]: [responsibility]
- [Component 2]: [responsibility]

## Interfaces
- [Interface 1]: [contract]

## Data Flow
[Diagram or description]

## Dependencies
- [Dependency 1]: [why needed]
- [Dependency 2]: [why needed]

## Trade-offs
- [Trade-off 1]: [what we gain vs what we lose]
```

### 4. Decomposition (Break Into Tasks)

```markdown
# tasks.md

## Task 1: [Title]
- [ ] Subtask 1.1: [description]
- [ ] Subtask 1.2: [description]
- Files: [list of files to create/modify]
- Tests: [what tests are needed]
- Depends on: [other tasks]

## Task 2: [Title]
- [ ] Subtask 2.1: [description]
- [ ] Subtask 2.2: [description]
- Files: [list of files to create/modify]
- Tests: [what tests are needed]
- Depends on: [Task 1]
```

### 5. Implement (Code + Tests)

```bash
# For each task:
# 1. Write tests first (TDD)
# 2. Implement code
# 3. Run tests
# 4. Run linting
# 5. Commit with conventional commit
```

### 6. Review (Quality Gate)

```bash
# Run all tests
pytest

# Run linting
ruff check src/ tests/

# Run type checking
mypy src/

# Security scan
trailmark analyze src/ --summary
trailmark entrypoints src/

# Code review
# [Use reviewer agent]
```

### 7. Ship (Merge + Deploy)

```bash
# Create PR with structured description
# Link to spec.md, plan.md, tasks.md
# Request review
# Merge after approval
```

## Rules

- **Spec before code** — never start implementing without a spec
- **One question at a time** — don't overwhelm with multiple questions
- **Measurable criteria** — acceptance criteria must be testable
- **Document decisions** — future you needs context
- **TDD when possible** — write tests before code
- **Atomic commits** — one logical change per commit
- **Conventional commits** — `feat:`, `fix:`, `test:`, `refactor:`
- **Quality gates** — tests must pass before merge

## Templates

### spec.md Template

```markdown
# Specification: [Feature Name]

## Problem Statement
[What problem are we solving?]

## User Story
As a [user type], I want [feature] so that [benefit].

## Requirements
### Must Have
- [ ] [Requirement 1]

### Should Have
- [ ] [Requirement 2]

### Nice to Have
- [ ] [Requirement 3]

## Acceptance Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]

## Edge Cases
- [Edge case 1]
- [Edge case 2]

## Out of Scope
- [What we're NOT doing]
```

### plan.md Template

```markdown
# Architecture Plan: [Feature Name]

## Overview
[High-level approach]

## Architecture
[Diagram or description]

## Components
| Component | Responsibility | Owner |
|-----------|---------------|-------|
| [Name] | [What it does] | [Who] |

## Interfaces
[API contracts, data formats]

## Data Flow
[How data moves through the system]

## Dependencies
| Dependency | Version | Purpose |
|-----------|---------|---------|
| [Name] | [Version] | [Why] |

## Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk] | [Impact] | [Mitigation] |
```
