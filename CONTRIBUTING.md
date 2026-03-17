# Contributing to 10xProductivity

Thank you for contributing. The goal is a library of high-quality, verified tool connections that any agent can pick up and use immediately.

## The core rule: run before you write

Every snippet in a connection file must be code you actually executed and saw succeed. No copy-pasting from docs. No hypothetical endpoints. If you can't run it, don't write it.

This is the single most important quality gate. A connection file with one working snippet is better than five unverified ones.

## How to add a new tool connection

1. **Read the playbook:** Load `add-new-connection/SKILL.md` — it walks through the full process from research to validation to wiring.

2. **Research the tool:** Find the official API docs, identify the auth mechanism, find the base URL.

3. **Validate against production:** Test connectivity, auth, and at least 2 read endpoints. Record actual output.

4. **Write the connection file:** Use the format in `add-new-connection/SKILL.md`. Every snippet must have a `# → {actual output}` comment.

5. **Wire into the index:** Update `tool_connections/SKILL.md` in all 3 places (frontmatter, table, inline section).

6. **Open a PR** with the new file and the index update.

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

## SSO-based tools

If the tool uses SSO rather than long-lived API keys:

1. Add a session capture function to `playwright_sso.py` following the Grafana or Slack patterns.
2. Add a `--{tool}-only` CLI flag.
3. Add a session validity check (use `_http_get_no_redirect` for redirect-based expiry).
4. Document the refresh command in the tool's `.md` file.

## PR checklist

- [ ] New connection file at `tool_connections/{tool-name}.md`
- [ ] Every snippet was actually run and includes real output in comments
- [ ] Auth flow documented from scratch
- [ ] Index updated (`tool_connections/SKILL.md`) in all 3 places
- [ ] `env.sample` updated with new credential vars
- [ ] `CONTRIBUTING.md` doesn't need updating (this file is stable)

## Questions?

Open an issue. Describe the tool you're trying to connect and what you've already tried.
