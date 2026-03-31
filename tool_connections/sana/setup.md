---
name: sana-setup
description: Set up Sana Agents connection. Auth is Okta SAML session cookie + workspace ID header. No input needed — just run the SSO script and Okta auto-completes on managed Workday machine.
---

# Sana Agents — Setup

## Auth method: Okta SAML session cookie

Sana uses an Express session cookie (`sana-ai-session`) upgraded after Okta SAML auth, plus a static `sana-ai-workspace-id` header on every request.

**What to ask the user:** Nothing. Run the SSO script — Okta auto-completes on Workday managed machines.

---

## Steps

```bash
source .venv/bin/activate
python3 personal/sana/sso.py
# Opens Chromium → navigates to sana.ai → Okta SSO auto-completes
# Writes SANA_SESSION_COOKIE and SANA_WORKSPACE_ID to .env
```

---

## Verify

```python
from pathlib import Path
import urllib.request, json, ssl
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://sana.ai/x-api/trpc/assistantV2.list",
    headers={"Cookie": f"sana-ai-session={env['SANA_SESSION_COOKIE']}",
             "sana-ai-workspace-id": env["SANA_WORKSPACE_ID"],
             "Accept": "application/json"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
for a in r["result"]["data"]:
    print(a["name"])
# → Ask P&T Operations Agent
# → (list of available assistants)
# If 401: session expired — run sso.py --force
```

---

## `.env` entries

```bash
# --- Sana Agents ---
# Refresh with: source .venv/bin/activate && python3 personal/sana/sso.py --force
SANA_SESSION_COOKIE=s%3A...
SANA_WORKSPACE_ID=tPNxyS5GyK1r
```
