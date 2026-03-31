---
tool: {tool-name}
auth: {api-token | sso | oauth | session-cookie | ad-sso | ldap}
author: {your-github-username}
env_vars:
  - {TOOL_API_TOKEN}
  - {TOOL_BASE_URL}
  # For file-based auth (SSO session capture), use:
  # auth_file: ~/.browser_automation/{tool}_auth.json
  # Token TTL: {~8h | long-lived | ~1h — refresh with: <command>}
---

# {Tool Name} — {auth method}

{1-2 sentences: what this tool is, who uses it, and why this auth method.}

API docs: {URL}

**Verified:** {what was tested, against which environment, date.
e.g. "Production (api.example.com) — /me + /issues — 2026-03, no VPN required."}

---

## Verify connection

```python
# Quick auth check — run this first to confirm credentials work
from pathlib import Path
import urllib.request, json

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
BASE = env["{TOOL}_BASE_URL"]
TOKEN = env["{TOOL}_API_TOKEN"]

req = urllib.request.Request(f"{BASE}/me",  # or /health, /version, /whoami
      headers={"Authorization": f"Bearer {TOKEN}"})
print(json.loads(urllib.request.urlopen(req).read()))
# → {"id": "u_123", "name": "Alice"}
```

---

## Credentials

Setup: `staging/{tool-name}/setup.md`

```bash
# .env entries (single token):
{TOOL}_API_TOKEN=your-token-here
{TOOL}_BASE_URL=https://api.tool.com

# For tools requiring multiple tokens (e.g. API key + app key):
# {TOOL}_API_KEY=your-api-key
# {TOOL}_APP_KEY=your-app-key
```

**Token lifetime:** {long-lived | ~8h — refresh with: `source .venv/bin/activate && python3 tool_connections/shared_utils/playwright_sso.py --{tool}-only`}

{For SSO tools only: ⚠ Credentials are written to `.env` by `playwright_sso.py` — they do not exist until the SSO script has run at least once. The verify snippet will fail with a missing key error on a fresh clone. Run the SSO script first.}

---

## Auth

{Describe the auth flow in 1-2 sentences, then show the working command.}

```python
from pathlib import Path
import urllib.request, json

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

BASE = env["{TOOL}_BASE_URL"]
TOKEN = env["{TOOL}_API_TOKEN"]

req = urllib.request.Request(f"{BASE}/some-endpoint",
      headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    print(json.load(r))
# → {paste actual output here}
```

---

## Choosing the right method

{Optional — include only if the tool has multiple meaningfully different access patterns, e.g. search vs AI, REST vs GraphQL, read vs write.}

**Use {method A} for:**
- {when it's the right choice}
- {specific use case}

**Use {method B} for:**
- {when it's the right choice}
- {specific use case}

**⚠ {Critical gotcha if any — e.g. "Method B cannot filter by date. Use method A for time-specific queries."}**

---

## Verified snippets

**Style rules:**
- Write inline code, not reusable helper functions. The agent reading this is not building a library.
- Every snippet ends with `# → {actual output}` (truncate long output with `# → [{...}, ...]`).
- Use `⚠` for critical gotchas inline, right where the mistake would happen.
- 403 / 404 / permission errors are valid output — record them.
- Cut anything that didn't work.

```python
# {What this does — one line description}
r = api("GET", f"{BASE}/endpoint", params={"key": "value"})
print(r)
# → {actual output}
```

```python
# {What this does}
r = api("GET", f"{BASE}/other-endpoint")
# → 403 Forbidden — requires Admin role
```

---

## Notes

- {Any permission requirements, e.g. "requires Admin role for write endpoints"}
- {Network requirements, e.g. "no VPN required" or "requires corp VPN"}
- {Any known limitations or caveats}
