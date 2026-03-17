# Contributing to 10xProductivity

Thank you for contributing. The goal is a library of high-quality, verified tool connections that any agent can pick up and use immediately.

## The core rule: run before you write

Every snippet in a connection file must be code you actually executed and saw succeed. No copy-pasting from docs. No hypothetical endpoints. If you can't run it, don't write it.

This is the single most important quality gate. A connection file with one working snippet is better than five unverified ones.

---

## Two contribution paths

### Path 1: Community contribution (lower bar — start here)

Add a new tool or auth variant to `community/`. This is the right path if you have a working connection but it hasn't been tested on multiple environments, or if a variant already exists in core but you use a different auth method (e.g. AD SSO instead of API token).

1. **Copy the template:** `cp community/TEMPLATE.md community/{tool-name}/{auth-method}-{your-github-username}.md`
2. **Fill in the frontmatter:** `tool`, `auth`, `author`, `verified`, `env_vars`
3. **Run before you write:** every snippet must be code you actually executed and saw succeed
4. **Open a PR** — no index update needed for community files

Filename convention: `{auth-method}-{contributor}.md` (e.g. `api-token-alice.md`, `ad-sso-carol.md`)

### Path 2: Core contribution (higher bar)

Add or improve a connection in `tool_connections/`. Core files are maintained, kept up to date, and loaded by default. The bar is higher: multi-environment validation, complete auth flow, search interface documented.

1. **Read the playbook:** Load `add-new-connection/SKILL.md` — it walks through the full process from research to validation to wiring.

2. **Research the tool:** Find the official API docs, identify the auth mechanism, find the base URL.

3. **Validate against production:** Test connectivity, auth, and at least 2 read endpoints. Record actual output.

4. **Write the connection file:** Use the format in `add-new-connection/SKILL.md`. Every snippet must have a `# → {actual output}` comment.

5. **Wire into the index:** Update `tool_connections/SKILL.md` in all 3 places (frontmatter, table, inline section).

6. **Open a PR** — see PR process below.

> Community files can be promoted to core. If your `community/` contribution is solid, open a PR to move it to `tool_connections/` and wire it into the index.

---

## What makes a good connection file

**Good:**
- Every snippet was actually executed and shows real output
- Auth flow is documented from "zero" (fresh credentials) to "working request"
- Search/query interface is documented if the tool has one
- Permission limitations are noted (not just successes)
- Network requirements (VPN, specific proxy, etc.) are explicitly stated

**Not good:**
- Snippets copied from official docs without verification
- Endpoints with placeholder output like `# → {"result": "..."}` (show real output)
- Stale content that hasn't been re-validated after major API changes
- Session-specific IDs or one-time URLs that won't work for the next user

---

## SSO-based tools

If the tool uses SSO rather than long-lived API keys:

1. Add a session capture function to `playwright_sso.py` following the Grafana or Slack patterns.
2. Add a `--{tool}-only` CLI flag.
3. Add a session validity check (use `_http_get_no_redirect` for redirect-based expiry).
4. Document the refresh command in the tool's `.md` file.

---

## PR process

### Branch naming

```
connection/{tool-name}           # new connection (community or core)
connection/{tool-name}-promote   # promoting community → core
fix/{tool-name}                  # fixing a broken snippet or stale endpoint
```

### Opening the PR

```bash
git checkout -b connection/{tool-name}
git add community/{tool-name}/ tool_connections/ CONTRIBUTING.md   # whatever changed
git commit -m "Add {Tool Name} connection ({auth-method})"
gh pr create \
  --title "Add {Tool Name} connection ({auth-method})" \
  --body "$(cat <<'EOF'
## What this adds

{1-2 sentences: what tool, what auth method, what it enables.}

## Verified against

{environment, date, e.g. "Production (teams.live.com) — 2026-03, personal Microsoft account, no VPN"}

## Checklist
EOF
)"
```

Then append the appropriate checklist from below to the PR body.

### PR title format

| Contribution type | Title format |
|-------------------|--------------|
| New community file | `Add {Tool} connection ({auth-method})` |
| Promote to core | `Promote {Tool} connection to core` |
| Fix existing | `Fix {Tool} connection: {what broke}` |
| New SSO tool | `Add {Tool} SSO connection + playwright_sso.py support` |

---

## PR checklist

**Community contribution (`community/`):**
- [ ] File placed at `community/{tool-name}/{auth-method}-{username}.md`
- [ ] Frontmatter filled in (`tool`, `auth`, `author`, `verified`, `env_vars`)
- [ ] Every snippet was actually run and includes real output in comments
- [ ] Auth flow documented from scratch

**Core contribution (`tool_connections/`):**
- [ ] New connection file at `tool_connections/{tool-name}.md`
- [ ] Frontmatter uses core format (`name:`, `description:`)
- [ ] Every snippet was actually run and includes real output in comments
- [ ] Auth flow documented from scratch
- [ ] Search/query interface checked — documented if found, explicitly noted if absent
- [ ] Network requirement stated (VPN or confirmed not needed)
- [ ] Index updated (`tool_connections/SKILL.md`) in all 3 places (frontmatter description, table row, inline section)
- [ ] `.env` updated with new credential vars and refresh notes

**Promotion (community → core):**
- [ ] All core checklist items above
- [ ] Community file removed (or kept if the auth variant differs from core)
- [ ] `SETUP.md` updated if the tool was listed as "coming soon"

**SSO tool (additional):**
- [ ] `playwright_sso.py` updated: session function, `--{tool}-only` flag, `check_tokens()`, `load_tokens_from_env()`, `update_env_file()`
- [ ] `SETUP.md` "Minimum user input" table updated
