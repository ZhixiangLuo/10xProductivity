---
name: add-new-tool
description: Add a new tool from scratch — research auth, validate against a live instance, write files to personal/{tool-name}/. Use when a tool has no recipe yet. Do NOT use this if the tool already exists in tool_connections/ — use setup.md instead.
---

# Add a New Tool

> **What this file is for:** The tool has no recipe yet. You are building one from scratch — researching auth, validating against a live instance, and writing the files to `personal/{tool-name}/` for your own use.
>
> **Wrong file?** If the tool already exists in `tool_connections/`, use `setup.md` instead — that one connects your own instance using an existing recipe.
>
> **Want to contribute back?** After completing Phase 1, read `contributing.md`.

## Purpose

Turn "I want my agent to access Tool X" into a working, verified connection file that any agent can pick up and use.

**Phase 1 (always):** Research, validate, and write the connection for your own use.
**Phase 2 (optional):** Contribute it back to the repo as a PR — only if the tool is commercial and publicly available.

---

## Non-negotiable rules

1. **Research viability first.** Before asking the user for anything, determine what auth methods exist for this tool. If no viable method exists (no public API, no session-based workaround, no OAuth path), stop — there is nothing to build.
2. **Ask only what the auth method actually needs.** The credential ask must be proportional to the auth method: SSO/browser-session → ask for nothing (just a URL to confirm the instance); API token → ask for the token and where to generate it; username+password → ask for both. Never ask vague questions the user can't answer.
3. **A URL is your best minimal input.** If you need to confirm an instance, ask for any URL from that tool (profile page, dashboard, ticket). It reveals the base URL, regional variant, and proves the user has access — without requiring them to know anything about auth.
4. **Run before you write.** Every snippet must be code you actually executed and saw succeed against a live instance. No copy-paste from docs. No illustrative output. The reason you haven't run them does not matter — unverified snippets do not belong in a connection file.
5. **Write for the next agent.** Strip session-specific IDs, one-time URLs, org-specific data. Document the pattern, not the artifact.
6. **Nothing broken.** If an endpoint didn't work, cut it. One working snippet beats five broken ones.

---

## Phase 1: Create and Verify

### Step 0: Research viability — stop here if no path exists

Before asking the user for anything:

1. Research what auth methods exist for this tool (official API docs, OAuth, browser session, etc.)
2. Pick the best viable method using the priority order below
3. Determine exactly what that method needs from the user

**This repo's goal is zero-friction setup.** The user should never have to create an app, register OAuth credentials, or configure anything outside of this repo's own flow. Reject any auth approach that requires that — even if it's technically cleaner.

**Auth method priority order:**

| Priority | Auth method | User friction | Ask the user for |
|----------|-------------|---------------|-----------------|
| 1 | **API token** | Near-zero — generate in tool settings (~30s) | The token + where to generate it |
| 2 | **Browser session (SSO, one-time capture)** | Near-zero — run `sso.py` once, cached days/weeks | A URL from the tool — nothing else |
| 3 | **Browser session (per operation)** | Low but costly — Playwright runs on every call | A URL from the tool — nothing else |
| 4 | **Username + password** | Low — but only for legacy tools | Username and password |
| ✗ | **OAuth requiring user to create their own app** | High — stop, do not use | N/A |

**On browser automation cost:** distinguish setup cost from per-operation cost.
- *SSO capture (Priority 2)* — Playwright runs once. Session is saved to disk and reused. This is acceptable and often the only option for SSO tools (Slack, Teams, Google Workspace).
- *Per-operation browser (Priority 3)* — Playwright launches on every `search()`, `read()`, or `list()` call. Only accept this if there is genuinely no API or export endpoint. Document it explicitly in the connection file.

**On OAuth:** OAuth is acceptable *only* when the repo ships pre-configured client credentials (the user just clicks "Authorize" in their browser — zero app creation). OAuth that requires the user to create a Google Cloud project, register a redirect URI, or configure a consent screen is **not acceptable** — the friction cost makes it worse than a browser session.

**Stop and explain** if the only viable path requires the user to create an app or register OAuth credentials. Don't propose it as an option — it violates this repo's zero-friction goal.

If a viable zero-friction method exists → ask the user only for what that method requires, then proceed to Step 1.

---

### Step 1: Identify the base URL

If the user provided a URL (login page, dashboard, ticket), probe it first:

```bash
curl -sI --max-time 10 "https://{the-url}" | head -5
```

Sites redirect. Confirm the real base URL before researching. Note any site-variant clues (e.g. `us5.datadoghq.com` → API base is `api.us5.datadoghq.com`).

---

### Step 2: Research the API

Do not guess. Find the official API docs.

**Search order:**
1. Official docs (`docs.tool.com/api` or `developer.tool.com`)
2. OpenAPI/Swagger spec (`/api/swagger.json`, `/openapi.json`)
3. GitHub code search — working callers are more accurate than docs

**Collect before moving on:**
- Base URL (production)
- Auth mechanism (API key, Bearer token, session cookie, OAuth2) and header name
- Token lifetime and refresh method
- Key endpoints: health/version (no auth), list, get
- Search/query interface if any
- Network requirements (VPN?)
- Env var names to use

---

### Step 3: Store credentials

Add to `.env` (repo root) only — do not edit root `env.sample` (it is a stub) or other shared index files. Document new variables in `personal/{tool}/setup.md` under **`.env` entries**.

> **Watch for tools with explicit resource-sharing requirements.** Some tools (e.g. Notion) require you to explicitly grant the integration access to specific resources (pages, databases) even after auth succeeds. Workspace-level installation ≠ data access. If auth passes but read endpoints return 404 or empty results, look for a resource-level sharing step — usually found in the tool's Settings → Integrations/Apps → edit the integration → content/resource access panel. Document this in the Notes section of the connection file.

```bash
# --- Tool Name ---
TOOL_API_TOKEN=your-api-token-here
TOOL_BASE_URL=https://api.tool.com
# Generate at: https://tool.com/settings/api-tokens
# Token lifetime: long-lived / ~8h (refresh with: ...)
```

---

### Step 4: Validate against the live instance

**Do not use dev environments.** Validate on the actual production endpoint.

#### 4a. Connectivity (no auth)

```bash
curl -sI --max-time 10 "$TOOL_BASE_URL/health"    # or /version, /ping, /api/v1/status
```

- 200 → proceed
- SSL error → VPN may be required; document it
- Timeout → wrong URL

#### 4b. Auth

```bash
source .env
# Try the auth pattern from docs
curl -s "$TOOL_BASE_URL/some-read-endpoint" \
  -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .

# If header name is unclear, probe common patterns:
for h in "Authorization: Bearer $TOOL_API_TOKEN" "X-API-Key: $TOOL_API_TOKEN" "api-key: $TOOL_API_TOKEN"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$TOOL_BASE_URL/some-endpoint" -H "$h")
  echo "$h → HTTP $code"
done
```

#### 4c. Key read endpoints

Run at least 2 read endpoints and capture real output:

```bash
curl -s "$TOOL_BASE_URL/users/me" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → {"id": "u_123", "name": "Alice", "email": "alice@example.com"}

curl -s "$TOOL_BASE_URL/items?limit=5" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → [{"id": "p_1", "name": "My Item"}, ...]
```

Record both successes and permission errors — both are useful.

#### 4d. Native search and AI/chat

**Always check — this is what makes a connection genuinely useful to an agent.**

For every tool, answer these two questions before writing the connection file:

1. **Does it have a search API?** (full-text, title-based, filter-based — any kind)
   - Try common patterns: `/search`, `/api/search`, `?q=`, `?query=`
   - Run it. Record what fields it searches, what it returns, and any limitations (e.g. title-only, indexed with delay).

2. **Does it have an AI or chat API?** (LLM-backed Q&A, summarization, assistant endpoint)
   - Check official docs for "AI", "assistant", "chat", "copilot" endpoints.
   - If none exist in the public API, say so explicitly — do not leave it ambiguous.

**Document the result in the Notes section of the connection file:**
- If search works: show a verified snippet with real output.
- If AI/chat exists: show the endpoint and a verified call.
- If neither exists or is paywalled: state it clearly (e.g. "No search API." or "AI chat is enterprise-only, no public endpoint.").

Skipping this step leaves the agent blind to the tool's most useful capabilities.

---

### Step 5: Write the connection file

**Location:** `personal/{tool-name}/` — always. This is gitignored and never committed.
Do not write to `tool_connections/`, `staging/`, or anywhere else outside `personal/`.

**Format** (use `staging/_example/` as reference):

```markdown
---
tool: {tool-name}
auth: {api-token|oauth|sso|ad-sso|session-cookie}
author: {github-username}
verified: {YYYY-MM}
env_vars:
  - TOOL_API_TOKEN
  - TOOL_BASE_URL
---

# {Tool Name} — {auth method}

{1-2 sentences: what it is, who uses it.}

API docs: {URL}

**Verified:** Production ({base-url}) — {endpoints tested} — {YYYY-MM}. {VPN required / not required.}

---

## Credentials

\`\`\`bash
# Add to .env:
# TOOL_API_TOKEN=your-token-here
# TOOL_BASE_URL=https://api.tool.com
# Generate at: {URL}
\`\`\`

---

## Auth

{Auth flow in 1-2 sentences.}

\`\`\`bash
source .env
curl -s "$TOOL_BASE_URL/endpoint" \
  -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → {actual output}
\`\`\`

---

## Verified snippets

\`\`\`bash
source .env
BASE="$TOOL_BASE_URL"

# {What this does}
curl -s "$BASE/endpoint" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → {actual output}
\`\`\`

---

## Notes

- {Permission requirements}
- {VPN requirement}
- {Known limitations}
```

**Snippet rules:**
- Only include commands you actually ran and saw succeed
- Every snippet has a `# → {actual output}` comment (truncate long output with `# → [{...}, ...]`)
- Permission errors are valid: `# → 403 Forbidden — requires Admin role`
- Cut anything that didn't work

---

### Step 6: Update verified_connections.md

Once the connection file is written and at least 2 snippets are verified with real output, add the tool to your active capability index.

Open `setup.md` Step 3, add the tool name to `VERIFIED_NAMES`, and run the script:

```python
VERIFIED_NAMES = [
    # ... existing tools ...
    "{tool-name}",   # ← add this
]
```

```bash
# Run the script from setup.md Step 3 to regenerate verified_connections.md
source .venv/bin/activate
python3 - << 'EOF'
# ... paste the script from setup.md Step 3 here with your tool added ...
EOF
```

Then reload `verified_connections.md` — the new tool is now live in your session.

---

## Phase 2: Contribute back (optional)

If the tool is commercial/publicly available and you want to share the connection with the community, read `contributing.md` — it covers the full process: eligibility check, scrubbing personal data, and opening the PR.

---

## Checklist — do not mark done until all boxes checked

- [ ] Auth method researched and confirmed viable before asking user anything
- [ ] Asked user only for what the auth method actually requires
- [ ] Base URL confirmed (not guessed)
- [ ] Auth mechanism identified and tested on production
- [ ] At least 2 read endpoints run, real output recorded
- [ ] Native search API tested — verified snippet recorded, or explicitly noted as absent
- [ ] AI/chat API checked — verified snippet recorded, or explicitly noted as unavailable/paywalled
- [ ] `verified: YYYY-MM` filled in (blank = not ready)
- [ ] `.env` updated with new credentials
- [ ] All files written to `personal/{tool-name}/` only — nothing outside `personal/`
- [ ] File written with only verified snippets
- [ ] `verified_connections.md` regenerated with new tool added to `VERIFIED_NAMES`

**To contribute back:** see `contributing.md`
