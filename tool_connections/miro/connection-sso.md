---
tool: miro
auth: sso-session
description: Miro — visual collaboration boards. Internal API at miro.com/api/v1/ using session token cookie captured after Okta SAML. No OAuth app needed. List boards, read board content, get org info.
env_vars:
  - MIRO_TOKEN
---

# Miro — SSO session

Visual collaboration platform. Uses internal API at `miro.com/api/v1/` — the same endpoints the web app uses. Auth is a single `token` cookie captured after Okta SAML.

⚠ This is NOT the official Miro REST API (`api.miro.com/v2/`), which requires OAuth app registration. The internal API works identically for reading and requires zero setup beyond SSO.

**Verified:** Production (miro.com) — users/me, recent-boards, boards list — 2026-03.

---

## Credentials

```bash
# .env:
# MIRO_TOKEN=your-token-here
# Refresh: source .venv/bin/activate && python3 personal/miro/sso.py --force
```

---

## Auth

Single cookie on every request: `Cookie: token=$MIRO_TOKEN`

```python
from pathlib import Path
import urllib.request, json, ssl

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

HEADERS = {"Cookie": f"token={env['MIRO_TOKEN']}", "Accept": "application/json"}
BASE = "https://miro.com/api/v1"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

def miro_get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
```

---

## Verified snippets

```python
# Current user + board list
r = miro_get("/users/me/")
print(r["name"], r["email"])
# → Blake Tagget  blake.tagget@workday.com

# Recent boards
boards = miro_get("/recent-boards")
for b in boards[:5]:
    print(b["id"], b["title"])
# → uXjVG2SJJdM=  P&T Consolidated Data Architecture
# → uXjVJUVcQCQ=  ...

# All boards in org (use lastKnownOrgId from user info)
org_id = "3074457349191543397"
r = miro_get(f"/organizations/{org_id}/boards/")
for b in r.get("data", []):
    print(b["id"], b["title"])

# Specific board
board = miro_get("/boards/uXjVGseOKNM%3D")
print(board["title"], board["description"])
# → 403 if no access to that board
```

---

## Refresh

```bash
source .venv/bin/activate
python3 personal/miro/sso.py --force
# Okta SSO auto-completes on managed Workday machine
```

---

## Notes

- Token is the `.miro.com` domain cookie named `token` — captured post-SAML
- Board IDs in URLs are base64 — pass URL-encoded when used in API paths (e.g. `uXjVGseOKNM%3D`)
- `miro.com/api/v1/` (internal) vs `api.miro.com/v2/` (official OAuth) — these are different APIs; this connection uses the internal one
- Token TTL: session-based, typically days; re-run `sso.py --force` on 401
