# Forge0 Development Methodology

Spec-driven TDD with functional decomposition. How Forge0 agents write code.

## Core Principles

1. **No code before tests.** Every function has a test committed before its implementation.
2. **Atomic functions.** Each function does one thing. One input, one output, one purpose.
3. **Full traceability.** Function → test → task → requirement. Every line traces back to a spec.
4. **CI is the gate.** Tests must pass. Coverage must meet threshold. No exceptions.
5. **Python + pytest.** Standard language and test framework for all agent-written code.

## The Pipeline

```
Requirement
    │
    ▼
Architecture (tech decisions)
    │
    ▼
Functional Decomposition (dependency DAG)
    │
    ▼
Task Grouping (3-8 functions per task)
    │
    ▼
TDD per Function (test → code → commit)
    │
    ▼
PR + CI + Review
    │
    ▼
Merge to main
```

## Phase: Functional Decomposition

After architecture is approved, the Decomposition Agent breaks the system into atomic functions.

### What it produces

A dependency DAG (directed acyclic graph) of functions:

```
authenticate(email, password) -> Token
  ├── verify_password(plain, hash) -> bool
  │     └── hash_password(plain) -> str
  ├── get_user_by_email(email) -> User
  └── create_token(user_id) -> str
        └── encode_jwt(payload, secret) -> str
```

Each node is:
- **Function signature** — name, inputs, output type
- **Purpose** — one sentence
- **Dependencies** — what it calls
- **Complexity** — simple / moderate / complex

### How it works

1. Agent reads requirement.md + architecture.md
2. Agent identifies top-level entry points (API handlers, CLI commands, etc.)
3. Agent decomposes each into sub-functions
4. Agent continues until each leaf function is atomic
5. Agent validates: no circular dependencies, all leaves are implementable
6. Critic agent checks: is each function truly atomic? Are signatures clear?

### Output format

Stored in `.forge0/specs/REQ-NNN/decomposition.md`:

```markdown
---
id: DECOMP-001
requirement: REQ-001
status: approved
---

## Function Registry

### auth/
| Function | Signature | Purpose | Dependencies | Complexity |
|---|---|---|---|---|
| hash_password | `(plain: str) -> str` | Hash plaintext password | bcrypt | simple |
| verify_password | `(plain: str, hash: str) -> bool` | Verify password against hash | hash_password | simple |
| create_token | `(user_id: int) -> str` | Create JWT auth token | encode_jwt | moderate |
| verify_token | `(token: str) -> int` | Verify JWT and return user_id | decode_jwt | moderate |
| authenticate | `(email: str, password: str) -> Token` | Full auth flow | verify_password, get_user_by_email, create_token | moderate |

### users/
| Function | Signature | Purpose | Dependencies | Complexity |
|---|---|---|---|---|
| get_user_by_email | `(email: str) -> User` | Lookup user by email | db.query | simple |
| create_user | `(email: str, password: str) -> User` | Create new user | hash_password, db.insert | moderate |

## Dependency Graph

\```
authenticate
├── verify_password
│   └── hash_password
├── get_user_by_email
└── create_token
    └── encode_jwt

create_user
├── hash_password
└── db.insert
\```
```

## Phase: Task Grouping

The Planner Agent groups related functions into tasks.

### Rules

- A task contains **3-8 related functions** (not one, not twenty)
- Functions in a task share a **cohesive purpose** (e.g., "password handling")
- Tasks respect the **dependency graph** — a task's dependencies must be in earlier tasks
- Each task maps to **one Gitea issue** and **one branch**

### Example grouping

```
Task 1: password-hashing (REQ-001)
  - hash_password
  - verify_password
  → Dependencies: none (leaf functions)

Task 2: user-management (REQ-001)
  - get_user_by_email
  - create_user
  → Dependencies: Task 1 (needs hash_password)

Task 3: authentication (REQ-001)
  - create_token
  - verify_token
  - authenticate
  → Dependencies: Task 1, Task 2

Task 4: api-endpoints (REQ-001)
  - register_handler
  - login_handler
  → Dependencies: Task 3
```

### Output format

Stored in `.forge0/specs/REQ-001/tasks/`:

```
TASK-001-password-hashing.md
TASK-002-user-management.md
TASK-003-authentication.md
TASK-004-api-endpoints.md
```

Each task file includes:
```markdown
---
id: TASK-001
title: "Password Hashing"
requirement: REQ-001
status: pending
dependencies: []
functions:
  - hash_password
  - verify_password
branch: feature/REQ-001-task-001-password-hashing
---

## Functions

### hash_password(plain: str) -> str
- Purpose: Hash plaintext password using bcrypt
- Acceptance criteria:
  - [ ] Returns a string
  - [ ] Same input always produces different hashes (salt)
  - [ ] Hash is verifiable with verify_password

### verify_password(plain: str, hash: str) -> bool
- Purpose: Verify plaintext password against hash
- Acceptance criteria:
  - [ ] Returns True for matching password
  - [ ] Returns False for wrong password
  - [ ] Returns False for invalid hash
```

## TDD: Test-First per Function

For each function in a task, the Implementation Agent follows this exact sequence:

### Step 1: Write the test

Create `tests/test_{module}.py` with the test function. The test defines the contract:

```python
# tests/test_auth.py
import pytest
from src.auth import hash_password, verify_password

class TestHashPassword:
    def test_returns_string(self):
        result = hash_password("mypassword")
        assert isinstance(result, str)
    
    def test_different_hashes_for_same_input(self):
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2  # salt ensures uniqueness
    
    def test_hash_is_verifiable(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

class TestVerifyPassword:
    def test_correct_password(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True
    
    def test_wrong_password(self):
        h = hash_password("mypassword")
        assert verify_password("wrong", h) is False
    
    def test_invalid_hash(self):
        assert verify_password("mypassword", "not-a-hash") is False
```

### Step 2: Run tests (expect failure)

```bash
pytest tests/test_auth.py -v
# All tests FAIL (functions don't exist yet)
```

### Step 3: Write the implementation

Create `src/auth.py` with the minimum code to pass:

```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hash.encode())
    except (ValueError, TypeError):
        return False
```

### Step 4: Run tests (expect pass)

```bash
pytest tests/test_auth.py -v
# All tests PASS
```

### Step 5: Commit (test + code together)

```bash
git add tests/test_auth.py src/auth.py
git commit -m "feat(REQ-001): add hash_password and verify_password with tests"
```

### Commit ordering rule

On a task branch, commits follow this pattern:
```
commit 1: test for function A + implementation of function A
commit 2: test for function B + implementation of function B
commit 3: test for function C + implementation of function C
```

Each commit is **self-contained**: the test and code are committed together. The test defines the contract; the code fulfills it. If you cherry-pick one commit, you get both the test and the code.

**Why not separate test and code commits?** Because:
1. A code commit without its test would fail CI
2. A test commit without code would also fail CI (import errors)
3. Together they form a single atomic unit of work

## Branch Strategy

### One branch per task, not per function

```
main
├── feature/REQ-001-task-001-password-hashing
├── feature/REQ-001-task-002-user-management
├── feature/REQ-001-task-003-authentication
└── feature/REQ-001-task-004-api-endpoints
```

### Branch lifecycle

1. Branch created from `main` when task starts
2. Agent commits function+test pairs incrementally
3. CI runs on every push (tests must pass)
4. When all functions in the task are done, PR is opened
5. Critic agent reviews the PR
6. Human reviews (or auto-approves if critic passes)
7. Merge to `main`
8. Branch deleted

### Branch naming

Format: `feature/{REQ-ID}-task-{TASK-ID}-{kebab-title}`

Examples:
- `feature/REQ-001-task-001-password-hashing`
- `feature/REQ-001-task-003-authentication`
- `fix/REQ-002-task-001-fix-login-redirect`

## Language Standard: Python + pytest

### Why Python?

- Agents are best at Python (most training data, most reliable output)
- pytest is the most flexible test framework
- Rich ecosystem for any domain (web, ML, CLI, etc.)
- Type hints + mypy for static checking
- Fast iteration cycle

### Why pytest?

- Simple: `def test_x(): assert ...`
- Powerful: fixtures, parametrize, markers, plugins
- Universal: can test anything (shells out to other tools if needed)
- Rich reporting: coverage, durations, failure details
- CI-friendly: exit codes, JUnit XML output

### What if we need non-Python code?

If a project needs JS/TS (e.g., a React frontend), the agent:
1. Writes the Python test that calls the JS via subprocess
2. The test validates the JS behavior from the outside
3. The JS code is a "black box" tested through its interface

Example:
```python
def test_renders_component():
    result = subprocess.run(
        ["node", "test-harness.js", "MyComponent"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "expected output" in result.stdout
```

This keeps pytest as the universal test runner while allowing polyglot code.

## Coverage Requirements

- **New code:** minimum 80% line coverage
- **Critical paths** (auth, payments, data): minimum 95%
- **Overall project:** minimum 70% (increases over time)

Enforcement: CI fails if coverage drops below threshold.

```bash
pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

## Conventional Commits

All commits follow conventional commits format:

```
feat(REQ-001): add hash_password and verify_password with tests
fix(REQ-001): handle empty password in hash_password
test(REQ-001): add edge case tests for verify_token
docs(REQ-001): update API docs for auth module
refactor(REQ-001): extract JWT logic to separate module
chore: update dependencies
```

Format: `{type}({scope}): {description}`

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`

This enables:
- Automatic changelog generation
- Traceability from commit → requirement
- Semantic versioning decisions
