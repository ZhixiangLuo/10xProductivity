---
name: outlook-setup
description: Set up Outlook connection. Supports M365 work accounts (SSO) and personal Outlook.com accounts (token capture). Ask for any Outlook URL to detect the variant.
---

# Outlook — Setup

## Step 1: Ask for a URL to identify the variant

Ask the user: "Share any Outlook link or email URL."

Infer variant from the URL:
- `outlook.office.com` or `office365` or `office.com` → **Outlook / Microsoft 365** (work account) → `connection-m365.md`
- `outlook.live.com` or `outlook.com` → **Outlook.com** (personal account) → `connection-personal.md`

---

## Variant A: Outlook / Microsoft 365 (work account)

Auth uses two Bearer tokens captured from network requests as Outlook loads. No API token page exists — run the SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --outlook-only
```

On a managed machine (Workday/Intune/MDM), Azure AD SSO auto-completes in ~30s. On unmanaged machines, complete the Microsoft 365 login once through the browser.

Two tokens are written to `.env`:
- `GRAPH_ACCESS_TOKEN` — for Microsoft Graph (`/me`, `/me/people`)
- `OWA_ACCESS_TOKEN` — for Outlook REST API v2.0 (mail, calendar, contacts)

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
    headers={"Authorization": f"Bearer {env['GRAPH_ACCESS_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r["displayName"], r["mail"])
# → Alice Smith  alice@yourcompany.com
# If 401: token expired — run playwright_sso.py --outlook-only to refresh
```

Token TTL: ~1h. **Connection details:** `tool_connections/outlook/connection-m365.md`

---

## Variant B: Outlook.com (personal account)

```bash
source .venv/bin/activate
python3 tool_connections/outlook/get_outlook_token.py
```

A browser window opens to `outlook.live.com/mail/inbox`. If already logged in (session < ~24h) the token is captured in ~15s. Result: `OUTLOOK_ACCESS_TOKEN` written to `.env`.

**Verify:**
```python
from pathlib import Path
import urllib.request, json, ssl
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    "https://outlook.live.com/api/v2.0/me/mailfolders/inbox/messages?$top=1&$select=Subject",
    headers={"Authorization": f"Bearer {env['OUTLOOK_ACCESS_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get("value", [{}])[0].get("Subject"))
# → Subject of most recent email
```

Token TTL: ~1h. Session TTL: ~24h. **Connection details:** `tool_connections/outlook/connection-personal.md`

---

## `.env` entries

```bash
# --- Outlook / Microsoft 365 (work account) ---
# Short-lived (~1h) — refresh with: python3 tool_connections/shared_utils/playwright_sso.py --outlook-only
GRAPH_ACCESS_TOKEN=your-graph-bearer-token-here
OWA_ACCESS_TOKEN=your-owa-bearer-token-here

# --- Outlook.com (personal account) ---
# Short-lived (~1h) — refresh with: python3 tool_connections/outlook/get_outlook_token.py
OUTLOOK_ACCESS_TOKEN=your-outlook-access-token
```
