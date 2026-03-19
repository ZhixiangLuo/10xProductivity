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

Env: `SLACK_XOXC`, `SLACK_D_COOKIE` (~8h — refresh via `assets/playwright_sso.py --slack-only`)

---

## Verify connection

```python
# Always use Python to load .env — bash truncates long xoxc tokens silently
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
# If ok=False: session expired — run playwright_sso.py --slack-only to refresh.
```

## Auth setup

**Minimum user input:** ask for a Slack message link (right-click any message → Copy link, e.g. `https://acme.slack.com/archives/C.../p...`). That's it.

From the link, extract the workspace URL yourself (`https://acme.slack.com/`), update `SLACK_WORKSPACE_URL` in `.env`, then run:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --slack-only
```

The script opens a Chromium window, completes SSO (auto on managed machines, manual login once on personal machines), and writes `SLACK_XOXC` and `SLACK_D_COOKIE` to `.env` automatically. Never ask the user to open DevTools or extract tokens manually.

```bash
# Refresh all tokens (Grafana + Slack in one pass):
python3 tool_connections/shared_utils/playwright_sso.py
```

**⚠ Load credentials in Python, not bash `source .env`** — xoxc tokens are long and bash may truncate them silently, causing `not_authed`. Always read `.env` directly in Python:

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
xoxc, d = env["SLACK_XOXC"], env["SLACK_D_COOKIE"]
```

---

## Slack AI — ask questions, get synthesized answers

**Requires: Slack Business+ or Enterprise+ plan.** Slack AI is not available on Free or Pro plans (as of January 2026). If the workspace is on a lower plan, skip this section — use `search.messages` instead for message search.

**Best for:** natural-language questions ("how do I X?", "what did we decide about Y?", "who owns Z?"). Slack AI searches all channels you have access to and synthesizes a cited answer.

**How it works:** post your question to your Slackbot DM channel. Slack AI responds in the *thread* with `subtype='ai'` in ~0.2s. Poll `conversations.replies` on the thread ts.

**Key gotcha:** response arrives in ~0.2s — start polling immediately (1s sleep), not with a long delay.

```python
import json, ssl, time, urllib.request, urllib.parse
from pathlib import Path

# Load credentials
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

def get_slackbot_dm() -> str:
    """Find your Slackbot DM channel ID.

    ⚠ Do NOT use search.messages(from:slackbot) — it returns public channel IDs (C...)
    instead of the actual DM (D...). Use conversations.open with USLACKBOT instead.
    USLACKBOT is Slackbot's fixed user ID across all workspaces.
    """
    r = api("POST", "conversations.open", {"users": "USLACKBOT"})
    if r.get("ok"):
        return r["channel"]["id"]
    raise RuntimeError(f"Could not open Slackbot DM: {r.get('error')}")

def extract_element(item):
    """Render one rich_text element to plain text."""
    t = item.get("type", "")
    if t == "text":    return item.get("text", "")
    if t == "link":    return item.get("text") or item.get("url", "")
    if t == "channel": return f"#{item.get('channel_id', '?')}"
    if t == "user":    return f"@{item.get('user_id', '?')}"
    if t == "emoji":   return f":{item.get('name', '')}:"
    return ""

def extract_ai_answer(msg):
    """Extract readable text from a Slack AI message."""
    parts = []
    for block in msg.get("blocks", []):
        if block.get("type") == "timeline":
            continue  # skip Slack AI's internal search traces
        if block.get("type") == "rich_text":
            for el in block.get("elements", []):
                el_type = el.get("type", "")
                items = el.get("elements", [])
                if el_type == "rich_text_list":
                    for li in items:
                        parts.append("  • " + "".join(extract_element(i) for i in li.get("elements", [])))
                elif el_type == "rich_text_preformatted":
                    parts.append("```" + "".join(extract_element(i) for i in items) + "```")
                else:
                    parts.append("".join(extract_element(i) for i in items))
        elif block.get("type") == "section" and block.get("text"):
            parts.append(block["text"].get("text", ""))
    return "\n".join(p for p in parts if p.strip())

def ask_slack_ai(question: str, slackbot_dm: str, thread_ts: str = None) -> tuple[str, str]:
    """
    Post a question to Slack AI and return (thread_ts, answer).
    Pass thread_ts to continue a conversation in the same thread.
    """
    payload = {"channel": slackbot_dm, "text": question}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    r = api("POST", "chat.postMessage", payload)
    if not r.get("ok"):
        raise RuntimeError(f"Post failed: {r.get('error')}")
    msg_ts  = r["ts"]
    root_ts = thread_ts or msg_ts

    for _ in range(60):
        time.sleep(1)
        r = api("GET", "conversations.replies",
                params={"channel": slackbot_dm, "ts": root_ts, "limit": "20"})
        ai_replies = [m for m in r.get("messages", [])
                      if float(m.get("ts", "0")) > float(msg_ts)
                      and m.get("subtype") == "ai"]
        if ai_replies:
            answer = extract_ai_answer(ai_replies[-1])
            if answer and "Thinking" not in answer:
                return root_ts, answer
    return root_ts, "(no response after 60s)"

# Usage
slackbot_dm = get_slackbot_dm()  # or hardcode your DM channel ID
thread_ts, answer = ask_slack_ai("how do we handle on-call escalations?", slackbot_dm)
print(answer)

# Multi-turn conversation — pass thread_ts to maintain context
thread_ts, a1 = ask_slack_ai("What is our incident response process?", slackbot_dm)
_, a2 = ask_slack_ai("Who are the main contacts?", slackbot_dm, thread_ts=thread_ts)
```

---

## search.messages — raw full-text search

**Best for:** finding specific messages, people, decisions, or incidents. Supports full Slack search syntax.

```python
def search_slack(query: str, count: int = 10) -> list[dict]:
    """Search Slack messages. Returns list of {channel, user, text, permalink}."""
    r = api("GET", "search.messages",
            params={"query": query, "count": str(count), "sort": "score"})
    if not r.get("ok"):
        raise RuntimeError(f"search failed: {r.get('error')}")
    return [
        {"channel": m.get("channel", {}).get("name", "?"),
         "user": m.get("username", "?"),
         "text": m.get("text", ""),
         "ts": m.get("ts", ""),
         "permalink": m.get("permalink", "")}
        for m in r.get("messages", {}).get("matches", [])
    ]

# Slack search syntax examples:
# search_slack("deployment failed")                 — keyword search
# search_slack("in:#engineering deployment")        — specific channel
# search_slack("from:alice incident")               — by author
# search_slack("outage after:2026-01-01")           — date filter
# search_slack("api timeout", count=20)             — more results
```

---

## Read a thread from a Slack URL

```python
def fetch_thread(slack_url: str) -> list[dict]:
    """
    Fetch all messages in a Slack thread from its URL.
    Supports: slack.com/archives/CXXXXXXX/pNNNNNNNNNNNNNNN[?thread_ts=...]
    """
    import re
    m = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", slack_url)
    channel = m.group(1)
    raw_ts = m.group(2)
    ts = raw_ts[:10] + "." + raw_ts[10:]   # p1773406713930289 → 1773406713.930289

    tts_m = re.search(r"thread_ts=([\d.]+)", slack_url)
    thread_ts = tts_m.group(1) if tts_m else ts

    r = api("GET", "conversations.replies",
            params={"channel": channel, "ts": thread_ts, "limit": "50"})
    return r.get("messages", [])

# Usage:
msgs = fetch_thread("https://yourcompany.slack.com/archives/C08E6GQMLP6/p1773406713930289")
for msg in msgs:
    print(f"{msg.get('user','?')}: {msg.get('text','')[:120]}")
```

---

## API surface

| Endpoint | What it does | Notes |
|----------|-------------|-------|
| `auth.test` | Verify token, get user/team | — |
| `chat.postMessage` | Post a message | Requires `channel` + `text` |
| `conversations.replies` | Fetch thread / poll for Slack AI response | Requires `channel` + `ts` (thread root) |
| `conversations.history` | Read recent messages in a channel | Requires `channel` ID |
| `conversations.info` | Channel name, topic, metadata | Requires `channel` ID |
| `search.messages` | Full-text search across all accessible Slack | Full Slack syntax: `in:`, `from:`, `after:`, `before:` |
| `users.info` | Look up a user by ID | — |

---

## Discover channel IDs

```bash
# Workaround for Enterprise Grid (conversations.list may be blocked):
# Search for any message in the channel to get its ID
curl -s "https://slack.com/api/search.messages?query=in%3A%23channel-name+a&count=1" \
  -H "Authorization: Bearer $SLACK_XOXC" -H "Cookie: d=$SLACK_D_COOKIE" \
  | jq -r '.messages.matches[0].channel | {id, name}'
```

**URL parsing:**
- URL pattern: `.../archives/{CHANNEL_ID}/p{TS_NO_DOT}`
- `D...` = DM, `C...` = channel, `G...` = group DM
- `p1773406713930289` → ts `1773406713.930289`
