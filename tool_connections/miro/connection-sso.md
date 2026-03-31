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

**Verified:** Production (miro.com) — users/me, recent-boards, boards list, frames, board content — 2026-03-31.

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

## API Patterns

See `api-patterns.md` for the full reference: verified endpoints, board content extraction, widget schema, frame membership, and confirmed 404s. **Read that file before writing Miro API code** — the `/widgets/` endpoint is a trap.

## Verified snippets

```python
import urllib.parse

# Current user
r = miro_get("/users/me/")
print(r["name"], r["email"])

# Recent boards (returns a list directly, not {"data": [...]})
boards = miro_get("/recent-boards")
for b in boards[:5]:
    print(b["id"], b["title"])

# Frames in a board (with titles and positions)
board_id = urllib.parse.quote("BOARD_ID=", safe="")
frames = miro_get(f"/boards/{board_id}/frames")
for f in frames["data"]:
    print(f["id"], f["title"])

# Full board content — ALL widget text, positions, parent frames
# /widgets/ returns stubs only — use /content instead
import re, html
def strip_html(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()

r = miro_get(f"/boards/{board_id}/content")
for w in r["content"]["widgets"]:
    cod = w["canvasedObjectData"]
    if cod["type"] not in ("shape", "sticker") or not cod.get("json"):
        continue
    import json as _json
    data = _json.loads(cod["json"])
    text = strip_html(data.get("text", ""))
    parent = data.get("_parent")
    parent_id = parent["id"] if isinstance(parent, dict) else parent
    if text:
        print(f"[{cod['type']}] parent={parent_id} | {text[:80]}")
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
