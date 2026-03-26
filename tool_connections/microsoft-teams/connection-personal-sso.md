---
name: microsoft-teams-personal
auth: sso-session
description: Microsoft Teams (personal) — read and send messages in personal Teams chats via private SSO session. Use when reading chat history, sending messages, or listing chats for a personal Microsoft account (teams.live.com).
env_vars:
  - TEAMS_SKYPETOKEN
  - TEAMS_SESSION_ID
  - TEAMS_BASE_URL
---

# Microsoft Teams (personal)

Personal/consumer Microsoft Teams, accessed at `https://teams.live.com/v2/`. Uses a private API at `teams.live.com/api/` and `msgapi.teams.live.com/`, authenticated via a Skype-derived session token (`x-skypetoken`).

**⚠ Private API:** These endpoints are undocumented and not officially supported by Microsoft for third-party use. They may change without notice. Enterprise Teams users (work/school accounts at `teams.microsoft.com`) should use Microsoft Graph API instead.

Env: `TEAMS_SKYPETOKEN`, `TEAMS_SESSION_ID` (~24h — refresh with `python3 tool_connections/shared_utils/playwright_sso.py --teams-only`)
API docs: none (private API — community-discovered)

**Verified:** Production (teams.live.com + msgapi.teams.live.com) — list chats, read messages, send message — 2026-03. No VPN required. Personal Microsoft account. Token capture via Playwright network header interception.

---

## Auth setup

Teams (personal) has no API token page. Run the SSO script — it opens a Chromium window, you log in with your Microsoft personal account once, and tokens are written to `.env` automatically:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --teams-only
```

The script intercepts `x-skypetoken` from outgoing network request headers as the Teams app loads. On managed Azure AD machines this may auto-complete; on personal machines complete the Microsoft login once through the browser (~30–45s after login).

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

## Quick-reference snippets (verified)

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl, time

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

# List all chats — returns chat IDs and member MRIs
r = teams_get(f"{BASE}/api/csa/api/v1/teams/users/me")
for c in r.get("chats", []):
    members = [m["mri"] for m in c.get("members", [])]
    print(c["id"], members)
# → 19:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@thread.v2  ['8:other_user', '8:live:.cid.xxxxxxxxxxxxxxxx']
# Own MRI is the live:.cid.* entry. Chat IDs are needed for reading/sending.
# Returns empty list if account has no active chats.

# Read recent messages from a chat
CHAT_ID = "<chat-id-from-above>"   # e.g. "19:xxxxxxxx@thread.v2"
req = urllib.request.Request(
    f"https://msgapi.teams.live.com/v1/users/ME/conversations/{CHAT_ID}/messages"
    "?startTime=0&pageSize=20&view=msnp24Equivalent|supportsMessageProperties",
    headers={"authentication": f"skypetoken={skypetoken}", "x-ms-session-id": session_id})
with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
    msgs = json.loads(resp.read()).get("messages", [])
for m in msgs[-5:]:
    print(f"[{m.get('originalarrivaltime','?')}] {m.get('imdisplayname','?')}: {m.get('content','')[:80]}")
# → [2026-03-17T16:28:34.1400000Z] Agent: Hello from 10xProductivity agent — connection test 2026-03-17
# → [2026-03-17T16:26:42.5060000Z] Alice: <p>hi</p>
# Note: content field contains HTML — strip tags for plain text.

# Send a message to a chat
payload = {
    "content": "Hello from 10xProductivity agent",
    "messagetype": "RichText/Html",
    "contenttype": "text",
    "amsreferences": [],
    "clientmessageid": str(int(time.time() * 1000)),
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
with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
    r = json.loads(resp.read())
    print(f"HTTP {resp.status}", r)
# → HTTP 201 {"OriginalArrivalTime": 1773764914140}   # milliseconds epoch timestamp
```

---

## Full API surface (verified working)

| Method | Endpoint | Auth headers | Description |
|--------|----------|-------------|-------------|
| GET | `{BASE}/api/csa/api/v1/teams/users/me` | `x-skypetoken`, `x-ms-session-id` | List all chats + member MRIs; verify token via `metadata.syncToken` |
| GET | `https://msgapi.teams.live.com/v1/users/ME/conversations/{chatId}/messages?startTime=0&pageSize=N&view=msnp24Equivalent\|supportsMessageProperties` | `authentication: skypetoken=...`, `x-ms-session-id` | Read messages in a chat |
| POST | `https://msgapi.teams.live.com/v1/users/ME/conversations/{chatId}/messages` | `authentication: skypetoken=...`, `x-ms-session-id` | Send a message — returns `{"OriginalArrivalTime": ms}` |

---

## Notes

- **No search API.** All search endpoint patterns (`/api/mt/beta/search`, `/api/csa/api/v1/search`, POST variants, substrate.office.com, Bearer token variants) returned 401 or 404 with a valid skypetoken. Search requires an Azure AD OAuth2 Bearer token, not accessible via this SSO flow. Workaround: fetch full conversation history and filter client-side.
- **`/api/mt/` endpoints return 401.** The `/api/mt/beta/` namespace requires an Azure AD Bearer token, not skypetoken.
- **Personal accounts only.** For enterprise Teams (work/school), use Microsoft Graph API (`graph.microsoft.com`).
- **MRI format.** Own user identifier: `8:live:.cid.XXXXXXXXXXXXXXXX`. Chat IDs: `19:UUID@thread.v2`.
- **HTML content.** The `content` field in messages contains HTML (`RichText/Html` type). Strip tags for plain text.
