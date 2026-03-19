---
name: github-setup
description: Set up GitHub connection. API token (PAT) for github.com and GitHub Enterprise. Ask for a repo or PR URL if using GitHub Enterprise to infer the base URL.
---

# GitHub — Setup

## Step 1: Identify the variant

- No URL provided, or URL is `github.com` → **GitHub.com** — base URL is always `https://api.github.com`
- URL is a self-hosted instance (e.g. `github.yourcompany.com`) → **GitHub Enterprise** — infer base URL as `https://github.yourcompany.com/api/v3`

---

## Auth method: Personal Access Token (PAT)

**What to ask the user:**
- "Paste your GitHub personal access token" → GitHub → Settings → Developer settings → Personal access tokens → Generate new token
- Scopes needed: `repo`, `read:org` (add `workflow` to trigger Actions)
- If GitHub Enterprise: "Share any repo or PR URL from your GitHub" to infer the base URL

**Set `.env`:**
```bash
GITHUB_TOKEN=ghp_your-personal-access-token
GITHUB_BASE_URL=https://api.github.com          # or https://your-ghe.example.com/api/v3
```

**Verify:**
```bash
source .env
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/user" \
  | jq '{login, name, email}'
# → {"login": "alice", "name": "Alice Smith", "email": "alice@example.com"}
# If 401: token is wrong. If 404: check GITHUB_BASE_URL.
```

**Connection details:** `tool_connections/github/connection-api-token.md`

---

## `.env` entries

```bash
# --- GitHub ---
GITHUB_TOKEN=ghp_your-personal-access-token
GITHUB_BASE_URL=https://api.github.com
# For GitHub Enterprise: GITHUB_BASE_URL=https://your-ghe.example.com/api/v3
# Generate token at: GitHub → Settings → Developer settings → Personal access tokens
```
