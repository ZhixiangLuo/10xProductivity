---
name: miro-setup
description: Set up Miro connection. Auth is Okta SAML session token cookie. No input needed — run the SSO script and Okta auto-completes on managed Workday machine.
---

# Miro — Setup

## Auth method: Okta SAML session token (internal API)

Miro's official REST API (`api.miro.com/v2`) requires OAuth app registration. Instead, this uses the internal API (`miro.com/api/v1/`) with the `token` cookie the web app uses — zero setup beyond SSO.

**What to ask the user:** Nothing. Run the SSO script.

---

## Steps

```bash
source .venv/bin/activate
python3 personal/miro/sso.py
# Opens Chromium → navigates to miro.com → Okta SSO auto-completes
# Writes MIRO_TOKEN to .env
```

---

## Verify

```python
from pathlib import Path
import urllib.request, json, ssl
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://miro.com/api/v1/users/me/",
    headers={"Cookie": f"token={env['MIRO_TOKEN']}", "Accept": "application/json"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get("name"), r.get("email"))
# → Blake Tagget  blake.tagget@workday.com
# If 401: token expired — run sso.py --force
```

---

## `.env` entries

```bash
# --- Miro ---
# Refresh: source .venv/bin/activate && python3 personal/miro/sso.py --force
MIRO_TOKEN=your-token-here
```
