---
name: security-scan
description: Run security scanning tools — gitleaks, semgrep, bandit, trivy — and overlay findings onto code graph
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: security
---

## What I do

Run security scanning tools and overlay findings onto the code graph for comprehensive security analysis.

## When to use me

- Pre-commit security checks
- PR security review
- Security audit workflows
- Vulnerability detection

## Tools

### Gitleaks — Secret Detection

```bash
# Scan for secrets
gitleaks detect --source . --report-format json --report-path gitleaks.json --redact

# Check specific directory
gitleaks detect --source src/ --verbose
```

### Semgrep — SAST

```bash
# OWASP Top 10 rules
semgrep scan --config=p/owasp-top-ten --json --output semgrep.json src/

# Python-specific rules
semgrep scan --config=p/python --json --output semgrep.json src/

# Custom rules
semgrep scan --config=rules/ --json --output semgrep.json src/
```

### Bandit — Python SAST

```bash
# Basic scan
bandit -r src/ -f json -o bandit.json

# Medium+ severity only
bandit -r src/ -f json -o bandit.json -l -i --severity-level medium
```

### Trivy — Dependency CVEs

```bash
# Scan dependencies
trivy fs --format json --output trivy.json .

# Scan container image
trivy image --format json --output trivy.json myapp:latest
```

## Overlay with TrailMark

```bash
# Analyze code structure
trailmark analyze src/ --language auto --json > graph.json

# Find entrypoints
trailmark entrypoints src/ --json > entrypoints.json

# Overlay security findings
trailmark augment src/ --sarif semgrep.json
trailmark augment src/ --sarif bandit.json
trailmark augment src/ --sarif gitleaks.json

# Visualize paths from entrypoints to findings
trailmark entrypoint_paths_to <sink_function> --json
```

## Workflow

```bash
# 1. Run all scanners
gitleaks detect --source . --report-format json --report-path /tmp/gitleaks.json --redact
semgrep scan --config=p/owasp-top-ten --json --output /tmp/semgrep.json src/
bandit -r src/ -f json -o /tmp/bandit.json -l -i

# 2. Analyze code structure
trailmark analyze src/ --language auto --summary
trailmark entrypoints src/ --json > /tmp/entrypoints.json

# 3. Overlay findings
trailmark augment src/ --sarif /tmp/semgrep.json
trailmark augment src/ --sarif /tmp/bandit.json
trailmark augment src/ --sarif /tmp/gitleaks.json

# 4. Review findings
trailmark analyze src/ --complexity 10  # High-risk areas
```

## Rules

- **Run on every PR** — catch issues early
- **Fail on critical findings** — block merge for high-severity issues
- **Overlay on code graph** — understand where findings are in the codebase
- **Focus on entrypoints** — these are the attack surface
- **Track complexity** — high complexity = high risk
