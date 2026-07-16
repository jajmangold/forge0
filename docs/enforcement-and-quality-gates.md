# Enforcement & Quality Gates

How Forge0 ensures code quality. CI gates, branch protection, coverage, and why git hooks aren't enough.

## The Enforcement Stack

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: CONVENTION (AGENTS.md)                    │
│  "Write tests first." Agent follows the protocol.   │
├─────────────────────────────────────────────────────┤
│  Layer 2: CI GATES (Gitea Actions)                  │
│  Tests must pass. Coverage must meet threshold.     │
│  Lint must pass. Type checks must pass.             │
├─────────────────────────────────────────────────────┤
│  Layer 3: BRANCH PROTECTION (Gitea settings)        │
│  PR can't merge without green CI + approval.        │
│  Can't push directly to main.                       │
├─────────────────────────────────────────────────────┤
│  Layer 4: CODE REVIEW (Critic Agent + Human)        │
│  Critic agent reviews every PR.                     │
│  Human reviews when critic flags issues.            │
├─────────────────────────────────────────────────────┤
│  Layer 5: TEST-CODE CORRESPONDENCE                  │
│  Every src/ file must have a matching test file.    │
│  Verified by CI script.                             │
└─────────────────────────────────────────────────────┘
```

## Why NOT Git Hooks

Git hooks (pre-commit, pre-push) are **local only**:

1. **Bypassable:** `git commit --no-verify` skips all hooks
2. **Not shared:** Each developer/agent must install hooks manually
3. **Inconsistent:** Hook behavior depends on local environment
4. **No visibility:** No one knows if a hook was skipped

**What git hooks ARE good for:**
- Developer convenience (auto-format on commit)
- Quick feedback (lint before push)
- NOT enforcement

**What CI + branch protection IS good for:**
- Server-side enforcement (can't bypass)
- Shared (configured in repo, applies to everyone)
- Auditable (every check has a result in the CI log)
- Blocking (PR literally can't merge without passing)

## CI Gates (Gitea Actions)

### Gate 1: Tests must pass

```yaml
- name: Tests
  run: pytest tests/ -v --tb=short
```

If any test fails, CI fails. PR blocked.

### Gate 2: Coverage must meet threshold

```yaml
- name: Coverage
  run: pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

Default: 80% line coverage for new code. Configurable per project.

### Gate 3: Lint must pass

```yaml
- name: Lint
  run: ruff check src/ tests/
```

Catches: unused imports, undefined names, style violations, common bugs.

### Gate 4: Type checks must pass

```yaml
- name: Type check
  run: mypy src/ --ignore-missing-imports
```

Catches: type errors, missing annotations, incompatible types.

### Gate 5: Test-code correspondence

```yaml
- name: Test-code correspondence
  run: python .forge0/scripts/check-test-coverage.py
```

Every source file in `src/` must have a corresponding `test_*.py` in `tests/`.

### Gate 6: Commit message format

```yaml
- name: Conventional commits
  run: |
    # Check last commit message matches conventional format
    MSG=$(git log -1 --pretty=%B)
    if ! echo "$MSG" | grep -qE '^(feat|fix|test|docs|refactor|chore|ci)(\(.+\))?: .+'; then
      echo "ERROR: Commit message does not follow conventional commits format"
      echo "Expected: type(scope): description"
      exit 1
    fi
```

## Branch Protection (Gitea Settings)

Configured in Gitea repo settings → Branches → Branch Protection Rules:

```yaml
Rule name: main
Branch pattern: main

# Merge requirements
Require pull request before merging: YES
Required approvals: 0 (critic agent approval is sufficient)
Dismiss stale reviews: YES
Require review from code owners: NO

# Status checks
Require status checks to pass: YES
Required checks:
  - test
  - lint
  - type-check
  - coverage
  - test-correspondence
  - conventional-commits

# Push restrictions
Do not allow bypassing: YES
Allow force pushes: NO
Allow deletions: NO

# After merge
Delete branch after merge: YES
```

This means:
- No direct pushes to main
- Every change goes through a PR
- All CI checks must pass
- Branch auto-deleted after merge

## Test-Code Correspondence

### The principle

For every function in `src/`, there must be a test in `tests/`. This enforces:
1. No untested code reaches main
2. Tests exist before code (TDD)
3. Every function has documentation (tests as docs)

### Implementation

```python
# .forge0/scripts/check-test-coverage.py
"""Verify every source file has a corresponding test file."""
import ast
import sys
from pathlib import Path

def get_functions(filepath: Path) -> list[str]:
    """Extract function names from a Python file."""
    tree = ast.parse(filepath.read_text())
    return [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith('_')
    ]

def get_tested_functions(filepath: Path) -> list[str]:
    """Extract tested function names from a test file."""
    tree = ast.parse(filepath.read_text())
    return [
        node.name.replace('test_', '') for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith('test_')
    ]

errors = []
for src_file in Path("src").rglob("*.py"):
    if src_file.name == "__init__.py":
        continue
    
    test_file = Path("tests") / f"test_{src_file.name}"
    if not test_file.exists():
        errors.append(f"Missing test file: {test_file}")
        continue
    
    src_functions = get_functions(src_file)
    tested_functions = get_tested_functions(test_file)
    
    untested = [f for f in src_functions if f not in tested_functions]
    if untested:
        errors.append(f"{src_file}: untested functions: {untested}")

if errors:
    print("ERROR: Test-code correspondence check failed:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("All source functions have corresponding tests.")
```

## Coverage Configuration

### pytest.ini / pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

### Per-module overrides

Critical modules can have higher thresholds:

```python
# In CI, run separate coverage checks for critical modules
pytest tests/test_auth.py --cov=src/auth --cov-fail-under=95
pytest tests/test_payment.py --cov=src/payment --cov-fail-under=95
pytest tests/ --cov=src --cov-fail-under=80  # overall
```

## Enforcement Summary

| What | How | Where | Bypassable? |
|---|---|---|---|
| Tests pass | CI check | Gitea Actions | No |
| Coverage ≥ 80% | CI check | Gitea Actions | No |
| Lint clean | CI check | Gitea Actions | No |
| Types correct | CI check | Gitea Actions | No |
| Tests exist for code | CI script | Gitea Actions | No |
| Conventional commits | CI script | Gitea Actions | No |
| PR required | Branch protection | Gitea settings | No |
| No direct push | Branch protection | Gitea settings | No |
| Write tests first | Convention | AGENTS.md | Yes (by design) |

The last one (write tests first) is intentionally convention-based, not mechanically enforced. Here's why:

**You can't mechanically enforce "test written before code" in git.** You can enforce that tests EXIST and PASS. You can enforce that test files and code files are both present. But the order of writing is a process concern, not a tooling concern.

**What matters:** Tests exist. Tests pass. Tests cover the code. Whether the human/agent wrote the test 5 minutes before or 5 hours before the code is irrelevant to the outcome.

**The discipline comes from the protocol:** AGENTS.md says "write test first." The agent follows this. The critic agent verifies the pattern. The CI verifies the outcome. This is the right layering.
