---
description: Set up Microsoft Teams Enterprise connection. Auth via MSAL token extracted from Teams web app (teams.microsoft.com) using Playwright SSO — no API token page, no app registration needed.
---

# Microsoft Teams Enterprise — Setup

## Auth method: sso

Teams enterprise has no personal API token page. Auth uses MSAL access tokens extracted from the Teams web app's localStorage cache via Playwright. Two tokens are captured: one scoped to `graph.microsoft.com` and one for the Teams internal chatsvc API. Tokens are captured automatically on first run — complete MFA in the Playwright window once, then the saved browser profile handles subsequent refreshes silently.

**What to ask the user:**
- Nothing. Just run `sso.py` — it opens teams.microsoft.com in a browser window. Complete MFA once if prompted.

---

## Steps

1. Run the SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/microsoft-teams-enterprise/sso.py
```

2. A browser window opens at `teams.microsoft.com`. If not logged in, sign in with your M365 account and complete MFA. If the profile is already saved, it auto-completes.

3. Once Teams loads, the script extracts `TEAMS_ENTERPRISE_GRAPH_TOKEN` and `TEAMS_ENTERPRISE_CHATSVC_TOKEN` from localStorage and writes them to `.env`.

---

## Verify

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
    headers={"Authorization": f"Bearer {env['TEAMS_ENTERPRISE_GRAPH_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, timeout=10).read())
print(r["displayName"], r["mail"])
# → Alice  alice@example.onmicrosoft.com
# If 401: run sso.py to refresh
```

**Connection details:** `tool_connections/microsoft-teams-enterprise/connection-sso.md`

---

## `.env` entries

```bash
# --- Microsoft Teams Enterprise ---
TEAMS_ENTERPRISE_GRAPH_TOKEN=your-msal-graph-token-here
TEAMS_ENTERPRISE_CHATSVC_TOKEN=your-chatsvc-token-here
# Both captured automatically by sso.py — do not set manually
# TTL: ~1h. Refresh: python3 tool_connections/microsoft-teams-enterprise/sso.py
```

---

## Refresh

Token TTL: ~1h. Re-run `sso.py` to refresh. The persistent browser profile at `~/.browser_automation/teams_enterprise_profile/` handles Azure AD SSO silently after the first login — no MFA prompt on subsequent runs.

```bash
source .venv/bin/activate
python3 tool_connections/microsoft-teams-enterprise/sso.py
```
