---
name: grafana-setup
description: Set up Grafana connection. Auth is SSO browser session. Only input needed from the user is the Grafana URL.
---

# Grafana — Setup

## Auth method: SSO browser session

Grafana session cookies are captured after SSO login. No API token page needed for SSO-based instances.

**What to ask the user:** "Share your Grafana URL" (e.g. `https://grafana.acme.com`).

That is the only input needed. Set `GRAFANA_BASE_URL` in `.env`, then run the SSO script.

> **Alternative:** If your Grafana instance uses API keys instead of SSO, use `connection-api-key.md` instead (ask for the API key directly — no browser automation needed).

---

## Steps (SSO)

1. Set `GRAFANA_BASE_URL` in `.env` from the URL the user provided
2. Run the SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --grafana-only
```

On managed machines with enterprise SSO it completes automatically (~20–30s). On personal machines, complete the Grafana login once through the browser. `GRAFANA_SESSION` is written to `.env` automatically.

---

## Verify

```bash
source .env
curl -s "$GRAFANA_BASE_URL/api/user" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '{login, email, name}'
# → {"login": "alice", "email": "alice@example.com", "name": "Alice Smith"}
# If 401/redirect: session expired — run playwright_sso.py --grafana-only to refresh
# If connection refused: check GRAFANA_BASE_URL in .env
```

**Connection details:** `tool_connections/grafana/connection-sso.md`

---

## `.env` entries

```bash
# --- Grafana ---
# Short-lived (~8h) — refresh with: python3 tool_connections/shared_utils/playwright_sso.py --grafana-only
GRAFANA_BASE_URL=https://grafana.yourcompany.com
GRAFANA_SESSION=your-grafana-session-cookie-value
```

---

## Refresh

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --grafana-only
```

Token TTL: ~8h.
