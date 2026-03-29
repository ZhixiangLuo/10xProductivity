# M365 Copilot Search — Setup

Microsoft 365 Copilot Search via Microsoft Graph Search API. Searches SharePoint files (OneDrive), calendar events, SharePoint sites, and list items. Pair with the Outlook connection for email search.

Requires a Microsoft 365 subscription with access to `m365.cloud.microsoft`.

## What to ask the user

Nothing — SSO auto-completes on managed Macs (macOS Enterprise SSO). On unmanaged machines, the user completes the login once when the browser opens.

## `.env` entries

```bash
# --- M365 Copilot Search
M365_SEARCH_TOKEN=your-token-here
# Token lifetime: ~1h
# Refresh: python3 tool_connections/m365-copilot-search/sso.py --force
```

## Setup

```bash
source .venv/bin/activate
python3 tool_connections/m365-copilot-search/sso.py
# → Opens browser → Azure AD SSO → captures M365_SEARCH_TOKEN → writes to .env
```

## Verify

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
tok = env["M365_SEARCH_TOKEN"]

body = json.dumps({"requests": [{"entityTypes": ["driveItem"],
                                  "query": {"queryString": "test"}, "from": 0, "size": 1}]}).encode()
req = urllib.request.Request("https://graph.microsoft.com/v1.0/search/query",
    data=body, headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, method="POST")
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
total = r["value"][0]["hitsContainers"][0].get("total", 0)
print(f"driveItem search: {total} hits — token valid")
# → driveItem search: N hits — token valid
# If 401: run sso.py --force to refresh
```
