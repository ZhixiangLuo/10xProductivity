---
name: backstage-setup
description: Set up Backstage connection. Bearer token auth — either a static long-lived token (from platform team) or a short-lived SSO JWT (from browser local storage). Ask for Backstage URL.
---

# Backstage — Setup

## Step 1: Ask for a URL

Ask the user: "Share your Backstage URL" (e.g. `https://backstage.yourcompany.com`).

Infer `BACKSTAGE_BASE_URL` from the URL.

---

## Auth method: Bearer token

Two token types depending on your Backstage deployment:

**Static token (long-lived — preferred):**
Set in `app-config.yaml` under `backend.auth.keys`. Ask your platform team: "Can I get a static Backstage token for local agent use?"

**SSO-issued JWT (short-lived, ~8h):**
Log in via your identity provider and capture the token from browser local storage:
DevTools → Application → Local Storage → your Backstage URL → look for a key containing `"token"`

**What to ask the user:** "Paste your Backstage token" (either static or SSO JWT from browser local storage).

> **Check `.env` first** — some deployments store the token under a non-standard name (e.g. `PORTAL_IDP_TOKEN`, `BACKSTAGE_JWT`). If any token-shaped value exists for the Backstage URL's domain, try it before asking the user.

---

## Set `.env`

```bash
BACKSTAGE_TOKEN=your-backstage-token
BACKSTAGE_BASE_URL=https://backstage.yourcompany.com
```

---

## Verify

```bash
source .env
curl -s -k "$BACKSTAGE_BASE_URL/api/catalog/entity-facets?facet=kind" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '.facets.kind'
# → [{"value": "Component", "count": 1154}, {"value": "Group", "count": 4373}, ...]
# If 401: token expired or wrong — refresh or ask your platform team.
```

**Connection details:** `tool_connections/backstage/connection-api-token.md`

---

## `.env` entries

```bash
# --- Backstage ---
BACKSTAGE_TOKEN=your-backstage-token         # or whatever name your deployment uses
BACKSTAGE_BASE_URL=https://backstage.yourcompany.com
# Static token (long-lived): ask your platform team or set in app-config.yaml backend.auth.keys
# SSO JWT (short-lived ~8h): capture from browser DevTools → Application → Local Storage → backstage
# Note: some deployments use a different env var name (e.g. PORTAL_IDP_TOKEN) — check .env before asking user
```
