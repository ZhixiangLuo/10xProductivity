---
name: contribute-connection
description: End-to-end skill for creating, testing, and contributing a tool connection via PR. Covers the full flow: research → validate → write community file → promote to core → open PR. Use when asked to add a new tool connection and contribute it back, or to promote an existing community file to core.
---

# Contribute a Tool Connection

## Purpose

Take a tool connection from zero to a merged PR. This skill orchestrates the full pipeline:

1. Research and validate the connection (`add-new-connection/SKILL.md`)
2. Write a verified community file
3. Promote to core if the bar is met
4. Open a PR with the correct format

**Prerequisites:** Read `tool_connections/SKILL.md` and `CONTRIBUTING.md` first.

---

## When to use

- "Add a connection for X and open a PR"
- "Promote the community/X file to core"
- "Fix the broken Y connection and PR the fix"
- You just finished validating a new connection and want to contribute it

---

## Step 1: Determine the contribution type

Ask yourself (or infer from context):

| Situation | Path |
|-----------|------|
| Brand new tool, not yet tested across envs | Community file → PR |
| Brand new tool, validated on production, generalizable auth | Core file → PR |
| Existing community file, all checklist items pass | Promote community → core → PR |
| Existing core file has broken/stale snippets | Fix in place → PR |

Branch names:
- `connection/{tool-name}` — new connection
- `connection/{tool-name}-promote` — community → core promotion
- `fix/{tool-name}` — fixing broken snippets

---

## Step 2: Build and validate the connection

If the connection file doesn't exist yet, run `add-new-connection/SKILL.md` in full before continuing. Do not proceed to Step 3 until the checklist in that skill is fully checked.

If the connection exists in `community/` and you're promoting it:
- Re-run all snippets to confirm they still work
- Record fresh output with today's date
- Check the promotion checklist in `CONTRIBUTING.md`

---

## Step 3: Write or update the file

### Community file format

Location: `community/{tool-name}/{auth-method}-{github-username}.md`

Use `community/TEMPLATE.md`. Frontmatter required:

```markdown
---
tool: {tool-name}
auth: {api-token|oauth|sso|ad-sso|session-cookie}
author: {github-username}
verified: {YYYY-MM}
env_vars:
  - {TOOL_TOKEN}
---
```

### Core file format

Location: `tool_connections/{tool-name}.md`

Frontmatter:

```markdown
---
name: {tool-name}
description: {Tool} — {one sentence what it is}. Use when {2-3 specific use cases}.
---
```

When promoting from community → core:
1. Copy the community file to `tool_connections/{tool-name}.md`
2. Replace the community frontmatter with the core frontmatter above
3. Wire into `tool_connections/SKILL.md` in all 3 places (frontmatter description, table row, inline section) — see `add-new-connection/SKILL.md` Step 5 for exact format
4. Update `SETUP.md` if the tool was listed as "coming soon"
5. Delete the community file (or keep it if auth variant differs from core)

---

## Step 4: Run the PR checklist

Before opening the PR, verify every box. Read the relevant section from `CONTRIBUTING.md`:

- Community: **Community contribution checklist**
- Core / promotion: **Core contribution checklist** + **Promotion checklist**
- SSO tool: also **SSO tool checklist**

Do not open the PR if any box is unchecked. Fix the gap first.

---

## Step 5: Open the PR

```bash
# 1. Create and switch to branch
git checkout -b connection/{tool-name}          # or connection/{tool-name}-promote

# 2. Stage all relevant changes
git add community/{tool-name}/                  # if community file added/changed
git add tool_connections/                       # if core file added/changed
git add tool_connections/SKILL.md               # if index updated
git add CONTRIBUTING.md SETUP.md               # if updated
git add tool_connections/assets/playwright_sso.py  # if SSO support added
git add .env                                   # if new env vars added (check .gitignore first!)

# 3. Commit
git commit -m "Add {Tool Name} connection ({auth-method})"
# For promotion: git commit -m "Promote {Tool Name} connection to core"
# For fix:       git commit -m "Fix {Tool Name} connection: {what broke}"

# 4. Push
git push -u origin HEAD

# 5. Open PR
gh pr create \
  --title "{PR title per CONTRIBUTING.md}" \
  --body "$(cat <<'EOF'
## What this adds

{1-2 sentences: what tool, what auth method, what it enables.}

## Verified against

{environment, date, e.g. "Production (api.example.com) — 2026-03, no VPN required"}

## Checklist

- [ ] File placed correctly
- [ ] Frontmatter complete
- [ ] Every snippet run with real output
- [ ] Auth flow documented from scratch
- [ ] Index updated (if core)
- [ ] .env updated
- [ ] SETUP.md updated (if applicable)
- [ ] playwright_sso.py updated (if SSO)
EOF
)"
```

**Important:** Never commit `.env`. Verify it is in `.gitignore` before staging.

---

## Step 6: After the PR is open

- Post the PR URL to the user
- If CI checks run, monitor them — fix any failures before marking ready
- If reviewers request changes, address them and push to the same branch

---

## Checklist — do not mark done until all boxes checked

**Validation**
- [ ] All snippets in the connection file were actually executed
- [ ] Every snippet has real `# → {output}` comments
- [ ] Auth confirmed working on production
- [ ] At least 2 read endpoints tested

**File**
- [ ] Correct location and filename
- [ ] Correct frontmatter format (community vs core)
- [ ] No session-specific artifacts
- [ ] Search interface checked and documented or explicitly noted as absent

**Wiring (core only)**
- [ ] `tool_connections/SKILL.md` updated in all 3 places
- [ ] `SETUP.md` updated if applicable
- [ ] `.env` updated with new vars

**PR**
- [ ] Branch name follows convention
- [ ] Commit message follows convention
- [ ] PR body includes verified-against statement and checklist
- [ ] `.env` is NOT staged or committed
