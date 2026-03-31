---
tool: sana
auth: sso-session
description: Sana Agents — AI assistant with search, chat, and knowledge tools. tRPC API at sana.ai/x-api/trpc/. Auth requires sana-ai-session cookie (captured after Okta SAML) AND sana-ai-workspace-id header. Cookie-only calls return 401 for workspace-scoped endpoints.
env_vars:
  - SANA_SESSION_COOKIE
  - SANA_WORKSPACE_ID
---

# Sana Agents — SSO session

AI assistant and knowledge platform at sana.ai. tRPC API — all endpoints at `https://sana.ai/x-api/trpc/{procedure}`.

**Verified:** Production (sana.ai) — user.me, assistantV2.list — 2026-03.

---

## Credentials

```bash
# .env entries:
# SANA_SESSION_COOKIE=s%3A...   (from sso.py — refreshed after Okta session expires)
# SANA_WORKSPACE_ID=tPNxyS5GyK1r  (static — workspace ID from invite URL)
# Refresh: source .venv/bin/activate && python3 personal/sana/sso.py --force
```

---

## Auth

⚠ Two things required on every request:
1. `Cookie: sana-ai-session=$SANA_SESSION_COOKIE`
2. `sana-ai-workspace-id: $SANA_WORKSPACE_ID`

`user.me` works without the workspace header (pre-auth endpoint). All other endpoints return 401 without it.

The session cookie is upgraded to a workspace session only after Okta SAML completes (`POST /x-api/auth/saml`). `sso.py` waits for this response before capturing.

```python
from pathlib import Path
import urllib.request, json, ssl

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

HEADERS = {
    "Cookie": f"sana-ai-session={env['SANA_SESSION_COOKIE']}",
    "sana-ai-workspace-id": env["SANA_WORKSPACE_ID"],
    "Accept": "application/json",
}
BASE = "https://sana.ai/x-api/trpc"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

def trpc_get(procedure):
    req = urllib.request.Request(f"{BASE}/{procedure}", headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
```

---

## Verified snippets

```python
# Current user
r = trpc_get("user.me")
print(r["result"]["data"]["user"]["email"])
# → blake.tagget@workday.com

# List assistants
r = trpc_get("assistantV2.list")
for a in r["result"]["data"]:
    print(a["name"])
# → Ask P&T Operations Agent
# → ...

# List recent assets
# → 400 (requires input param — not yet determined)
```

---

## Chat (POST)

Chat endpoint pattern observed: `POST /x-api/agent-v2/chat/{chatId}/messages`

```python
import json as _json
chat_id = "5oiRUZBhFBF7"   # from assistantV2.list or create new chat
post_headers = {**HEADERS, "Content-Type": "application/json"}
body = _json.dumps({"message": "hello"}).encode()
req = urllib.request.Request(
    f"https://sana.ai/x-api/agent-v2/chat/{chat_id}/messages",
    data=body, headers=post_headers, method="POST"
)
# Response is streaming SSE — read chunks
with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
    for line in r:
        print(line.decode())
```

---

## Refresh

```bash
source .venv/bin/activate
python3 personal/sana/sso.py --force
# Opens Chromium → Okta SSO auto-completes → writes updated cookie to .env
```

---

## Notes

- `sana-ai-workspace-id` header is required for all workspace-scoped endpoints — omitting it returns 401 with no error message
- SAML flow goes through `workday.okta.com` — auto-completes on managed Workday machine
- Session TTL unknown — re-run `sso.py --force` if 401s appear
- `workday.sana.ai` is a separate product (Sana Learn/LMS) — do not confuse with this workspace
