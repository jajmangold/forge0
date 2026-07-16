---
name: project-context
description: Load full project context — wikis, documentation, issues, PRs, other repos, and fleet status
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: context
---

## What I do

Load comprehensive project context from Gitea, wikis, documentation, and the broader fleet. Give agents full situational awareness.

## When to use me

- Starting work on an unfamiliar project
- Need to understand project history and decisions
- Want to see related issues and PRs
- Need fleet-wide context

## Context Sources

### 1. Project Wiki

```bash
# List wiki pages
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/wiki/pages" | jq

# Get specific wiki page
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/wiki/pages/{page_name}" | jq
```

### 2. Project Documentation

```bash
# Read README
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/contents/README.md" | jq -r '.content' | base64 -d

# Read docs/ directory
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/contents/docs" | jq

# Read specific doc
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/contents/docs/architecture.md" | jq -r '.content' | base64 -d
```

### 3. Issues and PRs

```bash
# List open issues
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/issues?state=open" | jq

# List recent PRs
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/pulls?state=all&limit=10" | jq

# Get issue comments
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/issues/{index}/comments" | jq
```

### 4. Git History

```bash
# Recent commits
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/commits?limit=20" | jq

# Commit details
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/commits/{sha}" | jq
```

### 5. Fleet Context

```bash
# List all repos in the org
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/orgs/forge0/repos" | jq

# Get repo topics
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/topics" | jq
```

## Workflow

### 1. Before Starting Work

```bash
# 1. Load project wiki
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/wiki/pages" | jq

# 2. Read README and docs
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/contents/README.md" | jq -r '.content' | base64 -d

# 3. Check open issues
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/issues?state=open" | jq

# 4. Review recent PRs
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/pulls?state=all&limit=5" | jq

# 5. Check git history
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/commits?limit=10" | jq
```

### 2. During Development

```bash
# Check if issue exists for current task
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/issues?q={task_description}" | jq

# Check related PRs
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/pulls?state=open" | jq
```

### 3. Before Merging

```bash
# Review all comments on PR
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/pulls/{index}/comments" | jq

# Check CI status
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/{repo}/statuses/{sha}" | jq
```

## Rules

- **Always load context first** — don't start work blind
- **Check wiki before coding** — decisions are documented there
- **Review issue history** — avoid repeating past mistakes
- **Check related PRs** — coordinate with other work
- **Understand fleet context** — see how your work fits
