---
name: add-new-connection
description: Research, validate, and write a new tool connection file. Use when you need API access to a tool not yet in tool_connections, or when asked to add a new tool connection. Produces a verified connection file — community/{tool}/ for new/unvalidated tools, or tool_connections/{tool}.md if fully validated across environments.
---

# Add a New Tool Connection

## Purpose

Turn "I've heard of this tool" into a working, verified connection file that any agent can pick up and use.

**Non-negotiable rules:**
1. **Run before you write.** Every snippet in the file must be code you actually executed and saw succeed. No copy-paste from docs. No hypothetical endpoints.
2. **Write for the next agent, not yourself.** The file is a general template — not a log of your test session. Strip out session-specific IDs, one-time URLs, and example data. Document the *pattern* (e.g. "search URL returns result URLs") not the artifact.
3. **Generalize the auth, not just the snippets.** Before writing, ask: does this auth flow work for the full range of users? (SSO vs password login, managed vs personal machine, free vs paid tier, different OS.) Document the assumptions and variations explicitly. A connection that only works for your exact setup is a personal note, not a connection file.
4. **Nothing broken.** If something didn't work (wrong endpoint, 404, expired session logic), cut it. A connection file with one working snippet is better than five broken ones.

**Prerequisites:** Load `verified_connections.example.md` first (master catalog + format reference).

---

## When to use

- You need API access to a tool for your own use and no connection file exists
- An existing connection file has unverified snippets or missing auth details
- Someone asks "can the agent access X?"

**If you want to contribute the result back as a PR**, load `contribute-connection/SKILL.md` instead — it wraps this skill and adds the full PR flow on top.

---

## Step 0: Probe the endpoint first

Before researching or writing anything, check what the URL actually resolves to:

```bash
curl -sI --max-time 10 "https://{the-url}" | head -10
```

Sites often redirect to a completely different domain. A 5-second curl saves you from researching the wrong platform. Identify the real final URL and any tech hints (server headers, platform names in HTML) before doing any research.

---

## Step 1: Research

Do not guess base URLs or auth patterns. Find the official API docs first.

**Search strategy (in order):**
1. Official docs — most tools have a public API reference (`docs.tool.com/api` or `developer.tool.com`)
2. OpenAPI/Swagger spec — often at `/api/swagger.json`, `/openapi.json`, or linked from docs
3. Existing callers — search GitHub for code that calls the tool's endpoint; working code is more accurate than docs

**Collect before moving on:**
- Base URL (production)
- Auth mechanism (API key, Bearer token, session cookie, OAuth2)
- Token lifetime and refresh method
- Search/query interface (if any — prefer it as the primary interface)
- Key endpoints: health/version (no auth), list, get, create
- Network requirements (VPN, specific network access, etc.)
- Required env vars not already in `.env`

---

## Step 2: Store credentials in `.env`

Before testing, add any new credentials to `.env` (repo root). Follow the existing format:

```bash
# --- Tool Name ---
TOOL_API_TOKEN=your-api-token-here
# Generate at: https://tool.com/settings/api-tokens
```

For short-lived tokens (session cookies, JWTs), note the refresh method in a comment.

If the tool uses SSO:
- Check if it can be automated via `playwright_sso.py` (add a new `--tool-only` flag)
- Or document the manual refresh steps clearly

---

## Step 3: Validate — on the real environment

**Dev is not sufficient.** Dev environments are often misconfigured or have different auth. Validate against the actual production/staging endpoint you'll use.

### 3a. Connectivity (no auth)

```bash
# Try health/version endpoints — note which ones respond
curl -sv --max-time 10 "https://{prod-base-url}/health"
curl -sv --max-time 10 "https://{prod-base-url}/version"
curl -sv --max-time 10 "https://{prod-base-url}/api/v1/status"
curl -sv --max-time 10 "https://{prod-base-url}/ping"
```

- **200 OK** → reachable, proceed
- **SSL error** → check if VPN/proxy required; document it
- **Timeout** → wrong URL; keep searching

### 3b. Auth

```bash
BASE="https://{prod-base-url}"

# API key / Bearer token
curl -s "$BASE/some-read-endpoint" \
  -H "Authorization: Bearer $TOOL_API_TOKEN" \
  | jq .

# If token header name is unclear, try common ones:
for header in "Authorization: Bearer $TOOL_API_TOKEN" "X-API-Key: $TOOL_API_TOKEN" "api-key: $TOOL_API_TOKEN"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    "$BASE/some-read-endpoint" -H "$header")
  echo "$header → HTTP $code"
done
```

### 3c. Key read endpoints

Test at least 2 read endpoints that return real data. Record actual output — this becomes the snippet comments in the file:

```bash
curl -s "$BASE/users/me" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → {"id": "u_123", "name": "Alice", "email": "alice@example.com"}

curl -s "$BASE/projects?limit=5" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → [{"id": "p_1", "name": "My Project"}, ...]
```

Note both successes **and** permission errors — both are useful for the next user.

---

## Step 4: Write the tool connection file

**Where to put it:**

- **New tool or auth variant, not yet validated across environments** → `community/{tool-name}/{auth-method}-{your-github-username}.md`
  Use the template at `community/TEMPLATE.md`. Frontmatter required. No index update needed.
- **Well-validated, ready for core** → `tool_connections/{tool-name}-{auth}.md`
  Follow the format below and wire into the index (Step 5).

When in doubt, start in `community/`. A solid community file can be promoted to core later.

---

**Core file location:** `tool_connections/{tool-name}-{auth}.md` (e.g. `jira-api-token.md`, `slack-sso-session.md`). If the tool also has a variant dimension: `tool_connections/{tool-name}-{variant}-{auth}.md` (e.g. `jira-server-api-token.md`).

**Format:**

```markdown
---
name: {tool-name}
auth: {api-token|sso-session|browser-session|oauth}
description: {Tool} — {one sentence what it is}. Use when {2-3 specific use cases}.
env_vars:
  - TOOL_TOKEN
  - TOOL_BASE_URL
---

# {Tool Name}

{1-2 sentences: what problem it solves, who uses it.}

Env: `TOOL_TOKEN` ({short-lived? how to refresh})
API docs: {URL}

**Verified:** {exactly what was tested, on which env, date.
 e.g. "Production (api.tool.com) — /users/me + /projects — 2026-03-16, v2.1.0. No VPN required."}

---

## Auth

{Auth flow in prose, then commands.}

\`\`\`bash
source .env
BASE="https://{prod-base-url}"

curl -s "$BASE/endpoint" \
  -H "Authorization: Bearer $TOOL_API_TOKEN" \
  | jq .
\`\`\`

---

## Quick-reference snippets (verified)

\`\`\`bash
source .env
BASE="https://{prod-base-url}"

# Health check (no auth)
curl -s "$BASE/version"
# → "2.1.0"

# Verified endpoint 1
curl -s "$BASE/users/me" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → {"id": "u_123", "name": "Alice"}

# Verified endpoint 2
curl -s "$BASE/projects?limit=5" -H "Authorization: Bearer $TOOL_API_TOKEN" | jq .
# → [{"id": "p_1", "name": "My Project"}]
\`\`\`

---

## Full API surface (most-used endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Current user |
| GET | `/projects` | List projects |
```

**Snippet rules:**
- Only include commands you actually ran and saw succeed. No copy-paste from docs.
- Add `# → {actual output}` after every command. Truncate long output with `# → [{...}, ...]`.
- Permission errors are valid output — document them: `# → 403 requires Admin role`.
- Do not include write/mutating endpoints unless you verified them intentionally.
- If an endpoint didn't work — cut it.

**Generality rule:** Write for the next agent, not for your test session.
- ❌ Don't document: specific session IDs, one-time task URLs, example data from a single run
- ✅ Do document: URL patterns, auth flows, endpoint schemas, how to discover IDs

---

## Step 5: Wire into the index

Three places in `verified_connections.example.md` (the master catalog at the repo root):

**1. Table row** — add a row in the appropriate tier table:
```markdown
| **{Tool}** | {auth-method} | `tool_connections/{tool}.md` | {when to use} |
```

**2. Inline section** — add before "Adding new connections":
```markdown
## {Tool Name} → `tool_connections/{tool}.md`

**Use when:** {2-3 specific triggers}.
Env: `TOOL_TOKEN`, `TOOL_BASE_URL`
```

**3. Connection file frontmatter** — ensure `auth`, `env_vars` (and `auth_file` if applicable) are set in `tool_connections/{tool}.md`:
```markdown
---
name: {tool-name}
auth: {api-token|sso-session|browser-session|oauth}
description: ...
env_vars:
  - TOOL_TOKEN
  - TOOL_BASE_URL
---
```

---

## Step 6: Reflect and harden

**If you iterated more than once to get auth working, the skill isn't done yet.**

Before closing, ask:
1. What broke, and why? (wrong assumption, missing edge case, bad fallback)
2. Is the fix generalizable — does it affect all users of this tool, not just your situation?
3. If yes — update `playwright_sso.py`, the tool `.md`, or `SETUP.md` before marking done.

**The test:** could the next agent follow this skill on a fresh machine, with a different org, and succeed on the first try?

---

## Checklist — do not mark done until all boxes checked

**Research & validation**
- [ ] Base URL confirmed (not guessed)
- [ ] Auth mechanism identified and tested
- [ ] Connectivity confirmed on production (HTTP 200)
- [ ] Auth confirmed on production (token accepted)
- [ ] At least 2 read endpoints tested, output recorded
- [ ] Search/query interface checked — documented if found

**The file itself**
- [ ] Every snippet was actually executed — no copy-paste from docs
- [ ] Every snippet has a `# → {actual output}` comment
- [ ] Permission gaps noted (e.g. "requires Admin role")
- [ ] Network requirement explicitly stated (VPN, etc.) or confirmed not needed
- [ ] No session-specific artifacts (IDs, tokens, example data from one run)
- [ ] New credentials added to `.env` with descriptive names and refresh notes
- [ ] Auth flow covers realistic variations (SSO *and* password login if both exist; free vs paid tier differences noted)
- [ ] Assumptions that only hold for specific org setups or plans are explicitly called out

**Wiring**
- [ ] Wired into `verified_connections.example.md` in all 3 places (table row, inline section, connection file frontmatter)

---

## Adding SSO-based tools

If the tool uses SSO (session cookies rather than long-lived API keys):

1. Add a `get_{tool}_session()` function in `playwright_sso.py`
2. Add a `--{tool}-only` CLI flag
3. Add a session validity check (use `_http_get_no_redirect` for redirect-based expiry detection)
4. Add the session token to `load_tokens_from_env()` and `update_env_file()`
5. Document the refresh command in the tool's `.md` file

Follow the Grafana or Slack patterns in `playwright_sso.py` as a template.
