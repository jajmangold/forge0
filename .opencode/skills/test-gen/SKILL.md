---
name: test-gen
description: Generate comprehensive test suites — unit, integration, edge cases, and mutation testing
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: testing
---

## What I do

Generate comprehensive test suites covering happy paths, edge cases, error handling, and integration points.

## When to use me

- Writing tests for new code
- Improving test coverage
- Generating edge case tests
- Mutation testing

## Test Types

### Unit Tests

```python
# test_auth.py
import pytest
from src.auth import verify_token, create_token

class TestVerifyToken:
    def test_valid_token_returns_true(self):
        token = create_token({"user_id": 1})
        assert verify_token(token) is True
    
    def test_expired_token_returns_false(self):
        token = create_token({"user_id": 1}, expires_in=-1)
        assert verify_token(token) is False
    
    def test_invalid_token_returns_false(self):
        assert verify_token("invalid.token.here") is False
    
    def test_none_token_returns_false(self):
        assert verify_token(None) is False
```

### Integration Tests

```python
# test_api.py
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_login_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        assert response.status_code == 200
        assert "token" in response.json()
```

### Edge Cases

```python
# test_edge_cases.py
def test_empty_input():
    assert process("") == []

def test_max_length_input():
    max_input = "x" * 10000
    result = process(max_input)
    assert len(result) <= MAX_OUTPUT

def test_unicode_input():
    assert process("Hello 世界") == ["Hello", "世界"]

def test_special_characters():
    assert process("<script>alert('xss')</script>") == []
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("", []),
    ("hello", ["hello"]),
    ("hello world", ["hello", "world"]),
    ("  spaced  ", ["spaced"]),
])
def test_tokenize(input, expected):
    assert tokenize(input) == expected
```

## Mutation Testing

```bash
# Run mutation testing
mutmut run --paths-to-mutate=src/ --tests-dir=tests/

# View results
mutmut results

# Show surviving mutants
mutmut results --surviving
```

## Coverage

```bash
# Run with coverage
pytest --cov=src --cov-report=html --cov-report=json

# Check coverage threshold
pytest --cov=src --cov-fail-under=80
```

## Rules

- **Test before code** — TDD when possible
- **One assertion per test** — keep tests focused
- **Descriptive names** — test names should explain the scenario
- **Arrange-Act-Assert** — clear test structure
- **Isolate tests** — no shared state between tests
- **Test edge cases** — empty, null, max, min, unicode
- **Mock externals** — don't call real APIs in unit tests
- **Run tests before commit** — never commit broken code
