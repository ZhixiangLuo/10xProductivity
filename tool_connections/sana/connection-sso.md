---
name: sana
auth: sso
description: Sana (sana.ai) — enterprise AI workspace that can search connected knowledge (e.g. email, drive, docs, calendars, depending on what your org connected). Query a Sana agent over HTTP and return the answer to the user — do not paste raw curl or session material in the final reply.
env_vars:
  - SANA_SESSION
  - SANA_WORKSPACE_URL
  - SANA_WORKSPACE_ID
  - SANA_AGENT_ID
---

# Sana — SSO session

[Sana](https://www.sana.ai/) workspaces live under **`https://sana.ai/`**. Automation uses the **`sana-ai-session`** cookie plus **`sana-ai-workspace-id`** on agent API calls. Session capture: `tool_connections/sana/sso.py` or `python3 tool_connections/shared_utils/playwright_sso.py --sana-only`.

**Verified:** Pattern exercised against production `sana.ai` x-api (tRPC + SSE agent stream) — 2026-03. SSO flow depends on your org’s IdP.

**Limits:** There is no supported public “search everything” REST shortcut beyond agent chat and documented tRPC routes; behavior depends on workspace configuration. If `user.me` returns 401, refresh the session.

---

## Credentials

Setup: `tool_connections/sana/setup.md`

```bash
SANA_WORKSPACE_URL=https://sana.ai/your-workspace-id
SANA_WORKSPACE_ID=your-workspace-id
SANA_AGENT_ID=your-agent-id
SANA_SESSION=your-sana-ai-session-cookie
```

---

## Verify session

```python
from pathlib import Path
import ssl
import urllib.request

env = {
    k.strip(): v.strip()
    for line in Path(".env").read_text().splitlines()
    if "=" in line and not line.startswith("#")
    for k, v in [line.split("=", 1)]
}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    "https://sana.ai/x-api/trpc/user.me",
    headers={"Cookie": f"sana-ai-session={env['SANA_SESSION']}"},
)
with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
    print(r.status)
# → 200 when authenticated
# → urllib.error.HTTPError 401 when session expired or cookie wrong
```

---

## Agent chat (SSE)

Use your **`SANA_AGENT_ID`** (from the agent URL: `/agent/{id}`). Responses arrive as SSE `data:` lines with JSON objects; concatenate `text-delta` deltas.

```bash
export $(grep -v '^#' .env | grep -v '^$' | xargs) 2>/dev/null
source .venv/bin/activate && python3 - << 'PYEOF'
import json, os, random, re, string, subprocess, urllib.parse

session = os.environ["SANA_SESSION"]
ws = os.environ["SANA_WORKSPACE_ID"]
agent = os.environ["SANA_AGENT_ID"]
headers = [
    "-H", f"Cookie: sana-ai-session={session}",
    "-H", f"sana-ai-workspace-id: {ws}",
]

def curl_json(url, extra_args):
    r = subprocess.run(
        ["curl", "-s", url] + extra_args,
        capture_output=True, text=True, timeout=30,
    )
    return json.loads(r.stdout)

inp = urllib.parse.quote(json.dumps({"chatId": agent}))
msgs = curl_json(
    f"https://sana.ai/x-api/trpc/agentV2.getExistingMessages?input={inp}",
    headers,
)["result"]["data"]["messages"]
parent = msgs[-1]["id"] if msgs else None

q = "YOUR QUESTION HERE"
mid = "msg-" + "".join(random.choices(string.ascii_letters + string.digits, k=12))
body = json.dumps({
    "version": 0,
    "parentMessageId": parent,
    "assetIds": [],
    "teamspaceIds": [],
    "sourceTypeGroups": [],
    "isWebSearchEnabled": False,
    "userMessage": {
        "parts": [{"type": "text", "text": q}],
        "id": mid,
        "role": "user",
    },
})
r = subprocess.run(
    [
        "curl", "-s",
        f"https://sana.ai/x-api/agent-v2/chat/{agent}/messages",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", "Accept: text/event-stream",
    ]
    + headers
    + ["--max-time", "90", "-d", body],
    capture_output=True,
    text=True,
    timeout=95,
)
parts = []
for line in r.stdout.split("\n"):
    line = line.strip()
    if line.startswith("data: "):
        try:
            d = json.loads(line[6:])
            if d.get("type") == "text-delta":
                parts.append(d.get("delta", ""))
        except json.JSONDecodeError:
            pass
print(re.sub(r"<sana-citation[^/]*/>", "", "".join(parts)).strip())
# → (natural-language answer from the agent)
PYEOF
```

**Failure cases**

- **401 / empty `result` on `user.me`:** refresh `SANA_SESSION` (SSO script).
- **Agent returns empty text:** wrong `SANA_AGENT_ID`, or agent blocked for your user; confirm in the Sana UI.
- **No enterprise search API:** use agent chat above; there is no separate documented global search endpoint in this recipe.

---

## Optional: restrict knowledge sources

If your workspace exposes source groups, you can pass them in the POST body, e.g. `"sourceTypeGroups": ["google-drive", "sana-learn"]`. Available values depend on org configuration — inspect network requests in the browser if needed.
