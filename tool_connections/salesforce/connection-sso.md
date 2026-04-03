---
name: salesforce
auth: browser-session
description: Salesforce CRM — query records, run SOQL/SOSL, read accounts/contacts/opportunities/cases via REST API. Use when querying or updating Salesforce data, searching records, or running reports.
env_vars:
  - SF_SID
  - SF_BASE_URL
  - SF_USERNAME
  - SF_PASSWORD
---

# Salesforce — Browser Session (SSO)

Salesforce CRM — records, accounts, contacts, opportunities, cases. Works on any Salesforce org: Developer Edition, Sandbox, Production, or Trailhead Playground.

API docs: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/

**Verified:** Production (your-org.my.salesforce.com) — userinfo, SOQL queries, sobjects list, SOSL search — 2026-04. No VPN required.

---

## Credentials

```bash
# Add to .env:
SF_USERNAME=you@example.com
SF_PASSWORD=yourpassword
SF_BASE_URL=https://your-org.my.salesforce.com
SF_SID=                         # captured by sso.py — leave blank, sso.py fills it in
```

Find your org's `my.salesforce.com` URL by logging in and checking the browser address bar (it differs from the `lightning.force.com` URL).

---

## Auth

Browser SSO via Playwright — logs in with username/password and captures the `sid` cookie from `{your-org}.my.salesforce.com`. Used as `Authorization: Bearer $SF_SID`.

⚠ Use the `sid` from `my.salesforce.com` only — the one from `lightning.force.com` returns 401 on REST API calls.
⚠ SOAP login() is disabled by default on newer orgs. OAuth connected apps require admin setup. Browser session capture is the zero-friction path that works on all org types.

```bash
source .venv/bin/activate && python3 tool_connections/salesforce/sso.py
# → ✓ SF_SID saved to .env
```

Token lifetime varies by org (Setup → Session Settings). Default is 2–8h. Re-run `sso.py --force` when you get 401s.

---

## Verified snippets

```bash
export $(grep -v '^#' .env | grep 'SF_' | xargs)
BASE="$SF_BASE_URL"

# Identity check — confirm token is valid and see logged-in user
curl -s "$BASE/services/oauth2/userinfo" \
  -H "Authorization: Bearer $SF_SID" | python3 -m json.tool
# → {"preferred_username": "alice@example.com", "name": "Alice Smith", "email": "alice@example.com", ...}

# SOQL query — list accounts
curl -s "$BASE/services/data/v63.0/query?q=SELECT+Id,Name+FROM+Account+LIMIT+5" \
  -H "Authorization: Bearer $SF_SID" | python3 -m json.tool
# → {"totalSize": 5, "done": true, "records": [{"attributes": {...}, "Id": "001...", "Name": "Acme Corp"}, ...]}

# List all available sObjects (Account, Contact, Opportunity, custom objects, etc.)
curl -s "$BASE/services/data/v63.0/sobjects/" \
  -H "Authorization: Bearer $SF_SID" | python3 -m json.tool
# → {"sobjects": [{"name": "Account", ...}, {"name": "Contact", ...}, ...]}

# SOSL full-text search across all objects
curl -s "$BASE/services/data/v63.0/search?q=FIND+%7Bacme%7D+IN+ALL+FIELDS" \
  -H "Authorization: Bearer $SF_SID" | python3 -m json.tool
# → {"searchRecords": [{"attributes": {"type": "Account", ...}, "Id": "001...", ...}]}

# Expired / invalid token
curl -s "$BASE/services/data/v63.0/query?q=SELECT+Id+FROM+Account+LIMIT+1" \
  -H "Authorization: Bearer invalid-token" | python3 -m json.tool
# → [{"message": "Session expired or invalid", "errorCode": "INVALID_SESSION_ID"}]
```

---

## Notes

- API version: v63.0 (latest as of 2026-04) — substitute earlier versions if needed (`/services/data/` returns all available versions)
- SOQL: `/services/data/v63.0/query?q=SELECT+...+FROM+{Object}+WHERE+...`
- SOSL (full-text): `/services/data/v63.0/search?q=FIND+%7Bterm%7D+IN+ALL+FIELDS`
- Token lifetime is org-configurable (Setup → Session Settings) — default 2h on production, up to "never" on dev orgs
- No connected app or admin approval needed — browser session works for all standard REST API calls
- Org URL format: `https://{org-name}.my.salesforce.com` — find it in the browser address bar after login
