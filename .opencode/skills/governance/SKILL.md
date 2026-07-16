---
name: governance
description: Enforce work item hygiene, git hygiene, automatic documentation, and prevent sprawl across the Forge0 fleet
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: governance
---

## What I do

Enforce consistency and prevent sprawl across the Forge0 fleet. Automate documentation, enforce hygiene, and keep the system clean.

## When to use me

- Creating new issues, PRs, or repos
- Reviewing code changes
- Managing project documentation
- Cleaning up stale work items
- Preventing repository sprawl

## Work Item Hygiene

### Issue Templates

Every repo should have issue templates in `.gitea/ISSUE_TEMPLATE/`:

```yaml
# .gitea/ISSUE_TEMPLATE/bug.yaml
name: Bug Report
description: Report a bug
labels: ["type:bug", "status:triage"]
body:
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What happened?
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Steps to Reproduce
      description: How can we reproduce this?
    validations:
      required: true
  - type: dropdown
    id: priority
    attributes:
      label: Priority
      options:
        - low
        - medium
        - high
        - critical
    validations:
      required: true
```

```yaml
# .gitea/ISSUE_TEMPLATE/feature.yaml
name: Feature Request
description: Suggest a new feature
labels: ["type:feature", "status:triage"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What problem does this solve?
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How should we solve it?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: What other approaches did you consider?
```

### PR Template

```markdown
# .gitea/PULL_REQUEST_TEMPLATE.md

## Summary
[One-line description]

## Changes
- [ ] Change 1
- [ ] Change 2

## Related Issues
Closes #N

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Changelog updated (if user-facing)
- [ ] No breaking changes (or documented)
- [ ] Branch follows naming convention
- [ ] Commits follow conventional format
```

### Label Taxonomy

```
# Type
type:bug
type:feature
type:docs
type:refactor
type:test
type:chore

# Priority
priority:low
priority:medium
priority:high
priority:critical

# Status
status:triage
status:accepted
status:in-progress
status:review
status:blocked
status:done

# Component
component:api
component:ui
component:infra
component:agent

# Source
source:agent
source:human
source:automated
```

## Git Hygiene

### Branch Naming

```
agent/<ticket>-<short-desc>
feature/<ticket>-<short-desc>
fix/<ticket>-<short-desc>
docs/<topic>
refactor/<component>
```

### Commit Messages

```
<type>(<scope>): <description>

[optional body]

[optional footer]

Closes #42
```

### Branch Protection Rules

```yaml
# .gitea/workflows/branch-protection.yaml
name: Branch Protection
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Check branch naming
        run: |
          BRANCH="${{ github.head_ref }}"
          if [[ ! "$BRANCH" =~ ^(agent|feature|fix|docs|refactor)/ ]]; then
            echo "❌ Branch must follow naming convention: agent/, feature/, fix/, docs/, refactor/"
            exit 1
          fi

      - name: Check commit messages
        run: |
          git log origin/main..HEAD --format="%s" | while read msg; do
            if [[ ! "$msg" =~ ^(feat|fix|docs|test|refactor|perf|chore|ci)(\(.+\))?: ]]; then
              echo "❌ Commit message must follow conventional commits: $msg"
              exit 1
            fi
          done
```

### Squash Merge Only

Configure in Gitea repo settings:
- Allow merge commits: ❌
- Allow rebase merging: ❌
- Allow squash merging: ✅
- Delete branch after merge: ✅

## Automatic Documentation

### Changelog Generation

```yaml
# .gitea/workflows/changelog.yaml
name: Auto Changelog
on:
  push:
    branches: [main]

jobs:
  changelog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate Changelog
        run: |
          # Get conventional commits since last tag
          LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
          if [ -n "$LAST_TAG" ]; then
            COMMITS=$(git log $LAST_TAG..HEAD --format="%s" --no-merges)
          else
            COMMITS=$(git log --format="%s" --no-merges)
          fi

          # Parse into categories
          FEATS=$(echo "$COMMITS" | grep "^feat" || true)
          FIXES=$(echo "$COMMITS" | grep "^fix" || true)
          DOCS=$(echo "$COMMITS" | grep "^docs" || true)

          # Generate CHANGELOG.md
          cat > CHANGELOG.md << EOF
          # Changelog

          ## [Unreleased]

          ### Features
          $FEATS

          ### Bug Fixes
          $FIXES

          ### Documentation
          $DOCS
          EOF
```

### README Auto-Update

```yaml
# .gitea/workflows/readme.yaml
name: Auto README
on:
  push:
    branches: [main]
    paths:
      - 'src/**/*.py'
      - 'pyproject.toml'

jobs:
  readme:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Update README
        run: |
          # Auto-generate API section from code
          python scripts/generate_readme.py > README.md
```

### Architecture Decision Records (ADRs)

```markdown
# docs/adr/001-use-fastapi.md

# ADR: Use FastAPI

## Status
Accepted

## Context
We need a high-performance async Python web framework.

## Decision
Use FastAPI for all new API services.

## Consequences
+ High performance with async/await
+ Automatic OpenAPI documentation
+ Type safety with Pydantic
- Smaller ecosystem than Flask/Django
```

## Preventing Sprawl

### Repo Naming Convention

```
forge0/<service-name>
```

Examples:
- `forge0/portal`
- `forge0/agent-core`
- `forge0/docs`

### Max Repo Limits

| Category | Limit | Action |
|----------|-------|--------|
| Total repos | 50 | Archive oldest inactive |
| Repo size | 1GB | Split or optimize |
| Branches per repo | 20 | Auto-delete stale |
| Open issues per repo | 100 | Triage or close |
| Open PRs per repo | 10 | Review or close |

### Stale Cleanup

```yaml
# .gitea/workflows/stale.yaml
name: Stale Cleanup
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - name: Close stale issues
        uses: actions/stale@v9
        with:
          days-before-stale: 30
          days-before-close: 7
          stale-issue-label: 'status:stale'
          exempt-issue-labels: 'priority:critical,status:blocked'

      - name: Delete stale branches
        run: |
          git fetch --prune
          git branch -r --merged origin/main | grep -v main | while read branch; do
            git push origin --delete "${branch#origin/}" || true
          done
```

### Repo Archive Policy

```
Inactive > 90 days → Label "archive candidate"
Inactive > 180 days → Auto-archive
Inactive > 365 days → Auto-delete (with backup)
```

## Governance Rules

1. **Every issue needs**: type, priority, status labels
2. **Every PR needs**: linked issue, tests, docs update
3. **Every commit needs**: conventional format
4. **Every branch needs**: proper naming convention
5. **Every repo needs**: README, LICENSE, .gitignore
6. **No orphaned repos**: every repo has an owner
7. **No stale work**: clean up monthly
8. **No undocumented decisions**: use ADRs
