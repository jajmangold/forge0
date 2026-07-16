---
name: edit-format
description: File editing using SEARCH/REPLACE blocks for precise, reversible code changes
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: editing
---

## What I do

Implement file editing using SEARCH/REPLACE blocks for precise, reversible code changes. This format ensures edits are exact, traceable, and can be auto-reverted on failure.

## When to use me

- Editing existing code files
- Making precise, targeted changes
- Need reversible edits
- Want clear audit trail of changes

## SEARCH/REPLACE Format

````
src/module.py
```python
<<<<<<< SEARCH
def old_function():
    pass
=======
def new_function():
    return True
>>>>>>> REPLACE
```
````

## Rules

- **Exact match** — SEARCH must exactly match existing code
- **One logical change** — each block should be one atomic edit
- **Preserve indentation** — match surrounding code style
- **Include context** — include enough lines to uniquely identify the change
- **Verify after edit** — run tests/lint after applying edits

## Example

````
src/auth.py
```python
<<<<<<< SEARCH
def verify_token(token: str) -> bool:
    return token == "secret"
=======
def verify_token(token: str) -> bool:
    """Verify JWT token signature and expiry."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("exp", 0) > time.time()
    except jwt.InvalidTokenError:
        return False
>>>>>>> REPLACE
```
````
