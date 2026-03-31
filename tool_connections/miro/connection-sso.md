---
name: miro
auth: sso-session
description: Miro — boards via internal miro.com/api/v1 using session token cookie after browser SSO. No OAuth app. List boards, user profile, board metadata.
env_vars:
  - MIRO_TOKEN
---

# Miro — SSO session (internal API)

Uses **`https://miro.com/api/v1/`** — the same JSON API the web client calls — with the **`token`** cookie captured after sign-in (SAML, Google, email, etc.).

⚠ **Not** the official [Miro REST API](https://developers.miro.com/docs/rest-api-reference) (`api.miro.com/v2/`), which requires a Developer OAuth app. Internal routes may change without notice.

**CLI helper:** `python3 tool_connections/miro/read_miro.py` (from repo root).

**Verified:** Production (`miro.com`) — `GET /api/v1/users/me/` with cookie → 200 when session valid; without cookie → **401** auth error JSON — 2026-03. `/recent-boards`, `/organizations/{id}/boards/` — 2026-03. No VPN required for public Miro.

---

## Credentials

```bash
# .env (written by playwright_sso.py --miro-only or tool_connections/miro/sso.py):
# MIRO_TOKEN=your-token-here
```

---

## Auth

```http
Cookie: token=$MIRO_TOKEN
Accept: application/json
```

Some corporate SSL inspection requires disabling verify in quick probes (see snippets below). Prefer system trust where possible.

---

## Snippets (stdlib)

```python
from pathlib import Path
import json, ssl, urllib.request

def load_env():
    p = Path(".env")
    return {k.strip(): v.strip() for line in p.read_text().splitlines()
            if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

env = load_env()
HEADERS = {"Cookie": f"token={env['MIRO_TOKEN']}", "Accept": "application/json"}
BASE = "https://miro.com/api/v1"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def miro_get(path: str):
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read())

me = miro_get("/users/me/")
# → JSON with profile fields (shape varies by account)

boards = miro_get("/recent-boards")
# → list or object with recent boards (shape may vary)

org_id = me.get("lastKnownOrgId") or me.get("organization", {}).get("id")
r = miro_get(f"/organizations/{org_id}/boards/")
for b in r.get("data", []):
    print(b.get("id"), b.get("title"))
# → 403 if no access to org/boards
```

**Unauthenticated check:**

```bash
curl -sS "https://miro.com/api/v1/users/me/" -w "\nHTTP:%{http_code}\n" | tail -3
# → 401 — token required
```

Board ids in paths often need **URL encoding** (e.g. `%3D` for `=`).

---

## Refresh

```bash
python3 tool_connections/shared_utils/playwright_sso.py --miro-only --force
```

---

## Notes

- **`token`** is set on **miro.com** after successful login.
- **403** on a board: no access to that board.
- **`read_miro.py --org`:** Uses `/organizations/{id}/boards/` when `lastKnownOrgId` exists on `/users/me/`; otherwise falls back to **`boards.data`** on `/users/me/` (often a subset — use **`--recent`** for the full recent list).
- **Enterprise:** If browser SSO is blocked, this path fails the same way the web app would.
