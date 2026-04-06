---
description: Set up OneNote connection. Reuses TEAMS_ENTERPRISE_GRAPH_TOKEN from the Microsoft Teams Enterprise connection — no additional auth needed.
---

# OneNote — Setup

## Auth method: sso (shared token)

OneNote is accessed via the Graph OneNote API using the same `TEAMS_ENTERPRISE_GRAPH_TOKEN` from the Teams Enterprise connection. No additional setup if that connection is already active.

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
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me/onenote/notebooks",
    headers={"Authorization": f"Bearer {TOKEN}"})
r = json.loads(urllib.request.urlopen(req, timeout=10).read())
for nb in r.get("value", []):
    print(nb["displayName"], nb["id"])
# → My Notebook  1-c3d4e5f6-1a2b-3c4d-5e6f-7a8b9c0d1e2f
# If 401: run sso.py to refresh
```

**Connection details:** `tool_connections/onenote/connection-sso.md`

---

## `.env` entries

```bash
# OneNote — no additional env vars needed
# Uses: TEAMS_ENTERPRISE_GRAPH_TOKEN (set by microsoft-teams-enterprise/sso.py)
```

---

## Refresh

Same token as Teams Enterprise. TTL: ~1h.

```bash
source .venv/bin/activate
python3 tool_connections/microsoft-teams-enterprise/sso.py
```
