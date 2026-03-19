---
name: microsoft-teams-setup
description: Set up Microsoft Teams connection. Supports personal accounts (teams.live.com) via SSO session. Enterprise Teams (teams.microsoft.com) not yet supported. Ask for any Teams link to detect the variant.
---

# Microsoft Teams — Setup

## Step 1: Ask for a URL to identify the variant

Ask the user: "Share any Teams link or message URL."

Infer variant from the URL:
- `teams.live.com` → **Teams (personal)** — use the flow below
- `teams.microsoft.com` → **Enterprise Teams** — not yet supported (contribution welcome via `add-new-tool.md`)

---

## Teams (personal) — SSO browser session

No API token page exists. Auth uses a Skype-derived session token captured from network headers.

**What to ask the user:** Nothing beyond the URL (used to confirm variant).

Run the SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --teams-only
```

The script opens a Chromium window. On managed Azure AD machines it may auto-complete. On personal machines, log in with your Microsoft personal account (~30–45s). `TEAMS_SKYPETOKEN` and `TEAMS_SESSION_ID` are written to `.env` automatically.

---

## Verify

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    f"{env['TEAMS_BASE_URL']}/api/csa/api/v1/teams/users/me",
    headers={"x-skypetoken": env["TEAMS_SKYPETOKEN"],
             "x-ms-session-id": env["TEAMS_SESSION_ID"]})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print("ok" if "metadata" in r else r)
# → ok
# If 401: token expired — run playwright_sso.py --teams-only to refresh
```

**Connection details:** `tool_connections/microsoft-teams/connection-personal-sso.md`

---

## `.env` entries

```bash
# --- Microsoft Teams (personal) ---
# Short-lived (~24h) — refresh with: python3 tool_connections/shared_utils/playwright_sso.py --teams-only
TEAMS_SKYPETOKEN=your-skypetoken-here
TEAMS_SESSION_ID=your-session-id-uuid-here
TEAMS_BASE_URL=https://teams.live.com
```

---

## Refresh

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --teams-only
```

Token TTL: ~24h.
