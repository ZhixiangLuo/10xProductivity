---
tool: {tool-name}
auth: {api-token|oauth|sso|ad-sso|session-cookie|ldap}
author: {your-github-username}
verified: {YYYY-MM}
env_vars:
  - {TOOL_API_TOKEN}
---

# {Tool Name} — {auth method}

{1-2 sentences: what this tool is, who uses it, and why this auth method.}

API docs: {URL}

**Verified:** {what was tested, against which environment, date.
e.g. "Production (api.linear.app) — /viewer + /issues — 2026-03, no VPN required."}

---

## Credentials

```bash
# Add to .env:
# {TOOL_API_TOKEN}=your-token-here
# Generate at: {URL where to get the token}
```

---

## Auth

{Describe the auth flow in 1-2 sentences, then show the working command.}

```bash
source .env
BASE="https://{prod-base-url}"

curl -s "$BASE/{some-endpoint}" \
  -H "Authorization: Bearer ${TOOL_API_TOKEN}" \
  | jq .
# → {paste actual output here}
```

---

## Verified snippets

```bash
source .env
BASE="https://{prod-base-url}"

# {What this does}
curl -s "$BASE/{endpoint}" \
  -H "Authorization: Bearer ${TOOL_API_TOKEN}" \
  | jq .
# → {actual output}

# {What this does}
curl -s "$BASE/{endpoint}" \
  -H "Authorization: Bearer ${TOOL_API_TOKEN}" \
  | jq .
# → {actual output}
```

---

## Notes

- {Any permission requirements, e.g. "requires Admin role for write endpoints"}
- {Network requirements, e.g. "no VPN required" or "requires corp VPN"}
- {Any known limitations or caveats}
