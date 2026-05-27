---
name: slack-setup
description: Set up Slack connection. Auth is SSO browser session — no API token page exists. Only input needed from the user is any Slack message URL from their workspace.
---

# Slack — Setup

## Auth method: SSO browser session

Slack uses a short-lived client token (`xoxc`) + cookie (`d`) captured from your browser session after SSO. No API token page exists. No admin approval needed.

**What to ask the user:** "Send me any Slack message link from your workspace (right-click any message → Copy link)."

That is the only input needed. Everything else is automated.

> **Note:** Slack AI (natural-language Q&A) requires Business+ or Enterprise+ plan. On Free/Pro plans, `search.messages` still works for keyword search.

---

## Steps

1. Extract the workspace URL from the message link the user provides:
   - e.g. `https://acme.slack.com/archives/C.../p...` → `https://acme.slack.com/`
2. Update `SLACK_WORKSPACE_URL` in `.env`
3. Run the SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --slack-only
```

The script opens a Chromium window. On managed machines with enterprise SSO it completes automatically (~20s). On personal machines, the user logs in once through the browser. Tokens are written to `.env` automatically.

For multiple Slack workspaces, use account-scoped keys. The account name is
normalized to an uppercase `.env` prefix:

```bash
# .env
SLACK_ACME_WORKSPACE_URL=https://acme.slack.com/

source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --slack-only --account acme
```

That writes `SLACK_ACME_XOXC` and `SLACK_ACME_D_COOKIE` without replacing the
default `SLACK_XOXC` / `SLACK_D_COOKIE` pair.

---

## Verify

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://slack.com/api/auth.test",
    headers={"Authorization": f"Bearer {env['SLACK_XOXC']}", "Cookie": f"d={env['SLACK_D_COOKIE']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get("user"), r.get("team"))
# → alice  your-workspace
# If ok=False: session expired — run playwright_sso.py --slack-only to refresh
```

---

## `.env` entries

```bash
# --- Slack ---
# Short-lived (~8h) — refresh with: python3 tool_connections/shared_utils/playwright_sso.py --slack-only
SLACK_WORKSPACE_URL=https://yourcompany.slack.com/
SLACK_XOXC=your-slack-client-token
SLACK_D_COOKIE=your-slack-d-cookie-value

# Optional second workspace:
SLACK_ACME_WORKSPACE_URL=https://acme.slack.com/
SLACK_ACME_XOXC=your-acme-client-token
SLACK_ACME_D_COOKIE=your-acme-d-cookie-value
```

---

## Refresh

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --slack-only

# Refresh a named workspace/account:
python3 tool_connections/shared_utils/playwright_sso.py --slack-only --account acme
```

Token TTL: ~8h. Re-run when `auth.test` returns `ok=False`.

## Verified multi-workspace setup

The default and account-scoped flows were both tested with real Slack sessions
and scrubbed output:

```text
$ python3 tool_connections/shared_utils/playwright_sso.py --slack-only
# → slack: ok
# → auth.test: ok=True, team=Development, user=alice
# → conversations.open: ok=True, channel=D0123456789
# → chat.postMessage: ok=True

$ python3 tool_connections/shared_utils/playwright_sso.py --slack-only --account chatbotgig
# → slack:chatbotgig: ok
# → auth.test: ok=True, team=slack_chatbot_gig, user=alice
# → conversations.open: ok=True, channel=D9876543210
# → chat.postMessage: ok=True
```

Failure case: private workspaces that use Google sign-in may show `This browser
or app may not be secure` in Playwright-controlled Chromium. If the scoped
`SLACK_<ACCOUNT>_XOXC` and `SLACK_<ACCOUNT>_D_COOKIE` values are still valid,
the refresher validates them and skips browser login. If they are expired, log
in through the opened browser manually or refresh from an already trusted
browser session.
