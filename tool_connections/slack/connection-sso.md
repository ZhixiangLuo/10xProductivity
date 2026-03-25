---
name: slack
auth: sso-session
description: Slack — two complementary modes. (1) Slack AI: post a natural-language question to the Slackbot DM and get a synthesized AI answer in ~0.2s, drawn from all Slack content you have access to. (2) search.messages: raw full-text search with Slack syntax (in:#channel, from:user, date range). Also: read channel/thread history, post messages. No Slack app install needed — xoxc user session via SSO.
env_vars:
  - SLACK_XOXC
  - SLACK_D_COOKIE
---

# Slack

Access is via your own user session (`xoxc` client token) extracted after SSO — no Slack app installation or admin approval needed.

Env: `SLACK_XOXC`, `SLACK_D_COOKIE` (~8h — refresh via `python3 tool_connections/shared_utils/playwright_sso.py --slack-only`)

---

## Verify connection

```python
# ⚠ Always use Python to load .env — bash truncates long xoxc tokens silently
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://slack.com/api/auth.test",
    headers={"Authorization": f"Bearer {env['SLACK_XOXC']}", "Cookie": f"d={env['SLACK_D_COOKIE']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get("ok"), r.get("user"), r.get("team"))
# → True alice your-workspace
```

## Auth setup

**Minimum user input:** ask for a Slack message link (right-click any message → Copy link, e.g. `https://acme.slack.com/archives/C.../p...`).

Extract workspace URL (`https://acme.slack.com/`), update `SLACK_WORKSPACE_URL` in `.env`, then run:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --slack-only
```

The script opens Chromium, completes SSO, and writes `SLACK_XOXC` and `SLACK_D_COOKIE` to `.env` automatically.

---

## Choosing the right method

**Use `search.messages` for:**
- Time-specific queries: "my activity today", "messages this week", "what happened yesterday"
- Finding specific messages, people, or keywords with date filters
- When you need exact timestamps and message metadata

**Use Slack AI for:**
- Open-ended knowledge questions: "how do we handle X?", "what's our policy on Y?"
- Synthesized answers drawn from multiple channels
- When you want AI to summarize and cite sources

**⚠ Critical:** Slack AI cannot reliably filter by specific dates. For date-specific queries, always use `search.messages` with `after:` / `before:` filters.

---

## Slack AI — synthesized answers

**Requires:** Slack Business+ or Enterprise+ plan (not available on Free/Pro as of Jan 2026)

**Pattern:** Post question to Slackbot DM → poll `conversations.replies` for response with `subtype='ai'`

**⚠ Key gotcha:** Response arrives in ~0.2s — poll immediately with 1s sleep, not with long delay

```python
import json, ssl, time, urllib.request, urllib.parse
from pathlib import Path

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
xoxc, d = env["SLACK_XOXC"], env["SLACK_D_COOKIE"]

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def api(method, endpoint, data=None, params=None):
    url = f"https://slack.com/api/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url,
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {xoxc}", "Cookie": f"d={d}",
                 "Content-Type": "application/json; charset=utf-8"},
        method=method)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
        return json.loads(resp.read())

# Get Slackbot DM ID (USLACKBOT is fixed across all workspaces)
r = api("POST", "conversations.open", {"users": "USLACKBOT"})
slackbot_dm = r["channel"]["id"]

# Post question
r = api("POST", "chat.postMessage", {"channel": slackbot_dm, "text": "how do we handle on-call escalations?"})
msg_ts = r["ts"]

# Poll for AI response (arrives in ~0.2s, poll with 1s sleep)
for _ in range(60):
    time.sleep(1)
    r = api("GET", "conversations.replies", params={"channel": slackbot_dm, "ts": msg_ts, "limit": "20"})
    ai_replies = [m for m in r.get("messages", [])
                  if float(m.get("ts", "0")) > float(msg_ts) and m.get("subtype") == "ai"]
    if ai_replies:
        # Parse blocks to extract answer (you can access msg["blocks"] for rich text, or msg["text"] for plain)
        print(ai_replies[-1])
        break
```

**Multi-turn:** Pass `thread_ts` to `chat.postMessage` to continue conversation in same thread.

---

## search.messages — date-filtered search

**Best for:** Time-specific queries, keyword search with precise date filtering

**Syntax:** `from:@me after:2026-03-24`, `in:#channel keyword`, `from:alice before:2026-01-01`

```python
# Using api() helper from above
today = "2026-03-24"  # or: from datetime import datetime; datetime.now().strftime("%Y-%m-%d")

r = api("GET", "search.messages",
        params={"query": f"from:@me after:{today}", "count": "50", "sort": "timestamp"})

matches = r.get("messages", {}).get("matches", [])
for m in matches:
    print(f"{m.get('channel', {}).get('name')}: {m.get('text', '')[:100]}")
```

**Search operators:**
- `in:#channel-name` — specific channel
- `from:@username` — by author
- `after:YYYY-MM-DD` / `before:YYYY-MM-DD` — date filter
- `has:link` / `has:file` — filter by content type

---

## Read thread from URL

```python
import re

# URL: https://acme.slack.com/archives/C08E6GQMLP6/p1773406713930289
m = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", slack_url)
channel_id = m.group(1)
ts = m.group(2)[:10] + "." + m.group(2)[10:]  # p1773406713930289 → 1773406713.930289

r = api("GET", "conversations.replies", params={"channel": channel_id, "ts": ts, "limit": "50"})
messages = r.get("messages", [])
```

---

## API reference

| Endpoint | What it does | Key params |
|----------|-------------|------------|
| `auth.test` | Verify token, get user/team | — |
| `chat.postMessage` | Post a message | `channel`, `text`, `thread_ts` (optional) |
| `conversations.open` | Open DM with user | `users` (e.g., `"USLACKBOT"`) |
| `conversations.replies` | Fetch thread / poll for Slack AI | `channel`, `ts` (thread root), `limit` |
| `conversations.history` | Read recent channel messages | `channel`, `limit` |
| `search.messages` | Full-text search with date filters | `query`, `count`, `sort` |
| `users.info` | Look up user by ID | `user` |

---

## URL patterns

- Channel/DM URL: `.../archives/{CHANNEL_ID}/p{TS_NO_DOT}`
- `D...` = DM, `C...` = channel, `G...` = group DM
- Timestamp: `p1773406713930289` → `1773406713.930289`
