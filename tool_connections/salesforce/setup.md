# Salesforce — Setup

Works on any Salesforce org: Developer Edition, Sandbox, Production, or Trailhead Playground.

## What to ask the user

Ask for a URL from the org (any page after login — reveals the org base URL). Then ask for username and password if not already in `.env`.

## .env entries

```bash
SF_USERNAME=you@example.com
SF_PASSWORD=yourpassword
SF_BASE_URL=https://your-org.my.salesforce.com
SF_SID=                         # filled in by sso.py
```

Find `SF_BASE_URL` from the browser: after logging in at login.salesforce.com, the address bar shows `https://{org-name}.my.salesforce.com` (not the `lightning.force.com` variant — use `my.salesforce.com`).

## First-time setup

```bash
source .venv/bin/activate
python3 tool_connections/salesforce/sso.py
```

A browser window opens, logs in automatically using credentials from `.env`, and saves `SF_SID` to `.env`.

## Verify

```bash
export $(grep -v '^#' .env | grep 'SF_' | xargs)
curl -s "$SF_BASE_URL/services/oauth2/userinfo" \
  -H "Authorization: Bearer $SF_SID" | python3 -m json.tool
# → {"name": "Alice Smith", "preferred_username": "alice@example.com", ...}
```

## Refresh

Token expires based on org Session Settings (default 2–8h). Re-run:

```bash
source .venv/bin/activate && python3 tool_connections/salesforce/sso.py --force
```
