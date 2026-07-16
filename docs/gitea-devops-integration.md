# Gitea Integration

How Forge0 uses Gitea for the full devops practice. Issues, branches, CI, wiki, webhooks.

## Gitea as the Source of Truth

Everything lives in Gitea:
- **Repos** — source code + specs + tests
- **Issues** — work items (derived from task files)
- **Pull Requests** — code review + CI gate
- **Actions** — CI/CD pipelines
- **Wiki** — project documentation
- **Webhooks** — event-driven agent triggers

## Issues: Work Items

### Issue lifecycle

```
created → in-progress → review → done → closed
```

### Issue creation

When a requirement is approved, the Backlog Agent creates issues from the decomposition:

```
Title: [REQ-001] Implement password hashing
Labels: task, REQ-001, complexity:simple
Milestone: REQ-001 - Initial Build
Description:
  Functions: hash_password, verify_password
  Branch: feature/REQ-001-task-001-password-hashing
  
  Acceptance Criteria:
  - [ ] hash_password returns a string
  - [ ] Different hashes for same input (salt)
  - [ ] verify_password returns True for correct password
  - [ ] verify_password returns False for wrong password
  
  Dependencies: none
```

### Issue linking

- Issues link to their parent requirement via label (`REQ-NNN`)
- Issues link to their PR via Gitea's built-in PR-issue linking
- Issues link to their task file via the description

### Issue automation

| Event | Agent Action |
|---|---|
| Requirement approved | Create task issues |
| Task branch created | Move issue to `in-progress` |
| PR opened | Move issue to `review` |
| PR merged | Move issue to `done`, close issue |
| CI fails on PR | Add `blocked` label, comment with analysis |
| Stale (7 days no activity) | Comment, suggest cleanup |

## Branches: One per Task

### Branch naming

```
feature/{REQ-ID}-task-{TASK-ID}-{kebab-title}
fix/{REQ-ID}-task-{TASK-ID}-{description}
hotfix/{description}
```

Examples:
```
feature/REQ-001-task-001-password-hashing
feature/REQ-001-task-002-user-management
fix/REQ-002-task-001-fix-login-redirect
```

### Branch lifecycle

1. Created from `main` when task starts
2. Agent commits function+test pairs
3. CI runs on every push
4. PR opened when task complete
5. Reviewed (critic + human)
6. Merged to `main`
7. Deleted

### Branch protection (configured in Gitea)

```yaml
# Branch protection rules for 'main'
- Require pull request before merging
- Require approvals: 1 (can be critic agent)
- Require status checks to pass:
  - pytest (tests must pass)
  - lint (code must be clean)
  - coverage (must meet threshold)
- Do not allow bypassing the above
- Require linear history (no merge commits)
- Delete branch after merge
```

## Pull Requests: Code Review

### PR creation

When all functions in a task are implemented, the Implementation Agent opens a PR:

```
Title: [REQ-001] Implement password hashing
Description:
  Implements TASK-001: password hashing functions
  
  Functions implemented:
  - hash_password(plain: str) -> str
  - verify_password(plain: str, hash: str) -> bool
  
  Tests: 6 tests, all passing
  Coverage: 100% for new code
  
  Closes #42
```

The `Closes #42` syntax auto-closes the issue on merge.

### PR review process

1. **CI runs automatically** (Gitea Actions)
2. **Critic agent reviews** (via webhook → portal → agent → comment on PR)
3. **Human reviews** (can see specs, tests, code, and critic feedback)
4. **If approved:** merge to main
5. **If changes requested:** agent reworks on the branch

### PR diff structure

A well-structured PR shows the TDD history:
```
commit 1: test_hash_password + hash_password implementation
commit 2: test_verify_password + verify_password implementation
```

Each commit is self-contained: test + code together.

## Actions: CI/CD

### CI pipeline (runs on every PR)

```yaml
# .forge0/ci.yaml
name: CI
on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -e ".[test]"
      
      - name: Lint
        run: ruff check src/ tests/
      
      - name: Type check
        run: mypy src/ --ignore-missing-imports
      
      - name: Tests
        run: pytest tests/ -v --tb=short
      
      - name: Coverage
        run: pytest --cov=src --cov-report=term-missing --cov-fail-under=80
      
      - name: Test-code correspondence
        run: |
          # Verify every src/ file has a corresponding test
          python .forge0/scripts/check-test-coverage.py
```

### Test-code correspondence check

A custom script verifies that every function in `src/` has a corresponding test:

```python
# .forge0/scripts/check-test-coverage.py
"""Verify every source file has a corresponding test file."""
import sys
from pathlib import Path

src_files = set(Path("src").rglob("*.py"))
test_files = set(Path("tests").rglob("test_*.py"))

missing = []
for src in src_files:
    expected_test = Path("tests") / f"test_{src.name}"
    if expected_test not in test_files:
        missing.append(f"  {src} -> missing {expected_test}")

if missing:
    print("ERROR: Source files without tests:")
    for m in missing:
        print(m)
    sys.exit(1)

print("All source files have corresponding tests.")
```

### CD pipeline (runs on merge to main)

```yaml
# .forge0/cd.yaml
name: CD
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Update wiki
        run: python .forge0/scripts/update-wiki.py
      
      - name: Generate changelog
        run: python .forge0/scripts/generate-changelog.py
```

## Wiki: Auto-Managed Documentation

Gitea's wiki is a git repo. The Documentation Agent maintains it via the Gitea API.

### Wiki pages

| Page | Updated When | Content |
|---|---|---|
| Home | On project creation, weekly | Project overview, status dashboard |
| Architecture | On architecture change | Tech stack, patterns, decisions |
| API-Reference | On merge | Auto-generated from docstrings |
| Changelog | On merge | Auto-generated from conventional commits |
| Development | On convention change | How to contribute, coding standards |
| Status | Weekly | Test coverage, open issues, velocity |
| Research/{topic} | On-demand + monthly refresh | Deep research by topic (payments, auth, etc.) |
| Monitoring/dependencies | Weekly | Dependency versions + available updates |
| Monitoring/security | Daily | Active security advisories |
| Monitoring/tech-radar | Monthly | Technology landscape for the stack |

Research and monitoring pages are maintained by the Research Agent. See `research-agents.md` for details.

### Status dashboard (in wiki)

The Documentation Agent generates a markdown dashboard:

```markdown
# Project Status

Last updated: 2026-07-15

## Progress
| Requirement | Tasks | Done | Progress |
|---|---|---|---|
| REQ-001 Initial Build | 4 | 2 | ██████░░░░ 50% |
| REQ-002 Authentication | 3 | 0 | ░░░░░░░░░░ 0% |

## Quality
- Test coverage: 87%
- Open issues: 5
- Failed CI runs (7d): 0
- Avg time to merge: 2.3 hours

## Recent Activity
- 2026-07-15: Merged TASK-002 (user management)
- 2026-07-15: Merged TASK-001 (password hashing)
- 2026-07-14: Architecture approved for REQ-001
```

## Webhooks: Event-Driven Agents

Gitea sends webhooks to the portal on key events. The portal dispatches to the appropriate agent.

### Webhook configuration

Set up in Gitea repo settings → Webhooks:

```
URL: http://forge0-portal:3001/api/webhooks/gitea
Content type: application/json
Secret: <shared secret>
Events:
  - Push events
  - Pull request events
  - Issue events
  - Workflow run events
```

### Webhook → Agent mapping

| Gitea Event | Agent | Action |
|---|---|---|
| `workflow_run` (failed) | Pipeline Watcher | Analyze failure, comment on PR |
| `workflow_run` (success) | Pipeline Watcher | Update task status |
| `pull_request` (opened) | Critic Agent | Review code, comment |
| `pull_request` (merged) | Documentation Agent | Update wiki, changelog |
| `issues` (opened) | Backlog Agent | Label, prioritize |
| `issues` (closed) | Backlog Agent | Update requirement progress |
| `push` (to main) | Documentation Agent | Update API docs |

### Webhook handler (portal side)

```python
# In portal/app/main.py (future addition)
@app.post("/api/webhooks/gitea")
async def gitea_webhook(request: Request):
    event = request.headers.get("X-Gitea-Event")
    payload = await request.json()
    
    # Verify signature
    if not verify_gitea_signature(request):
        return {"error": "invalid signature"}, 401
    
    # Dispatch to appropriate agent
    if event == "workflow_run":
        await dispatch_to_pipeline_watcher(payload)
    elif event == "pull_request":
        await dispatch_to_critic_or_docs(payload)
    elif event == "issues":
        await dispatch_to_backlog_agent(payload)
    
    return {"ok": True}
```

## Gitea API Usage

### Create issue
```bash
curl -X POST http://localhost:3000/api/v1/repos/agent/project/issues \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "[REQ-001] Implement password hashing",
    "body": "Functions: hash_password, verify_password\n\nCloses when PR merges.",
    "labels": [{"name": "task"}, {"name": "REQ-001"}, {"name": "complexity:simple"}]
  }'
```

### Create PR
```bash
curl -X POST http://localhost:3000/api/v1/repos/agent/project/pulls \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "[REQ-001] Implement password hashing",
    "head": "feature/REQ-001-task-001-password-hashing",
    "base": "main",
    "body": "Implements TASK-001.\n\nCloses #42"
  }'
```

### Update wiki
```bash
curl -X PUT http://localhost:3000/api/v1/repos/agent/project/wiki/pages/Status \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Status",
    "content_base64": "<base64 encoded markdown>",
    "message": "docs: update project status"
  }'
```
