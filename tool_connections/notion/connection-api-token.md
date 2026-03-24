---
name: notion
auth: api-token
description: Notion — workspace tool for notes, docs, databases, and task management (Bearer API token). Use when searching pages by title, reading page content, appending blocks to a page, or creating child pages.
env_vars:
  - NOTION_API_TOKEN
  - NOTION_BASE_URL
---

# Notion — API token (internal integration)

Notion is a workspace tool for notes, docs, databases, and task management. Internal integrations use a long-lived Bearer token scoped to a single workspace.

API docs: https://developers.notion.com/reference/authentication

**Verified:** Production (api.notion.com) — /v1/users/me, /v1/users, /v1/search, /v1/pages/{id}, /v1/blocks/{id}/children (read + write), POST /v1/pages — 2026-03. No VPN required.

---

## Credentials

```bash
# .env entries:
NOTION_API_TOKEN=your-token-here
NOTION_BASE_URL=https://api.notion.com/v1
# Generate at: https://www.notion.so/my-integrations → New integration → Internal → copy Secret
# Token lifetime: long-lived (does not expire unless manually revoked)
```

---

## Auth

Pass the token as a Bearer in `Authorization`, plus the required `Notion-Version` header on every request.

```bash
source .env
curl -s "$NOTION_BASE_URL/users/me" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" | jq .
# → {
#   "object": "user",
#   "id": "{bot-id}",
#   "name": "{integration-name}",
#   "type": "bot",
#   "bot": {
#     "owner": {"type": "workspace", "workspace": true},
#     "workspace_name": "{your-workspace-name}",
#     "workspace_id": "{workspace-id}"
#   }
# }
```

---

## Verified snippets

```bash
source .env
BASE="$NOTION_BASE_URL"

# Health check — get bot user info (works with any capability level)
curl -s "$BASE/users/me" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" | jq .
# → {"object":"user","id":"{bot-id}","name":"{integration-name}","type":"bot",...}

# List workspace members
curl -s "$BASE/users" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" | jq .
# → {"object":"list","results":[{"id":"{user-id}","name":"Alice","type":"person","person":{"email":"alice@example.com"}}, {"name":"{integration-name}","type":"bot",...}]}

# Search all pages/databases shared with the integration
curl -s -X POST "$BASE/search" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" \
  -H "Content-Type: application/json" \
  --data '{"page_size": 10}' | jq .
# → {"object":"list","results":[{"object":"page","properties":{"title":{"title":[{"plain_text":"My Page"}]}},...}]}

# Search by title query
curl -s -X POST "$BASE/search" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" \
  -H "Content-Type: application/json" \
  --data '{"query": "meeting notes", "page_size": 5}' | jq .
# → {"object":"list","results":[{"object":"page","properties":{"title":{"title":[{"plain_text":"Meeting Notes"}]}},...}]}

# Retrieve a page (metadata + title)
curl -s "$BASE/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" | jq .
# → {"object":"page","id":"{page-id}","properties":{"title":{"title":[{"plain_text":"My Page"}]}},...}

# Read page content (blocks)
curl -s "$BASE/blocks/{page_id}/children" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" | jq .
# → {"object":"list","results":[{"type":"paragraph","paragraph":{"rich_text":[{"plain_text":"Hello world"}]}},...]

# Append a paragraph to a page
curl -s -X PATCH "$BASE/blocks/{page_id}/children" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" \
  -H "Content-Type: application/json" \
  --data '{"children":[{"type":"paragraph","paragraph":{"rich_text":[{"type":"text","text":{"content":"Hello from the agent"}}]}}]}' | jq .
# → {"results":[{"id":"{block-id}","type":"paragraph","paragraph":{"rich_text":[{"plain_text":"Hello from the agent"}]}}]}

# Create a child page under a connected page
curl -s -X POST "$BASE/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" \
  -H "Content-Type: application/json" \
  --data '{"parent":{"type":"page_id","page_id":"{parent_page_id}"},"properties":{"title":[{"type":"text","text":{"content":"New page title"}}]}}' | jq .
# → {"id":"{page-id}","url":"https://www.notion.so/New-page-title-{page-id-nodashes}"}
```

---

## Native search

`POST /v1/search` — title-based search across all pages and databases shared with the integration.

```bash
source .env
# Search by title query
curl -s -X POST "$NOTION_BASE_URL/search" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" \
  -H "Content-Type: application/json" \
  --data '{"query": "meeting notes", "page_size": 5}' | jq .

# Filter to pages only
curl -s -X POST "$NOTION_BASE_URL/search" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2026-03-11" \
  -H "Content-Type: application/json" \
  --data '{"query": "notes", "filter": {"value": "page", "property": "object"}, "page_size": 5}' | jq .
```

**Limitations:** title-based only (does not search page body text). Newly shared pages may not appear immediately — indexing lag of seconds to minutes on new workspaces.

## AI / chat

**Not available via the public API.** Notion AI is an enterprise-only product with no developer endpoint. There is no Q&A, summarization, or chat API. The `/v1/search` endpoint above is the closest available capability.

---

## Notes

- **Granting page access — correct path:**
  Go to **Notion Settings → Integrations → find your integration → Edit → Content access → "Search pages or teamspaces"** → add pages there.
  The per-page `...` menu → Connections approach is unreliable in the current Notion UI. Use the Settings path above.
  Without this step, `/v1/search` returns empty results and all `/v1/pages/{id}` and `/v1/blocks/{id}` endpoints return 404.

- **Workspace root pages are not auto-accessible.** Even with the integration installed workspace-wide, every page must be explicitly added via the Content access panel.

- **Internal integrations cannot create workspace-root pages.** Pages must be created as children of an existing accessible page (`parent.page_id`).

- No VPN required.
- Free plan max file upload: 5 MB.
- API version pinned to `2026-03-11` — always send this header.
