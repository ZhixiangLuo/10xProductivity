---
name: pagerduty-setup
description: Set up PagerDuty connection. API token auth. Base URL is always api.pagerduty.com — no URL needed from user.
---

# PagerDuty — Setup

## Auth method: Personal REST API token

PagerDuty's API base is always `https://api.pagerduty.com` — no URL needed from the user.

**What to ask the user:** "Paste your PagerDuty API key" → PagerDuty → top-right avatar → My Profile → User Settings → API Access → Create New API Key.

---

## Set `.env`

```bash
PAGERDUTY_TOKEN=your-personal-api-key-here
```

---

## Verify

```bash
source .env
curl -s "https://api.pagerduty.com/users/me" \
  -H "Authorization: Token token=$PAGERDUTY_TOKEN" \
  -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '{name: .user.name, email: .user.email, role: .user.role}'
# → {"name": "Alice Smith", "email": "alice@example.com", "role": "limited_user"}
# If 401: token is wrong or expired — generate a new one in PagerDuty.
```

**Connection details:** `tool_connections/pagerduty/connection-api-token.md`

---

## `.env` entries

```bash
# --- PagerDuty ---
PAGERDUTY_TOKEN=your-personal-api-key
# Generate at: PagerDuty → My Profile → User Settings → API Access → Create New API Key
```
