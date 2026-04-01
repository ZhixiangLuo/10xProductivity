---
tool: figma
auth: api-token
---

# Figma — Setup

## What to ask the user

Ask for a personal access token. Direct them here to generate one:

**https://www.figma.com/settings** → Security tab → **Personal access tokens** → Generate new token

Scopes to select: `file_content:read`, `current_user:read`

Token is shown only once — copy it before closing.

---

## .env entries

```bash
# --- Figma ---
FIGMA_API_TOKEN=your-token-here
FIGMA_BASE_URL=https://api.figma.com
# Generate at: https://www.figma.com/settings (Security tab → Personal access tokens)
# Scopes needed: file_content:read, current_user:read
# Token lifetime: long-lived (expiry set at generation)
```

---

## Verify

```bash
export $(grep -v '^#' .env | grep 'FIGMA' | xargs)
curl -s "$FIGMA_BASE_URL/v1/me" -H "X-Figma-Token: $FIGMA_API_TOKEN" | python3 -m json.tool
# Expected: {"id": "...", "email": "...", "handle": "..."}
```

Pass = any JSON response with `id`, `email`, `handle` fields.
Fail = `{"status": 403, "err": "Forbidden"}` → token missing or wrong scopes.
