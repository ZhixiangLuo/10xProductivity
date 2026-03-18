# Contributing to 10xProductivity

Thank you for contributing. The goal is a library of high-quality, verified tool connections that any agent can pick up and use immediately.

## What to contribute

Contributions are welcome for:
- **New tool** — a tool not yet in the repo
- **New auth variant** — a different auth method for an existing tool (e.g. AD SSO vs API token)
- **New deployment variant** — e.g. Jira Server vs Jira Cloud
- **Improvement to an existing connection** — fixing broken snippets, adding missing endpoints, updating stale auth

Not sure if your idea fits? Open an issue first.

---

## The core rule: run before you write

Every snippet in a connection file must be code you actually executed and saw succeed. No copy-pasting from docs. No hypothetical endpoints. If you can't run it, don't write it.

This is the single most important quality gate. A connection file with one working snippet is better than five unverified ones.

---

## Two contribution paths

### Path 1: Community contribution (lower bar — start here)

Add a new tool or auth variant to `community/`. Right path if you have a working connection but it hasn't been tested across environments, or if you use a different auth method than core (e.g. AD SSO instead of API token).

**Agent:** load `contribute-connection/SKILL.md` — it runs the full flow.

Filename convention: `community/{tool-name}/{auth-method}-{github-username}.md` (e.g. `api-token-alice.md`, `ad-sso-carol.md`). No index update needed.

### Path 2: Core contribution (higher bar)

Add or improve a connection in `tool_connections/`. Core files are maintained and loaded by default. Bar is higher: multi-environment validation, complete auth flow, search interface documented, index wired.

**Agent:** load `contribute-connection/SKILL.md` — it orchestrates research → validate → write → PR.

> Community files can be promoted to core. If your `community/` contribution is solid, open a promotion PR to move it to `tool_connections/`.

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
- [ ] New connection file at `tool_connections/{tool-name}-{auth}.md` (e.g. `linear-api-token.md`). Add `{variant}` before `{auth}` if the tool has distinct deployment variants (e.g. `jira-server-api-token.md`).
- [ ] Frontmatter uses core format (`name:`, `auth:`, `description:`, `env_vars:`)
- [ ] Every snippet was actually run and includes real output in comments
- [ ] Auth flow documented from scratch
- [ ] Search/query interface checked — documented if found, explicitly noted if absent
- [ ] Network requirement stated (VPN or confirmed not needed)
- [ ] `verified_connections.example.md` updated in all 3 places (table row, inline section, connection file frontmatter)
- [ ] `env.sample` updated with placeholder entries for any new vars (`.env` is gitignored — do NOT commit it)

**Promotion (community → core):**
- [ ] All core checklist items above
- [ ] Community file kept (it stays as a verified record; do not delete)
- [ ] `SETUP.md` updated if the tool was listed as "coming soon"

**SSO tool (additional):**
- [ ] `playwright_sso.py` updated: session function, `--{tool}-only` flag, `check_tokens()`, `load_tokens_from_env()`, `update_env_file()`
- [ ] `SETUP.md` "Minimum user input" table updated

