---
name: {tool-name}-setup
description: Set up {Tool Name} connection. {1 sentence: auth method and what to ask the user.}
---

# {Tool Name} — Setup

## Auth method: {api-token | sso | oauth | session-cookie}

{1-2 sentences: what auth method this tool uses and why. If SSO: mention that no API token page exists.}

**What to ask the user:**
- {Minimal input needed. Examples:}
  - SSO: "Share any {Tool} URL" — that's it. Run `sso.py` to capture session automatically.
  - API token: "Paste your {Tool} API token" → {Tool} → {Settings path} → Create token
  - URL needed: "Share any {Tool} URL" → infer `{TOOL}_BASE_URL` from it

---

## Steps

{For SSO tools:}
1. {Extract base URL / workspace URL from the URL the user provides}
2. Run the SSO script:

```bash
source .venv/bin/activate
python3 staging/{tool-name}/sso.py
```

{For API token tools:}
1. Set `.env`:

```bash
{TOOL}_API_TOKEN=your-token-here
{TOOL}_BASE_URL=https://api.tool.com   # inferred from URL they shared
```

---

## Verify

```python
# {Paste actual verify snippet here — must have been run and seen succeed}
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
# ...
# → {actual output}
```

**Connection details:** `staging/{tool-name}/connection-{auth-method}.md`

---

## `.env` entries

```bash
# --- {Tool Name} ---
{TOOL}_API_TOKEN=your-token-here
{TOOL}_BASE_URL=https://api.tool.com
# Generate at: {URL}
```

---

## Refresh

{For SSO tools: token TTL and refresh command.}
{For API tokens: "Long-lived — no refresh needed unless revoked."}
