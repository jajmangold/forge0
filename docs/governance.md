# Forge0 Governance Configuration

## Repository Limits

| Metric | Limit | Action |
|--------|-------|--------|
| Total repos | 50 | Archive oldest inactive |
| Repo size | 1GB | Split or optimize |
| Branches per repo | 20 | Auto-delete stale |
| Open issues per repo | 100 | Triage or close |
| Open PRs per repo | 10 | Review or close |
| Files per PR | 50 | Split into smaller PRs |
| Lines per PR | 500 | Split into smaller PRs |

## Branch Naming Convention

```
agent/<ticket>-<short-desc>      # Agent-created branches
feature/<ticket>-<short-desc>    # New features
fix/<ticket>-<short-desc>        # Bug fixes
docs/<topic>                     # Documentation
refactor/<component>             # Code refactoring
```

## Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description | When to Use |
|------|-------------|-------------|
| `feat` | New feature | Adding functionality |
| `fix` | Bug fix | Fixing issues |
| `docs` | Documentation | README, comments, ADRs |
| `test` | Tests | Adding/updating tests |
| `refactor` | Refactoring | Code restructuring |
| `perf` | Performance | Speed improvements |
| `chore` | Chores | Build, CI, tooling |
| `ci` | CI/CD | Pipeline changes |

## Label Taxonomy

### Type Labels
```
type:bug          # Bug reports
type:feature      # Feature requests
type:docs         # Documentation
type:refactor     # Code refactoring
type:test         # Test updates
type:chore        # Maintenance
```

### Priority Labels
```
priority:low      # Nice to have
priority:medium   # Normal priority
priority:high     # Important
priority:critical # Urgent
```

### Status Labels
```
status:triage     # Needs review
status:accepted   # Approved
status:in-progress # Working on it
status:review     # In review
status:blocked    # Waiting on something
status:done       # Completed
status:stale      # Inactive
```

### Component Labels
```
component:api     # API layer
component:ui      # User interface
component:infra   # Infrastructure
component:agent   # Agent system
```

## Issue Templates

### Required Fields

**Bug Report:**
- Description (required)
- Steps to Reproduce (required)
- Expected Behavior (required)
- Priority (required)

**Feature Request:**
- Problem (required)
- Proposed Solution (required)
- Priority (required)

### Auto-Labeling

| File Change | Label |
|-------------|-------|
| `src/**/*.py` | `component:api` |
| `*.yaml` | `component:infra` |
| `docs/**` | `type:docs` |
| `tests/**` | `type:test` |

## PR Requirements

### Required Sections
- Summary
- Related Issues (must link to issue)
- Checklist

### Required Labels
- `type:*` label
- `priority:*` label (for features)

### Validation
- Branch name must follow convention
- Commit messages must follow conventional format
- PR must link to related issue
- No merge conflicts

## Documentation Requirements

### Per-Repo
- README.md (auto-updated)
- CHANGELOG.md (auto-generated)
- LICENSE
- .gitignore

### Architecture Decision Records
- Location: `docs/adr/`
- Format: `NNN-title.md`
- Required for: architectural changes

## Stale Policy

### Issues
- Stale after 30 days of inactivity
- Closed after 7 more days
- Exempt: `priority:critical`, `status:blocked`

### PRs
- Stale after 14 days of inactivity
- Closed after 7 more days
- Exempt: `priority:critical`, `status:blocked`

### Branches
- Merged branches: auto-deleted
- Unmerged branches: deleted after 30 days
- Protected branches: never deleted

## Archive Policy

| Inactivity | Action |
|------------|--------|
| > 90 days | Label "archive-candidate" |
| > 180 days | Auto-archive |
| > 365 days | Auto-delete (with backup) |

## Enforcement

### Automated
- Gitea Actions validate PRs
- Stale cleanup runs weekly
- Documentation auto-updated
- Branches auto-cleaned

### Manual
- Monthly repo review
- Quarterly governance audit
- Annual archive review

## Docker Image Governance

### Base Image Extension

```
Official Base (maintained by vendor)
└── Forge0 Common Layer (maintained by fleet)
    └── Per-Repo Image (maintained by project)
```

### Rules

1. **No forked base images** — extend official or Forge0 common bases
2. **Pin all versions** — no :latest in Dockerfiles
3. **Use .dockerignore** — keep build context small
4. **Layer ordering** — deps before code
5. **Multi-stage builds** — separate build from runtime
6. **Store in package registry** — every image goes to Gitea
7. **Use BuildKit cache** — never rebuild unnecessarily
8. **Deterministic builds** — same input = same output
9. **Cleanup regularly** — prune unused images
10. **Document base choices** — why this base image?

### Package Registry

All images stored in Gitea's package registry:

```bash
# Push
docker tag myapp:latest localhost:3000/forge0/myapp:latest
docker push localhost:3000/forge0/myapp:latest

# Pull
docker pull localhost:3000/forge0/myapp:latest
```

### Build Cache Strategy

```dockerfile
# Layer 1: System deps (rarely changes)
RUN apt-get update && apt-get install -y curl

# Layer 2: Language deps (changes occasionally)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 3: App code (changes frequently)
COPY src/ /app/src/
```

### Anti-Thrashing Checklist

- [ ] No :latest tags in Dockerfiles
- [ ] .dockerignore configured
- [ ] Layer ordering correct
- [ ] Multi-stage builds used
- [ ] BuildKit cache enabled
- [ ] Images stored in registry
- [ ] Deterministic builds verified
