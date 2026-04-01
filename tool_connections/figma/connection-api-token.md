---
name: figma
auth: api-token
description: Figma design files — read file content, fetch nodes/pages, list comments, get version history, inspect component/style libraries. Use when accessing a Figma file, reading design specs, or fetching comments from a Figma URL.
env_vars:
  - FIGMA_API_TOKEN
  - FIGMA_BASE_URL
---

# Figma — API Token

Figma is a collaborative interface design tool. Use to read file content, fetch nodes/pages, list comments, get version history, and inspect component/style libraries.

API docs: https://www.figma.com/developers/api

**Verified:** Production (https://api.figma.com) — `/v1/me`, `/v1/files/:key`, `/v1/files/:key/comments`, `/v1/files/:key/nodes` — 2026-04. No VPN required.

---

## Credentials

```bash
# Add to .env:
# FIGMA_API_TOKEN=your-token-here
# FIGMA_BASE_URL=https://api.figma.com
# Generate at: https://www.figma.com/settings (Security tab → Personal access tokens)
# Scopes needed: file_content:read, current_user:read
# Token lifetime: long-lived (expiry set at generation)
```

---

## Auth

Pass token in `X-Figma-Token` header (not `Authorization: Bearer`).

```bash
export $(grep -v '^#' .env | grep 'FIGMA' | xargs)
curl -s "$FIGMA_BASE_URL/v1/me" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool
# → {"id": "u_123456", "email": "alice@example.com", "handle": "Alice"}
```

---

## Verified snippets

```bash
export $(grep -v '^#' .env | grep 'FIGMA' | xargs)
BASE="$FIGMA_BASE_URL"

# Get current user
curl -s "$BASE/v1/me" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool
# → {"id": "u_123456", "email": "alice@example.com", "handle": "Alice", "img_url": "https://..."}

# Fetch a file by key (extract key from URL: figma.com/design/{FILE_KEY}/...)
curl -s "$BASE/v1/files/{FILE_KEY}?depth=1" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool | head -30
# → {"document": {"id": "0:0", "name": "Document", "children": [{"id": "0:1", "name": "Page 1", "type": "CANVAS"}]}, "name": "My Design File", "lastModified": "2024-01-15T10:30:00Z", "version": "1234567890"}

# Get file metadata only
curl -s "$BASE/v1/files/{FILE_KEY}?depth=1" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps({'name': d.get('name'), 'lastModified': d.get('lastModified'), 'version': d.get('version')}, indent=2))"
# → {"name": "My Design File", "lastModified": "2024-01-15T10:30:00Z", "version": "1234567890"}

# List comments on a file
curl -s "$BASE/v1/files/{FILE_KEY}/comments" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool | head -20
# → {"comments": [{"id": "123456", "message": "Looks good!", "user": {"handle": "Bob"}, "created_at": "2024-01-14T09:00:00Z", "resolved_at": null}]}

# Fetch a specific node (node-id from URL: ?node-id=0-1 → ids=0:1)
curl -s "$BASE/v1/files/{FILE_KEY}/nodes?ids=0:1" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool | head -20
# → {"nodes": {"0:1": {"document": {"id": "0:1", "name": "Page 1", "type": "CANVAS", "children": []}}}}

# Missing scope — returns 403
curl -s "$BASE/v1/files/{FILE_KEY}" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool
# → {"status": 403, "err": "Forbidden"} — token missing file_content:read scope
```

---

## Notes

- ⚠ Auth header is `X-Figma-Token`, NOT `Authorization: Bearer` — using the wrong header returns 403.
- File key is the alphanumeric segment in the URL: `figma.com/design/{FILE_KEY}/file-name`
- Node IDs in URLs use `-` (e.g. `node-id=0-1`) but the API expects `:` (e.g. `ids=0:1`).
- No search API — Figma REST API does not expose full-text search across files or teams. Files must be fetched by key.
- AI/chat: no public AI/assistant endpoint in the REST API.
- `/v1/me/files` returns 404 — there is no "list my files" endpoint.
