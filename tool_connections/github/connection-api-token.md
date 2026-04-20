---
name: github
auth: api-token
description: GitHub — browse repos, fetch READMEs and API docs, search code, manage PRs and issues. Use when browsing repos, reading READMEs, searching code, creating or reviewing PRs, managing issues. Works with both github.com and GitHub Enterprise (self-hosted).
env_vars:
  - GITHUB_TOKEN
  - GITHUB_BASE_URL
---

# GitHub

Env: `GITHUB_TOKEN`, `GITHUB_BASE_URL`

```bash
# Set in .env:
# GITHUB_TOKEN=ghp_your-personal-access-token
# GITHUB_BASE_URL=https://api.github.com          # public GitHub
# GITHUB_BASE_URL=https://your-ghe.example.com/api/v3  # GitHub Enterprise
```

Auth: `Authorization: token $GITHUB_TOKEN`

**Generate token:** GitHub → Settings → Developer settings → Personal access tokens → Generate new token
Scopes needed: `repo`, `read:org` (add `workflow` if you need to trigger Actions)

## Verify connection

```bash
export $(grep -v '^#' .env | grep 'GITHUB_' | xargs)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/user" \
  | jq '{login, name, email}'
# → {"login": "alice", "name": "Alice Smith", "email": "alice@example.com"}
# If you see 401: token is wrong. If you see 404: check GITHUB_BASE_URL.
```

---

## Repos

```bash
export $(grep -v '^#' .env | grep 'GITHUB_' | xargs)

# List your repos (sorted by recently updated)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/user/repos?per_page=10&sort=updated" \
  | jq '.[] | {name, full_name, updated_at, description}'

# Search repos by keyword
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/search/repositories?q=<keyword>&per_page=5" \
  | jq '.items[] | {name, full_name, description, stargazers_count}'

# Fetch a repo's README (base64-decoded)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/readme" \
  | jq -r '.content' | base64 -d

# List directory contents
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/contents/{path}" \
  | jq '.[] | {name, type, path}'

# Fetch a specific file (base64-decoded)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/contents/{path/to/file}" \
  | jq -r '.content' | base64 -d
```

---

## Code search

```bash
export $(grep -v '^#' .env | grep 'GITHUB_' | xargs)

# Search code by keyword
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/search/code?q=<keyword>+repo:{owner}/{repo}&per_page=5" \
  | jq '.items[] | {path, name, repository: .repository.full_name}'

# Search code across all accessible repos
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/search/code?q=<keyword>&per_page=10" \
  | jq '.items[] | {path, repository: .repository.full_name}'
```

---

## Pull Requests

```bash
export $(grep -v '^#' .env | grep 'GITHUB_' | xargs)

# List open PRs in a repo
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/pulls?state=open&per_page=20" \
  | jq '.[] | {number, title, user: .user.login, created_at}'

# Get a specific PR
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/pulls/{pr_number}" \
  | jq '{number, title, state, body, user: .user.login, base: .base.ref, head: .head.ref}'

# Get PR review comments
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/pulls/{pr_number}/comments" \
  | jq '.[] | {user: .user.login, body, path, line}'

# Create a PR
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/pulls" \
  -d '{"title": "PR title", "body": "Description", "head": "feature-branch", "base": "main"}'
```

---

## Issues

```bash
export $(grep -v '^#' .env | grep 'GITHUB_' | xargs)

# List open issues
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/issues?state=open&per_page=20" \
  | jq '.[] | {number, title, user: .user.login, labels: [.labels[].name]}'

# Create an issue
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/issues" \
  -d '{"title": "Issue title", "body": "Issue description", "labels": ["bug"]}'

# Add a comment to an issue
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/issues/{issue_number}/comments" \
  -d '{"body": "Comment text here."}'
```

---

## Git push (HTTPS with token)

Standard `git push` over HTTPS requires the token embedded in the remote URL. Using `Authorization: Bearer` or `Authorization: token` headers via `http.extraHeader` is **not** supported by git's credential layer and will return `invalid credentials`, especially on GitHub Enterprise.

**One-off push (Python — safe, token never stored in config):**
```python
import os, subprocess
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/path/to/.env"))
token = os.environ["GITHUB_TOKEN"]  # or GHE_TOKEN for GHE

push_url = f"https://{username}:{token}@{host}/{org}/{repo}.git"
subprocess.run(["git", "-C", "/path/to/repo", "push", push_url, "main"], check=True)
# push_url is never stored — it's only passed as a one-time argument
```

**Set remote temporarily (shell):**
```bash
git remote set-url origin "https://${GIT_USERNAME}:${GITHUB_TOKEN}@${host}/${org}/${repo}.git"
git push origin main
git remote set-url origin "https://${host}/${org}/${repo}.git"  # reset to clean URL after push
```

> Never store a token-embedded URL permanently in `.git/config`. Always reset to the clean URL after pushing.

---

## Commits and branches

```bash
export $(grep -v '^#' .env | grep 'GITHUB_' | xargs)

# List branches
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/branches?per_page=20" \
  | jq '.[] | .name'

# Get recent commits
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/repos/{owner}/{repo}/commits?per_page=10" \
  | jq '.[] | {sha: .sha[:8], message: .commit.message, author: .commit.author.name, date: .commit.author.date}'
```
