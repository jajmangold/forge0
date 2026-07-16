# External Repository Interaction

How Forge0 works with repos outside Gitea — GitHub, GitLab, Bitbucket, and any git remote.

## Design Principle

**Forge0 is the workspace. External repos are the source of truth (or sync targets).**

Users may have existing repos on GitHub. They may want to push agent work back to GitHub. They may want to pull updates from external repos. Forge0 must handle all of these.

## Interaction Modes

### Mode 1: Pull Mirror (import from external)

**Use case:** User has a repo on GitHub, wants to work on it in Forge0.

**How it works:**
1. Gitea migrates the repo with "This repository will be a mirror" checked
2. Gitea periodically pulls changes from the external repo
3. Forge0 agents work on the local copy
4. Changes can be pushed back via push mirror (Mode 2)

**Gitea API:**
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

**Limitation:** Pull mirrors can only be set at creation time. You can't convert an existing repo into a pull mirror.

**Sync trigger:** Automatic (periodic) or manual via API:
```bash
# Force sync a pull mirror
curl -X POST http://localhost:3000/api/v1/repos/agent/my-project/mirror-sync \
  -H "Authorization: token $TOKEN"
```

---

### Mode 2: Push Mirror (push changes to external)

**Use case:** Agent made changes in Forge0, user wants them on GitHub.

**How it works:**
1. Gitea repo has a push mirror configured pointing to the external repo
2. On every push to the Gitea repo (or on schedule), changes are force-pushed to the external repo
3. The external repo stays in sync with the Gitea repo

**Gitea API:**
```bash
# Add a push mirror to an existing repo
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

**Sync trigger:** On every commit (if `sync_on_commit: true`), periodic, or manual:
```bash
# Force sync a push mirror
curl -X POST http://localhost:3000/api/v1/repos/agent/my-project/push_mirrors/sync \
  -H "Authorization: token $TOKEN"
```

**Platforms supported:**
- GitHub (personal access token with `public_repo` + `workflow`)
- GitLab (personal access token with `write_repository`)
- Bitbucket (app password with `Repository Write`)
- Any HTTPS git remote with basic auth

---

### Mode 3: Fork-based workflow (GitHub PRs)

**Use case:** User wants to contribute to an open-source project via GitHub PRs.

**How it works:**
1. Pull mirror the upstream repo into Forge0
2. Agent creates a branch, makes changes
3. Push mirror to user's GitHub fork
4. User creates PR from fork to upstream on GitHub

**This requires:**
- Upstream repo: pull mirror
- User's fork: push mirror
- GitHub token with appropriate scopes

---

### Mode 4: Bidirectional sync

**Use case:** Team works on both GitHub and Forge0, changes flow both ways.

**How it works:**
1. Pull mirror: GitHub → Forge0 (periodic)
2. Push mirror: Forge0 → GitHub (on commit)
3. Conflict resolution: Forge0 is authoritative (push mirror force-pushes)

**Warning:** This can cause issues if both sides have changes. The push mirror will overwrite the external repo. Design choice: Forge0 is the workspace, external is the sync target.

---

### Mode 5: Direct git remote (no mirror)

**Use case:** Agent needs to push to a specific branch on an external repo without full mirroring.

**How it works:**
1. Agent clones the repo into Forge0 (not as mirror)
2. Agent adds the external repo as a git remote
3. Agent pushes specific branches to the external remote

**This is done via git commands inside the container:**
```bash
# Inside the Gitea container
git remote add github https://github.com/user/repo.git
git push github feature/my-branch
```

**Use case:** One-off pushes, not continuous sync.

## Credential Management

External repo credentials (tokens, passwords) must be stored securely.

### Storage

Credentials are stored in the Gitea database (configured via the push mirror UI or API). They are NOT stored in `.forge0/` or committed to repos.

### Environment variables (for agent access)

```bash
# GitHub
GITHUB_TOKEN=ghp_xxxx
GITHUB_USER=username

# GitLab
GITLAB_TOKEN=glpat-xxxx

# Generic
GIT_REMOTE_USER=username
GIT_REMOTE_TOKEN=xxxx
```

These are set in the portal's docker-compose.yaml and passed to agents as needed.

### API token scopes

| Platform | Required scopes |
|---|---|
| GitHub | `public_repo` (or `repo` for private), `workflow` (if using Actions) |
| GitLab | `write_repository` |
| Bitbucket | `Repository Write` (app password) |

## Agent Workflows with External Repos

### Import → Work → Push back

```
1. User provides GitHub URL
2. Agent creates pull mirror in Gitea
3. Agent analyzes codebase, creates .forge0/ scaffold
4. Agent works on features/fixes (TDD, branches, PRs)
5. Agent configures push mirror to GitHub
6. Changes appear on GitHub
```

### Pull updates from external

```
1. External repo has new commits
2. Gitea pull mirror syncs (periodic or manual)
3. Agent detects new commits
4. Agent rebases/merges local work if needed
5. Agent reports conflicts to user
```

### Push specific branch to external

```
1. Agent completes work on feature branch
2. Agent pushes branch to external remote via git
3. User creates PR on GitHub/GitLab
4. PR reviewed and merged externally
5. Pull mirror syncs the merge back to Forge0
```

## Portal Integration

The portal should show:
- **External sync status** for each repo (last sync time, direction, errors)
- **"Connect to GitHub"** button on repo settings
- **"Push to external"** button on completed branches
- **Conflict alerts** when pull mirror detects diverged history

## API Summary

| Action | Gitea API | Method |
|---|---|---|
| Create pull mirror | `POST /api/v1/repos/migrate` | `mirror: true` |
| Add push mirror | `POST /api/v1/repos/{owner}/{repo}/push_mirrors` | — |
| Sync pull mirror | `POST /api/v1/repos/{owner}/{repo}/mirror-sync` | — |
| Sync push mirror | `POST /api/v1/repos/{owner}/{repo}/push_mirrors/sync` | — |
| List push mirrors | `GET /api/v1/repos/{owner}/{repo}/push_mirrors` | — |
| Delete push mirror | `DELETE /api/v1/repos/{owner}/{repo}/push_mirrors/{name}` | — |

## SSH Push Mirrors (workaround)

Gitea doesn't natively support SSH push mirrors. Workaround using a post-receive hook:

```bash
#!/usr/bin/env bash
# Add as post-receive hook in Gitea repo settings
git push --mirror --quiet git@github.com:username/repository.git &>/dev/null &
echo "GitHub mirror initiated .."
```

The Gitea container must have SSH access to the external repo (SSH key mounted as volume).

## Security Considerations

1. **Tokens never committed** — stored in Gitea DB, not in repos
2. **Token rotation** — when external tokens expire, update via Gitea API
3. **Least privilege** — use tokens with minimum required scopes
4. **Audit trail** — all mirror syncs are logged by Gitea
5. **Force push warning** — push mirrors force-push, overwriting the external repo
