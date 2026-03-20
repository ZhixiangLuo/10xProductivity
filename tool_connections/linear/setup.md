---
name: linear-setup
description: Set up Linear connection. API token from linear.app/settings/api, paste it into .env.
---

# Linear — Setup

## Auth method: api-token

Linear uses long-lived personal API keys. The token never expires unless manually revoked. No SSO capture or OAuth app needed.

**What to ask the user:**
- "Paste your Linear API key" → linear.app/settings/api → **Personal API keys** → **Create key** → copy the token (starts with `lin_api_`)

---

## Steps

1. Set `.env`:

```bash
LINEAR_API_TOKEN=your-token-here
LINEAR_BASE_URL=https://api.linear.app/graphql
```

---

## Verify

```bash
source .env
curl -s -X POST "$LINEAR_BASE_URL" \
  -H "Authorization: $LINEAR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ viewer { id name email } }"}' | python3 -m json.tool
# → {"data": {"viewer": {"id": "u_123", "name": "alice@example.com", "email": "alice@example.com"}}}
```

**Connection details:** `staging/linear/connection-api-token.md`

---

## `.env` entries

```bash
# --- Linear ---
LINEAR_API_TOKEN=your-token-here
LINEAR_BASE_URL=https://api.linear.app/graphql
# Generate at: https://linear.app/settings/api → Personal API keys → Create key
# Token lifetime: long-lived (does not expire unless revoked)
```

---

## Refresh

Long-lived — no refresh needed unless the token is manually revoked at https://linear.app/settings/api.
