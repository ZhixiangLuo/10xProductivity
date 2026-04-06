---
description: Set up SharePoint / OneDrive connection. Reuses TEAMS_ENTERPRISE_GRAPH_TOKEN from the Microsoft Teams Enterprise connection — no additional auth needed.
---

# SharePoint / OneDrive — Setup

## Auth method: sso (shared token)

SharePoint and OneDrive are accessed via the same `TEAMS_ENTERPRISE_GRAPH_TOKEN` from the Teams Enterprise connection. No additional setup if that connection is already active.

**What to ask the user:**
- Nothing, if `microsoft-teams-enterprise` is already connected.
- If not: run `python3 tool_connections/microsoft-teams-enterprise/sso.py` first.

---

## Steps

1. Confirm the token is present:

```bash
grep TEAMS_ENTERPRISE_GRAPH_TOKEN .env
# → TEAMS_ENTERPRISE_GRAPH_TOKEN=eyJhbGciOi...
```

2. If missing, run the Teams Enterprise SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/microsoft-teams-enterprise/sso.py
# → Opening Teams (https://teams.microsoft.com/) — login auto-completes if profile is saved...
# → Graph token found (1842 chars)
# → Written to .env
```

---

## Verify

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json
TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me/drive",
    headers={"Authorization": f"Bearer {TOKEN}"})
r = json.loads(urllib.request.urlopen(req, timeout=10).read())
print(r["driveType"], r["name"], r["quota"]["used"], "bytes used")
# → business  OneDrive  109889 bytes used
# If 401: run sso.py to refresh
```

**Connection details:** `tool_connections/sharepoint-onedrive/connection-sso.md`

---

## `.env` entries

```bash
# SharePoint / OneDrive — no additional env vars needed
# Uses: TEAMS_ENTERPRISE_GRAPH_TOKEN (set by microsoft-teams-enterprise/sso.py)
```

---

## Refresh

Same token as Teams Enterprise. TTL: ~1h.

```bash
source .venv/bin/activate
python3 tool_connections/microsoft-teams-enterprise/sso.py
```
