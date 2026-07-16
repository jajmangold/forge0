---
name: git-flow
description: Git automation with branch strategy, conventional commits, and structured PR creation
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: git
---

## What I do

Automate git workflows with consistent branch naming, conventional commits, and structured PR descriptions.

## When to use me

- Creating branches for features/fixes
- Writing commit messages
- Creating pull requests
- Managing git history

## Branch Strategy

```
agent/<ticket>-<short-desc>
```

Examples:
- `agent/42-password-reset`
- `agent/123-api-optimization`

## Conventional Commits

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding tests |
| `refactor` | Code restructuring (no feature/fix) |
| `perf` | Performance improvement |
| `chore` | Build/tooling changes |
| `ci` | CI/CD changes |

### Examples

```bash
git commit -m "feat(auth): add JWT token refresh endpoint"
git commit -m "fix(api): handle null response from external service"
git commit -m "test(auth): add unit tests for token validation"
git commit -m "refactor(db): extract query builder to separate module"
```

## PR Description Template

```markdown
## Summary
[One-line description of what this PR does]

## Changes
- [Change 1]
- [Change 2]
- [Change 3]

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Related Issues
Closes #42

## AI Review
[Automated review summary]
```

## Workflow

```bash
# 1. Create branch
git checkout -b agent/42-feature-name

# 2. Make changes with conventional commits
git add .
git commit -m "feat(module): add new functionality"

# 3. Push and create PR
git push -u origin agent/42-feature-name

# 4. Create PR with structured description
gh pr create --title "feat: Add feature name" --body-file pr-template.md
```

## Rules

- **Always use branch prefix** — `agent/` for agent-created branches
- **One logical change per commit** — don't mix unrelated changes
- **Reference issues** — use `Closes #N` in commit/PR body
- **Conventional commits** — always use the format above
- **Atomic commits** — one feature/fix per commit
- **Sign commits** — use `--signoff` when appropriate
