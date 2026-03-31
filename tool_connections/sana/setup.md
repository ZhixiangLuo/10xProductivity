---
name: sana-setup
description: Set up Sana (sana.ai) enterprise workspace. SSO browser session — capture sana-ai-session via Playwright; user supplies a workspace URL.
---

# Sana — Setup

## Auth method: SSO browser session

Sana hosts each customer on **`https://sana.ai/{workspace-id}`** (and related `/x-api` routes). After your IdP login, the browser holds a **`sana-ai-session`** cookie (~hours; TTL varies by org). No personal API key replaces this for the web/agent API used here.

**What to ask the user:** *"Send any Sana URL from your browser after you’re logged in"* (home, profile, or an agent chat). From that, set `SANA_WORKSPACE_URL` to the workspace entry (e.g. `https://sana.ai/your-workspace-id`).

---

## Steps

1. From the URL, set in `.env`:

```bash
# --- Sana ---
SANA_WORKSPACE_URL=https://sana.ai/your-workspace-id
# Optional if the slug is not the first path segment:
# SANA_WORKSPACE_ID=your-workspace-id
```

2. Capture the session:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --sana-only
```

Or run the tool script directly:

```bash
python3 tool_connections/sana/sso.py
```

3. For **agent chat** snippets in `connection-sso.md`, set `SANA_AGENT_ID` to the agent id from the Sana UI (open the agent → id is in the URL path after `/agent/`).

---

## Verify

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
    print("status", r.status)
# → status 200
# If 401/403: session expired — run playwright_sso.py --sana-only again
```

---

## `.env` entries

```bash
# --- Sana ---
SANA_WORKSPACE_URL=https://sana.ai/your-workspace-id
SANA_WORKSPACE_ID=your-workspace-id
SANA_AGENT_ID=your-agent-id
SANA_SESSION=your-sana-ai-session-cookie
```

---

## Refresh

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --sana-only
```

**Connection details:** `tool_connections/sana/connection-sso.md`
