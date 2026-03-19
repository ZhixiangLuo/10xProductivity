---
name: bitbucket-server-setup
description: Set up Bitbucket Server / Data Center connection. Personal Access Token + Bearer auth. Ask for any repo or PR URL to infer the base URL.
---

# Bitbucket Server / Data Center — Setup

> This file covers **Bitbucket Server / Data Center** (self-hosted). Bitbucket Cloud (`bitbucket.org`) uses a different API and OAuth2 — not covered here.

## Step 1: Ask for a URL

Ask the user: "Share any Bitbucket repo or PR URL."

Infer `BITBUCKET_BASE_URL` from the URL (e.g. `https://bitbucket.yourcompany.com/projects/...` → `https://bitbucket.yourcompany.com`).

---

## Auth method: Personal Access Token (Bearer)

**What to ask the user:**
- "Paste your Bitbucket Personal Access Token" → Bitbucket → top-right user icon → Manage account → Personal access tokens → Create token
- Scopes needed: Project read + Repository read (add write/admin if needed)

---

## Set `.env`

```bash
BITBUCKET_TOKEN=your-personal-access-token
BITBUCKET_BASE_URL=https://bitbucket.yourcompany.com
```

---

## Verify

```bash
source .env
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BITBUCKET_BASE_URL/rest/api/1.0/profile/recent/repos?limit=3" \
  | jq '.values[] | {slug, name, project: .project.key}'
# → [{"slug": "my-repo", "name": "My Repo", "project": "MYPROJ"}, ...]
# If 401: token wrong or expired. If 403: token lacks read scope.
```

**Connection details:** `tool_connections/bitbucket-server/connection-api-token.md`

---

## `.env` entries

```bash
# --- Bitbucket Server / Data Center ---
BITBUCKET_TOKEN=your-personal-access-token
BITBUCKET_BASE_URL=https://bitbucket.yourcompany.com
# Generate token: Bitbucket → top-right user icon → Manage account → Personal access tokens → Create token
```
