---
tool: microsoft-teams-personal
auth: sso
author: zhixiangluo
verified: 2026-03
env_vars:
  - TEAMS_SKYPETOKEN
  - TEAMS_SESSION_ID
  - TEAMS_BASE_URL
---

# Microsoft Teams (personal) — SSO session (teams.live.com)

Microsoft Teams (personal) is the personal/consumer variant of Teams, accessed at `https://teams.live.com/v2/`. It uses a private API at `teams.live.com/api/` authenticated via a Skype-derived session token (`x-skypetoken`). This is separate from enterprise Teams (teams.microsoft.com), which uses Microsoft Graph API.

**⚠ Private API:** These endpoints are undocumented and not officially supported by Microsoft for third-party use. They may change without notice. Enterprise Teams users (work/school accounts) should use Microsoft Graph API instead.

**Verified:** Production (teams.live.com) — `/api/csa/api/v1/teams/users/me` + `/api/csa/api/v1/teams/users/me/updates` — 2026-03. No VPN required. Token capture via Playwright network header interception.

---

## Credentials

```bash
# Add to .env:
# TEAMS_SKYPETOKEN=your-skypetoken-here
# TEAMS_SESSION_ID=your-session-id-here
# TEAMS_BASE_URL=https://teams.live.com
#
# Short-lived (~24h) — refresh with:
# python3 tool_connections/assets/playwright_sso.py --teams-only
```

---

## Auth setup

Teams (personal) does not offer an API token UI. Run the SSO script — it opens a Chromium window, you log in with your Microsoft personal account once, and tokens are written to `.env` automatically:

```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --teams-only
```

The script intercepts `x-skypetoken` from outgoing network request headers as the Teams app loads. On managed Azure AD machines this may auto-complete; on personal machines complete the Microsoft login once through the browser. Takes ~30–45s after login.

---

## Verify connection

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    f"{env['TEAMS_BASE_URL']}/api/csa/api/v1/teams/users/me",
    headers={"x-skypetoken": env["TEAMS_SKYPETOKEN"],
             "x-ms-session-id": env["TEAMS_SESSION_ID"]})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print("ok" if "metadata" in r else r)
# → ok
# If 401: token expired — run playwright_sso.py --teams-only to refresh
```

---

## Auth

Requests require two headers:
- `x-skypetoken`: your session token (captured from browser session, ~24h TTL)
- `x-ms-session-id`: UUID identifying the client session (captured alongside skypetoken or auto-generated)

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
skypetoken = env["TEAMS_SKYPETOKEN"]
session_id = env["TEAMS_SESSION_ID"]
BASE = env["TEAMS_BASE_URL"]

def teams_get(url, extra_headers=None):
    headers = {"x-skypetoken": skypetoken, "x-ms-session-id": session_id}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
```

---

## Verified snippets

```python
# List all chats — get chat IDs and member MRIs
r = teams_get(f"{BASE}/api/csa/api/v1/teams/users/me")
for c in r.get("chats", []):
    members = [m["mri"] for m in c.get("members", [])]
    print(c["id"], members)
# → 19:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@thread.v2  ['8:other_user', '8:live:.cid.xxxxxxxxxxxxxxxx']
# Own MRI is the live:.cid.* entry; chat IDs are needed for reading/sending messages.

# Read recent messages from a chat
import ssl as _ssl
_ctx = _ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = _ssl.CERT_NONE
CHAT_ID = "19:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@thread.v2"  # from chats list above
req = urllib.request.Request(
    f"https://msgapi.teams.live.com/v1/users/ME/conversations/{CHAT_ID}/messages"
    "?startTime=0&pageSize=5&view=msnp24Equivalent|supportsMessageProperties",
    headers={"authentication": f"skypetoken={skypetoken}", "x-ms-session-id": session_id})
with urllib.request.urlopen(req, context=_ctx, timeout=10) as resp:
    msgs = json.loads(resp.read()).get("messages", [])
for m in msgs[-3:]:
    print(f"[{m.get('originalarrivaltime','?')}] {m.get('imdisplayname','?')}: {m.get('content','')[:80]}")
# → [2026-03-17T16:28:34.1400000Z] Agent: Hello from agent — connection test
# → [2026-03-17T16:26:42.5060000Z] Alice: <p>hi</p>
# Note: content field contains HTML — strip tags for plain text.

# Send a message to a chat
import time as _time
payload = {
    "content": "Hello from 10xProductivity agent",
    "messagetype": "RichText/Html",
    "contenttype": "text",
    "amsreferences": [],
    "clientmessageid": str(int(_time.time() * 1000)),
    "imdisplayname": "Agent",
    "properties": {"importance": "", "subject": ""},
}
req = urllib.request.Request(
    f"https://msgapi.teams.live.com/v1/users/ME/conversations/{CHAT_ID}/messages",
    data=json.dumps(payload).encode(),
    headers={"authentication": f"skypetoken={skypetoken}",
             "x-ms-session-id": session_id,
             "content-type": "application/json;charset=UTF-8"},
    method="POST")
with urllib.request.urlopen(req, context=_ctx, timeout=10) as resp:
    r = json.loads(resp.read())
    print(f"HTTP {resp.status}", r)
# → HTTP 201 {"OriginalArrivalTime": 1773764914140}
# OriginalArrivalTime is milliseconds epoch — confirms delivery.
```

---

## API surface (verified working)

| Method | Endpoint | Auth headers | Description |
|--------|----------|-------------|-------------|
| GET | `/api/csa/api/v1/teams/users/me` | `x-skypetoken`, `x-ms-session-id` | List chats + member MRIs; verify token |
| GET | `https://msgapi.teams.live.com/v1/users/ME/conversations/{chatId}/messages?startTime=0&pageSize=N&view=msnp24Equivalent\|supportsMessageProperties` | `authentication: skypetoken=...`, `x-ms-session-id` | Read messages in a chat |
| POST | `https://msgapi.teams.live.com/v1/users/ME/conversations/{chatId}/messages` | `authentication: skypetoken=...`, `x-ms-session-id` | Send a message — returns `{"OriginalArrivalTime": ms}` |

---

## Notes

- **Private API only.** No official Microsoft documentation for these endpoints. Breaking changes are possible with any Teams update.
- **Personal accounts only.** Specific to `teams.live.com` (consumer/personal Teams (personal)). Enterprise Teams (work/school) uses a different API — Microsoft Graph at `graph.microsoft.com`.
- **No VPN required.** All confirmed endpoints are publicly routable.
- **Token TTL ~24h.** Run `playwright_sso.py --teams-only` to refresh.
- **MRI format.** User identifiers use `8:live:.cid.XXXXXXXX`. Chat IDs use `19:UUID@thread.v2`.
- **No search API.** All search endpoint patterns tested (`/api/mt/beta/search`, `/api/csa/api/v1/search`, POST variants, substrate.office.com, Bearer token variants) returned 401 or 404 with a valid skypetoken. Search appears to require a different token type (Azure AD OAuth2 Bearer) not accessible via this SSO flow. To search messages, fetch the full conversation history from `msgapi.teams.live.com` and filter client-side.
- **401 on `/api/mt/` endpoints.** The `/api/mt/beta/` namespace consistently returns 401 with skypetoken auth. These endpoints likely require an Azure AD Bearer token.
