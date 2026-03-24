---
name: notion-setup
description: Set up Notion connection. API token from notion.so/my-integrations, then grant page access via Settings → Integrations → Edit → Content access.
---

# Notion — Setup

## Auth method: api-token

Notion internal integrations use a long-lived Bearer token. The token is scoped to a single workspace and never expires unless manually revoked.

**What to ask the user:**
- "Paste your Notion integration token" → notion.so/my-integrations → New integration → Internal → copy **Internal Integration Secret** (starts with `ntn_`)

---

## Steps

1. Set `.env`:

```bash
NOTION_API_TOKEN=your-token-here
NOTION_BASE_URL=https://api.notion.com/v1
```

2. Grant the integration access to pages:
   - In Notion: **Settings → Integrations → find your integration → Edit → Content access → "Search pages or teamspaces"** → add the pages/teamspaces you want accessible.
   - ⚠️ Without this step the token is valid but all read/write endpoints return 404 and search returns empty.

---

## Verify

```bash
source .env
curl -s "$NOTION_BASE_URL/users/me" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" | jq .
# → {"object":"user","name":"{integration-name}","type":"bot","bot":{"workspace_name":"..."}}
```

**Connection details:** `tool_connections/notion/connection-api-token.md`

---

## `.env` entries

```bash
# --- Notion ---
NOTION_API_TOKEN=your-token-here
NOTION_BASE_URL=https://api.notion.com/v1
# Generate at: https://www.notion.so/my-integrations → New integration → Internal → copy Secret
# Then grant page access: Settings → Integrations → Edit → Content access → add pages
```

---

## Refresh

Long-lived — no refresh needed unless the token is manually revoked in Notion Settings → Integrations.
