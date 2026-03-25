---
name: confluence-setup
description: Set up Confluence connection. Supports Cloud (API token + Basic auth) and Server/Data Center (Bearer PAT). Ask for any Confluence page URL to infer base URL and variant.
---

# Confluence — Setup

## Step 1: Ask for a URL to identify the variant

Ask the user: "Share any Confluence page URL."

Infer variant from the URL:
- `yourcompany.atlassian.net/wiki` → **Confluence Cloud** → API token + Basic auth (`email:token`)
- `confluence.yourcompany.com` (self-hosted) → **Confluence Server/Data Center** → Personal Access Token (Bearer)

Both variants use `connection-api-token.md`. The difference is auth format only — see below.

Infer `CONFLUENCE_BASE_URL` from the URL (e.g. `https://acme.atlassian.net/wiki/spaces/...` → `https://acme.atlassian.net/wiki`).

---

## Confluence Cloud — API token (most common)

**What to ask the user:**
- "Paste your Confluence API token" → https://id.atlassian.com/manage-profile/security/api-tokens → Create API token
- "Your Atlassian account email"

> **Note:** Confluence Cloud and Jira Cloud share the same Atlassian account. If the user already set up Jira, the same token and email work for Confluence.

**Set `.env`:**
```bash
CONFLUENCE_EMAIL=you@yourcompany.com
CONFLUENCE_TOKEN=your-atlassian-api-token
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki   # inferred from URL they shared
```

**Verify:**
```bash
source .env
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
  | jq '{total: .size, first: .results[0].title}'
# → {"total": 1, "first": "Some Page Title"}
# If 401: wrong email or token. If 403: token lacks permissions.
```

**Connection details:** `tool_connections/confluence/connection-api-token.md`

---

## Confluence Server / Data Center — Personal Access Token

**What to ask the user:**
- "Paste your Confluence Personal Access Token" → Confluence → Profile → Personal Access Tokens → Create token

**Set `.env`:**
```bash
CONFLUENCE_TOKEN=your-personal-access-token
CONFLUENCE_BASE_URL=https://confluence.yourcompany.com   # inferred from URL they shared
```

**Verify:**
```bash
source .env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
  | jq '{total: .size, first: .results[0].title}'
```

**Connection details:** `tool_connections/confluence/connection-api-token.md`

---

## `.env` entries

```bash
# --- Confluence ---
CONFLUENCE_EMAIL=your-email@example.com
CONFLUENCE_TOKEN=your-atlassian-api-token
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
# For Confluence Server: CONFLUENCE_BASE_URL=https://confluence.yourcompany.com
# Generate token at: https://id.atlassian.com/manage-profile/security/api-tokens
```
