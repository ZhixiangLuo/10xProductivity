---
name: microsoft-teams-enterprise
auth: sso
description: Microsoft Teams Enterprise — read + post channel messages, DMs, thread replies, list conversations, search. Two MSAL tokens extracted from Teams web app localStorage via Playwright — no app registration or IT approval needed.
env_vars:
  - TEAMS_ENTERPRISE_GRAPH_TOKEN
  - TEAMS_ENTERPRISE_CHATSVC_TOKEN
---

# Microsoft Teams Enterprise — SSO (MSAL token)

Microsoft Teams enterprise (`teams.microsoft.com`) via Microsoft Graph API and Teams internal chatsvc API. Auth uses MSAL access tokens extracted from the Teams web app localStorage — no app registration needed.

API docs: https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview

**Verified:** Production (graph.microsoft.com + teams.cloud.microsoft, M365 Business Basic trial) — list teams, list channels, read + post channel messages, read + post 1:1 DMs, thread replies, search — 2026-04. No VPN required.

---

## Credentials

```bash
# Written automatically by sso.py — do not set manually:
# TEAMS_ENTERPRISE_GRAPH_TOKEN=<msal-graph-token>   — for /me, /joinedTeams, /channels, search
# TEAMS_ENTERPRISE_CHATSVC_TOKEN=<chatsvc-token>    — for read + post via teams.cloud.microsoft
# TTL: ~1h. Refresh: python3 tool_connections/microsoft-teams-enterprise/sso.py
```

---

## Auth

Two MSAL tokens extracted from Teams web app `localStorage` via Playwright persistent context. First run: log in + complete MFA in the browser window. Subsequent runs: saved Azure AD session auto-completes (~15s). Profile saved at `~/.browser_automation/teams_enterprise_profile/`.

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]

req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
    headers={"Authorization": f"Bearer {TOKEN}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r["displayName"], r["mail"])
# → Alice  alice@example.onmicrosoft.com
```

---

## Verified snippets

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl, urllib.error, time

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]
CSVC_TOKEN = env["TEAMS_ENTERPRISE_CHATSVC_TOKEN"]
GRAPH = "https://graph.microsoft.com"
CSVC_BASE = "https://teams.cloud.microsoft/api/chatsvc/amer/v1"

def gget(path, ver="v1.0"):
    req = urllib.request.Request(f"{GRAPH}/{ver}{path}",
        headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

def gpost(path, body, ver="v1.0"):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{GRAPH}/{ver}{path}", data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST")
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

def csvc_get(path):
    req = urllib.request.Request(f"{CSVC_BASE}{path}",
        headers={"Authorization": f"Bearer {CSVC_TOKEN}"})
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

def csvc_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{CSVC_BASE}{path}", data=data,
        headers={"Authorization": f"Bearer {CSVC_TOKEN}", "Content-Type": "application/json"},
        method="POST")
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

# --- List joined teams ---
code, r = gget("/me/joinedTeams")
for t in r["value"]:
    print(t["id"], t["displayName"])
# → <team-id>  My Team

# --- List channels in a team ---
TEAM_ID = "<team-id-from-above>"
code, r = gget(f"/teams/{TEAM_ID}/channels")
for c in r["value"]:
    print(c["id"], c["displayName"])
# → 19:xxx@thread.tacv2  General

# --- Read channel messages (beta required — v1.0 returns 403) ---
CHANNEL_ID = "19:xxx@thread.tacv2"
code, r = gget(f"/teams/{TEAM_ID}/channels/{CHANNEL_ID}/messages?$top=20", ver="beta")
for m in r.get("value", []):
    sender = (m.get("from") or {}).get("user", {}).get("displayName", "system")
    body = m["body"]["content"][:80].replace("\n", " ")
    print(f'[{m["createdDateTime"]}] {sender}: {body}')
# → [2026-04-05T23:32:53.38Z] Alice: <p>hello</p>
# → [2026-04-05T23:33:25.564Z] system: <systemEventMessage/>
# ⚠ Use beta endpoint — v1.0 returns 403 (ChannelMessage.Read.All not in scope)

# --- Search channel messages ---
# ⚠ Fresh tenants return 0 hits — search index takes hours/days to populate.
# entityType="message" searches channel messages. entityType="chatMessage" → 403 (needs Chat.Read).
code, r = gpost("/search/query",
    {"requests": [{"entityTypes": ["message"], "query": {"queryString": "your query"},
                   "from": 0, "size": 25}]}, ver="beta")
hits = r.get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])
for h in hits:
    print(h.get("summary", "")[:80])
# → Hello from the General channel   (once indexed)

# ============================================================
# CHATSVC: teams.cloud.microsoft internal API (read + post + DMs)
# ============================================================

# List ALL conversations — channels + DMs. Use to discover conversation IDs.
code, r = csvc_get("/users/ME/conversations?pageSize=20&view=msnp24Equivalent")
for c in r.get("conversations", []):
    print(c["id"], c["type"])
# → 48:notes  Conversation                                         (self-DM / Notes)
# → 19:xxx@thread.tacv2  Conversation                             (channel)
# → 19:{myOID}_{theirOID}@unq.gbl.spaces  Conversation           (1:1 DM)
# ⚠ members list is empty — conversation ID encodes the participants for 1:1 DMs

# ⚠ Conversation IDs must be URL-encoded: 19:xxx@thread.tacv2 → 19%3Axxx%40thread.tacv2
import urllib.parse
CHANNEL_CONV_ID = urllib.parse.quote("19:xxx@thread.tacv2", safe="")

# Read messages in any conversation (channel or DM)
code, r = csvc_get(f"/users/ME/conversations/{CHANNEL_CONV_ID}/messages"
                   "?view=msnp24Equivalent%7CsupportsMessageProperties&pageSize=20")
for m in r.get("messages", []):
    sender = m.get("imdisplayname", "system")
    body = str(m.get("content", ""))[:80]
    print(f'[{m.get("originalarrivaltime","?")}] {sender}: {body}')
# → [2026-04-05T23:32:53.3800000Z] Alice: <p>hello</p>
# ⚠ content is HTML — strip tags for plain text

# Post a message to a channel or DM
code, r = csvc_post(f"/users/ME/conversations/{CHANNEL_CONV_ID}/messages", {
    "content": "<p>Hello from agent</p>",
    "messagetype": "RichText/Html",
    "contenttype": "text",
    "amsreferences": [],
    "clientmessageid": str(int(time.time() * 1000)),
    "imdisplayname": "Alice",
    "properties": {"importance": "", "subject": ""},
})
print(code, r.get("OriginalArrivalTime"))
# → 201  1775432870703

# Reply to a thread (replyToId = OriginalArrivalTime of the parent message)
PARENT_MSG_ID = "1775432870703"
code, r = csvc_post(f"/users/ME/conversations/{CHANNEL_CONV_ID}/messages", {
    "content": "<p>Thread reply from agent</p>",
    "messagetype": "RichText/Html",
    "contenttype": "text",
    "amsreferences": [],
    "clientmessageid": str(int(time.time() * 1000)),
    "imdisplayname": "Alice",
    "properties": {"importance": "", "subject": ""},
    "replyToId": PARENT_MSG_ID,
})
print(code, r.get("OriginalArrivalTime"))
# → 201  1775433908905

# Self-DM (Notes to self) — hardcoded conversation ID
DM_SELF_ID = "48%3Anotes"
code, r = csvc_get(f"/users/ME/conversations/{DM_SELF_ID}/messages"
                   "?view=msnp24Equivalent%7CsupportsMessageProperties&pageSize=10")
# → 200, messages list

# 1:1 DM — conversation ID format: 19:{myOID}_{theirOID}@unq.gbl.spaces
# Discover via GET /users/ME/conversations, then URL-encode
DM_1_1_ID = urllib.parse.quote("19:{myOID}_{theirOID}@unq.gbl.spaces", safe="")
code, r = csvc_get(f"/users/ME/conversations/{DM_1_1_ID}/messages"
                   "?view=msnp24Equivalent%7CsupportsMessageProperties&pageSize=10")
# → 200, messages list
code, r = csvc_post(f"/users/ME/conversations/{DM_1_1_ID}/messages", {
    "content": "<p>Hello from agent</p>",
    "messagetype": "RichText/Html",
    "contenttype": "text",
    "amsreferences": [],
    "clientmessageid": str(int(time.time() * 1000)),
    "imdisplayname": "Alice",
    "properties": {"importance": "", "subject": ""},
})
# → 201

# What does NOT work with Graph token:
# GET /v1.0/me/chats → 403 (Chat.Read not in scope — use chatsvc instead)
# GET /v1.0/teams/{id}/channels/{id}/messages → 403 (use /beta)
# POST to channel via Graph → 403 (use chatsvc instead)
# POST /search/query entityType=chatMessage → 403 (needs Chat.Read)
```

---

## API surface

### Graph API (`TEAMS_ENTERPRISE_GRAPH_TOKEN`)

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/v1.0/me/joinedTeams` | ✅ | List teams you're a member of |
| GET | `/v1.0/teams/{id}/channels` | ✅ | List channels in a team |
| GET | `/beta/teams/{id}/channels/{id}/messages` | ✅ | Read channel messages (beta only — v1.0 → 403) |
| POST | `/beta/search/query` entityType=message | ✅ | Search channel messages (indexing lag on fresh tenants) |
| GET | `/v1.0/me/chats` | ❌ 403 | Chat.Read not in scope — use chatsvc instead |

### chatsvc API (`TEAMS_ENTERPRISE_CHATSVC_TOKEN`)
Base: `https://teams.cloud.microsoft/api/chatsvc/amer/v1`

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/users/ME/conversations?pageSize=N` | ✅ | List all conversations — channels + DMs |
| GET | `/users/ME/conversations/{id}/messages?pageSize=N` | ✅ | Read messages in any conversation |
| POST | `/users/ME/conversations/{id}/messages` | ✅ | Post to channel or DM (201 verified) |
| POST | `/users/ME/conversations/{id}/messages` + `replyToId` | ✅ | Reply to a thread (201 verified) |

---

## Notes

- **Two tokens, two API surfaces:**
  - `TEAMS_ENTERPRISE_GRAPH_TOKEN` — Graph API: list teams/channels, read messages via `/beta`, search
  - `TEAMS_ENTERPRISE_CHATSVC_TOKEN` — chatsvc: list all conversations, read + post messages, DMs, thread replies
- **Read messages:** Graph `/beta` or chatsvc both work. chatsvc content is HTML — strip tags for plain text.
- **Post messages:** chatsvc only — Graph POST → 403. Works for channels, self-DM, and 1:1 DMs.
- **Thread replies:** pass `replyToId` = `OriginalArrivalTime` from the parent message POST response.
- **Discover conversation IDs:** `GET /users/ME/conversations` returns every conversation. 1:1 DM format: `19:{myOID}_{theirOID}@unq.gbl.spaces`. Always URL-encode IDs before use.
- **Self-DM:** hardcoded ID `48%3Anotes` (already encoded).
- **Search:** Graph `/beta/search/query` with `entityType=message`. Fresh tenants have indexing lag — allow hours/days.
- **chatsvc region:** `amer` in the base URL — adjust for non-AMER tenants (`emea`, `apac`).
- **Token TTL:** ~1h. Re-run `sso.py` to refresh. Persistent browser profile handles Azure AD SSO silently after first login.
- **No VPN required.**
