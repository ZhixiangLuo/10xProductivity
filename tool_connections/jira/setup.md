---
name: jira-setup
description: Set up Jira connection. Supports Cloud (API token + Basic auth) and Server/Data Center (SSO session). Ask for any Jira ticket URL to infer base URL and variant.
---

# Jira — Setup

## Step 1: Ask for a URL to identify the variant

Ask the user: "Share any Jira ticket URL."

Infer variant from the URL:
- `yourcompany.atlassian.net` → **Jira Cloud** → API token + Basic auth (`email:token`)
- `jira.yourcompany.com` (self-hosted) → **Jira Server / Data Center** → Personal Access Token (Bearer) — same `connection-api-token.md`, but no email needed; token goes directly in Authorization header as Bearer

Both variants use `connection-api-token.md`. The difference is auth format only — see below.

Infer `JIRA_BASE_URL` from the URL (e.g. `https://acme.atlassian.net/browse/ENG-123` → `https://acme.atlassian.net`).

---

## Jira Cloud — API token (most common)

**What to ask the user:**
- "Paste your Jira API token" → Jira → Profile photo → Manage account → Security → API tokens → Create
- "Your Atlassian account email"

**Set `.env`:**
```bash
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_BASE_URL=https://yourcompany.atlassian.net   # inferred from URL they shared
```

**Verify:**
```python
from pathlib import Path
import urllib.request, json, ssl, base64
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
creds = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
req = urllib.request.Request(f"{env['JIRA_BASE_URL']}/rest/api/2/myself",
    headers={"Authorization": f"Basic {creds}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get('displayName'), r.get('emailAddress'))
# → Alice Smith  alice@yourcompany.com
# If 401: wrong email or token. If 403: token lacks permissions.
```

**Connection details:** `tool_connections/jira/connection-api-token.md`

---

## Jira Server / Data Center — Personal Access Token

**What to ask the user:**
- "Paste your Jira Personal Access Token" → Jira → Profile photo → Personal Access Tokens → Create token
- No email needed — Bearer token auth only

**Set `.env`:**
```bash
JIRA_API_TOKEN=your-jira-pat
JIRA_BASE_URL=https://jira.yourcompany.com
# No JIRA_EMAIL needed for Server/DC
```

**Verify:**
```python
from pathlib import Path
import urllib.request, json, ssl
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(f"{env['JIRA_BASE_URL']}/rest/api/2/myself",
    headers={"Authorization": f"Bearer {env['JIRA_API_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get('displayName'), r.get('emailAddress'))
# → Alice Smith  alice@yourcompany.com
# If 401: token wrong or expired. If 403: token lacks permissions.
```

**Connection details:** `tool_connections/jira/connection-api-token.md`

---

## `.env` entries

```bash
# --- Jira Cloud ---
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_BASE_URL=https://yourcompany.atlassian.net
# Auth is Basic base64(email:token) — not Bearer. Always load via Python, not bash source.
# Generate token at: Jira → Profile photo → Manage account → Security → API tokens → Create

# --- Jira Server / Data Center ---
# JIRA_API_TOKEN=your-jira-pat   # Bearer token, no email needed
# JIRA_BASE_URL=https://jira.yourcompany.com
# Generate token at: Jira → Profile photo → Personal Access Tokens → Create token
```
