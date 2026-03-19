---
tool: {tool-name}
auth: {api-token | sso | oauth | session-cookie | ad-sso | ldap}
author: {your-github-username}
verified: {YYYY-MM}
env_vars:
  - {TOOL_API_TOKEN}
  - {TOOL_BASE_URL}
---

# {Tool Name} — {auth method}

{1-2 sentences: what this tool is, who uses it, and why this auth method.}

API docs: {URL}

**Verified:** {what was tested, against which environment, date.
e.g. "Production (api.example.com) — /me + /issues — 2026-03, no VPN required."}

---

## Credentials

Setup: `staging/{tool-name}/setup.md`

```bash
# .env entries:
{TOOL}_API_TOKEN=your-token-here
{TOOL}_BASE_URL=https://api.tool.com
```

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

## Verified snippets

```python
# {What this does}
# → {actual output}

# {What this does}
# → {actual output}
```

---

## Notes

- {Any permission requirements, e.g. "requires Admin role for write endpoints"}
- {Network requirements, e.g. "no VPN required" or "requires corp VPN"}
- {Any known limitations or caveats}
