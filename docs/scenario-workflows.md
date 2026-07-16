# Forge0 Scenario Workflows

All three scenarios: greenfield, existing project, external project.

## The Three Scenarios

| Scenario | User says | Starting context | Output |
|---|---|---|---|
| **Greenfield** | "I need a website" | Nothing | New repo + code + tests |
| **Existing Forge0** | "Add dark mode" / "Fix the bug" | .forge0/ + codebase | Incremental change |
| **External project** | "Here's my GitHub repo" | Raw codebase | Analysis + scaffold |

## Scenario 1: Greenfield

*Documented in `greenfield-workflow.md`.*

```
INTAKE → REQUIREMENTS → ARCHITECTURE → DECOMPOSITION → TDD → REVIEW → MERGE
```

User starts from nothing. Full requirements elicitation. New repo created.

---

## Scenario 2: Existing Forge0 Project

The repo already exists. There's a `.forge0/` directory with specs, knowledge, conventions. There's code, tests, CI. The user comes in with a new request.

### 2A: Feature Request

**User says:** "Add dark mode", "Add an API endpoint", "I need user profiles"

**Flow:** Requirements (shorter) → Architecture (update if needed) → Decomposition → TDD → Review

**Why it's different from greenfield:**
- Agent already knows the tech stack, conventions, patterns
- Requirements elicitation is faster (agent knows what questions to skip)
- Decomposition must account for existing code (don't recreate what exists)
- New code integrates with existing modules
- New tests must not break existing tests

**Agent context (assembled dynamically):**
```
System prompt (base)
+ .forge0/project.yaml
+ .forge0/workflow.yaml
+ .forge0/knowledge/decisions.md
+ .forge0/knowledge/assumptions.md
+ architecture.md
+ AGENTS.md
+ relevant source code (agent determines what's relevant)
+ existing test files (to understand patterns)
```

**Example:**

User: "Add dark mode to the website"

Agent reads existing code, finds the CSS/styling setup, understands the component structure.

Agent asks: "I see you're using Tailwind CSS. Should dark mode be a toggle in the header, or follow the system preference? Should it persist across sessions?"

(Much shorter than greenfield because the agent already knows the stack.)

Agent creates REQ-002, decomposes into tasks (add theme toggle component, update CSS variables, add persistence, add tests), implements via TDD.

**Gitea integration:**
- New issues created for REQ-002 tasks
- New branch per task: `feature/REQ-002-task-001-theme-toggle`
- PRs merged to main
- Wiki updated with new feature docs

---

### 2B: Bug Report

**User says:** "Login doesn't work", "Page crashes on mobile", "The API returns 500"

**Flow:** Reproduce → Diagnose → Fix → Review

**This is NOT the feature workflow.** Bugs follow a different path.

**Phase 1: REPRODUCE**

Agent writes a test that reproduces the bug:

```python
# tests/test_login_bug.py
def test_login_returns_500_on_empty_password(client):
    """Bug: login endpoint returns 500 when password is empty."""
    response = client.post("/api/login", json={
        "email": "user@example.com",
        "password": ""
    })
    assert response.status_code == 400  # Should be 400, not 500
```

The test FAILS (confirms the bug exists).

**Phase 2: DIAGNOSE**

Agent investigates:
- Reads the login handler code
- Traces the error path
- Identifies root cause (e.g., missing validation)

**Phase 3: FIX**

Agent fixes the code:

```python
# src/auth.py
def login(email: str, password: str) -> Token:
    if not password:  # ← added this check
        raise ValueError("Password cannot be empty")
    # ... rest of login logic
```

Test now PASSES.

**Phase 4: REVIEW**

Agent opens PR with:
- The bug reproduction test
- The fix
- Explanation of root cause

**Gitea integration:**
- Issue created: `[BUG] Login returns 500 on empty password`
- Label: `bug`
- Branch: `fix/login-empty-password`
- PR: "Fixes #43" (auto-closes issue on merge)

---

### 2C: Refactoring

**User says:** "Clean up the auth module", "Extract this into a service", "Simplify the API handlers"

**Flow:** Understand → Plan → Refactor → Review

**Key constraint:** All existing tests must pass at every step. No behavior change.

**Phase 1: UNDERSTAND**

Agent reads the target code + its tests. Understands:
- What does this code do?
- What are its dependencies?
- What tests cover it?
- What patterns does it follow?

**Phase 2: PLAN**

Agent proposes refactoring approach:
- What will change structurally
- What will NOT change behaviorally
- Step-by-step plan

**Phase 3: REFACTOR**

Agent makes changes incrementally. After each change:
- Run all tests (must pass)
- If tests fail: revert that change, try different approach

**Phase 4: REVIEW**

Agent opens PR with:
- Before/after comparison
- Confirmation that all tests still pass
- Explanation of structural improvements

**Gitea integration:**
- Issue: `[REFACTOR] Extract auth into separate service`
- Label: `refactor`
- Branch: `refactor/extract-auth-service`
- CI: all existing tests must pass

---

### 2D: Investigation

**User says:** "Why is this slow?", "How does the auth flow work?", "What happens when X?"

**Flow:** Read → Explain

**No code changes.** Agent reads code, explains.

**Agent produces:**
- Explanation of the relevant code
- Diagram (if helpful, as text/mermaid)
- Suggestions (if the agent sees issues)

**Gitea integration:**
- Optionally: agent adds explanation to wiki
- No branch, no PR, no code changes

---

### 2E: Documentation

**User says:** "Update the README", "Add API docs", "Document the auth flow"

**Flow:** Read → Generate docs → Review

**Agent reads code, generates/updates documentation.**

**Gitea integration:**
- Branch: `docs/update-api-reference`
- Changes: wiki pages, README, docstrings
- PR for review

---

## Scenario 3: External Project

User has a repo somewhere else (GitHub, GitLab, Bitbucket, any git remote). They want Forge0's help.

Forge0 can interact with external repos in multiple ways:
- **Pull mirror** — import and periodically sync from external
- **Push mirror** — push changes back to external
- **Direct remote** — push specific branches without mirroring
- **Bidirectional** — sync both ways (Forge0 is authoritative)

See `external-repo-interaction.md` for full details on mirroring, credentials, and platform support.

### 3A: Import and Work

**User says:** "Here's my GitHub repo, add a feature", "Can you help with this codebase?"

**Flow:** Clone → Analyze → Scaffold → Present → (becomes existing project) → Work → Push back

**Phase 1: CLONE (pull mirror)**

Agent creates a pull mirror in Gitea:
```bash
# Create a pull mirror from GitHub
curl -X POST http://localhost:3000/api/v1/repos/migrate \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clone_addr": "https://github.com/user/repo.git",
    "repo_name": "my-project",
    "repo_owner": "agent",
    "mirror": true,
    "auth_username": "github-user",
    "auth_token": "ghp_xxxx"
  }'
```

This creates a local copy that periodically syncs from GitHub.

**Phase 2: ANALYZE**

Agent does what a senior developer does when joining a new project:

1. **High-level scan:**
   - What language(s)? What framework(s)?
   - Directory structure?
   - README? package.json? requirements.txt?
   - CI already? (.github/workflows?)

2. **Code analysis:**
   - Entry points?
   - Main modules?
   - Patterns used? (MVC, services, etc.)
   - Test setup? Coverage?

3. **Quality assessment:**
   - Are there tests? How many?
   - Linting configured?
   - Type checking?
   - Known issues? (open GitHub issues)

**Phase 3: SCAFFOLD**

Agent creates `.forge0/` structure:

```yaml
# .forge0/project.yaml
id: "proj-imported-001"
name: "Imported Project"
type: external
status: active
imported_from: "https://github.com/user/repo"
imported_at: "2026-07-15"

stack:
  framework: "express"
  language: "javascript"
  database: "postgresql"
  testing: "jest"  # or "none" if no tests
```

```yaml
# .forge0/workflow.yaml
current_phase: analysis
phase_status: complete

phases:
  analysis:
    status: complete
    findings: "Express.js API with PostgreSQL, minimal tests"
```

```markdown
# .forge0/knowledge/decisions.md
## Discovered: Express.js with PostgreSQL
- Found in: package.json, docker-compose.yml
- ORM: Sequelize
- Auth: JWT (jsonwebtoken)
- Testing: Jest (3 test files found)
```

**Phase 4: PRESENT**

Agent presents findings to user:

> "Here's what I found:
> - **Stack:** Express.js + PostgreSQL + Sequelize ORM
> - **Tests:** 3 test files, low coverage (~15%)
> - **CI:** None configured
> - **Issues I noticed:**
>   - No input validation on the API endpoints
>   - SQL queries are string concatenation (SQL injection risk)
>   - No error handling middleware
>
> Want me to:
> 1. Add tests for existing code?
> 2. Fix the security issues?
> 3. Add a feature?"

**Phase 5: Transition to existing project**

Now it has `.forge0/` context. Can proceed with any existing project workflow (feature, bug, refactor, etc.).

**Phase 6: PUSH BACK (when work is done)**

When the agent completes work and it's merged to main, the user can push changes back to the external repo:

```bash
# Configure push mirror to GitHub
curl -X POST http://localhost:3000/api/v1/repos/agent/my-project/push_mirrors \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "push_mirror_add": {
      "remote_address": "https://github.com/user/repo.git",
      "remote_username": "github-user",
      "remote_password": "ghp_xxxx",
      "sync_on_commit": true
    }
  }'
```

Or push a specific branch for a PR:
```bash
# Agent pushes feature branch to user's GitHub fork
git remote add github https://github.com/user/repo.git
git push github feature/REQ-001-dark-mode
```

The user then creates a PR on GitHub from the pushed branch.

See `external-repo-interaction.md` for full details on mirroring modes, credentials, and platform support.

---

### 3B: Quick Question

**User says:** "Look at this code and tell me why it's broken", "Review this PR"

**Flow:** Read → Explain

**No import needed.** Agent reads the code (from URL or pasted), explains, suggests.

**Agent produces:**
- Explanation of the issue
- Suggested fix
- No project created (unless user wants to go deeper)

---

### 3C: Audit

**User says:** "Review this repo for security issues", "Check code quality"

**Flow:** Clone → Analyze → Report

**Agent produces an audit report:**
- Security vulnerabilities found
- Code quality issues
- Architecture concerns
- Test coverage assessment
- Recommendations prioritized by severity

**Gitea integration:**
- Report stored in `.forge0/audit-report.md`
- Issues created for each finding
- No code changes (audit is read-only)

---

## Scenario Comparison

| Aspect | Greenfield | Existing (Feature) | Existing (Bug) | External (Import) |
|---|---|---|---|---|
| Starting context | None | Full .forge0/ | Full .forge0/ | Raw code |
| Requirements | Full elicitation | Short (context exists) | Bug description | Analysis |
| Architecture | From scratch | Update existing | N/A | Discover |
| Decomposition | Full | Incremental | N/A | N/A |
| TDD | Yes | Yes | Regression test | Depends |
| CI gate | Yes | Yes | Yes | Yes |
| Human review | Yes | Yes | Yes | Yes (analysis) |

## Portal UX

All scenarios use the same conversation UI. The difference is the agent's starting context.

**Dashboard:**
- Project list (all scenarios)
- "New Project" button (greenfield)
- "Connect Repo" button (external import)
- "Ask" input (quick questions)

**Project detail page:**
- For Forge0 projects: phase pipeline, specs, tasks, activity
- For external projects: analysis results, issues, suggestions
- "New Request" button (starts feature/bug/refactor flow)

**Conversation view:**
- Same UI everywhere
- Agent messages include structured summaries
- "Approve" / "Revise" buttons on artifacts
- Pipeline visualization showing progress

## Agent Context Assembly

The agent's system prompt is dynamically assembled per scenario:

```python
def build_agent_context(project, scenario, user_request):
    """Assemble the agent's context based on scenario."""
    context = [BASE_SYSTEM_PROMPT]
    
    if scenario == "greenfield":
        context.append("This is a new project. No existing code or specs.")
    
    elif scenario == "existing_feature":
        context += [
            read_file(project.path / ".forge0/project.yaml"),
            read_file(project.path / ".forge0/workflow.yaml"),
            read_file(project.path / ".forge0/knowledge/decisions.md"),
            read_file(project.path / "architecture.md"),
            read_file(project.path / "AGENTS.md"),
            get_relevant_code(project, user_request),
            get_existing_tests(project),
        ]
    
    elif scenario == "existing_bug":
        context += [
            read_file(project.path / ".forge0/project.yaml"),
            read_file(project.path / "architecture.md"),
            get_relevant_code(project, user_request),
            get_error_details(user_request),
        ]
    
    elif scenario == "external_import":
        context += [
            analyze_codebase(project.path),
            get_readme(project.path),
            get_package_manifest(project.path),
        ]
    
    return "\n\n---\n\n".join(context)
```
