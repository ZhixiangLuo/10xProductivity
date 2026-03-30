---
name: review-staging-pr
description: Review a staging contribution PR, merge it (so the contributor gets GitHub credit), promote the files to tool_connections/, clean staging, and acknowledge the contribution with a PR comment.
---

# Review Staging PR — Review, Merge, Promote, Clean

> **What this file is for:** A contributor has opened a PR adding files to `staging/`. This workflow takes you from PR URL to a clean, promoted connection in `tool_connections/` in one pass.

---

## Step 1: Review

Fetch the PR diff and check every item below. All must pass before proceeding.

```bash
gh pr view <PR_NUMBER> --repo ZhixiangLuo/10xProductivity --json title,body,files
gh api repos/ZhixiangLuo/10xProductivity/pulls/<PR_NUMBER>/files \
  | python3 -c "import sys,json; [print(f['filename'],'\n',f.get('patch','')[:4000]) for f in json.load(sys.stdin)]"
```

**Review checklist:**

- [ ] Files are in `staging/{tool-name}/` only — no `.env`, no `verified_connections.md`, no `env.sample`
- [ ] Frontmatter complete in `connection-*.md`: `tool`, `auth`, `author`, `verified`, `env_vars`
- [ ] Every snippet has a `# →` output comment with real output (not illustrative)
- [ ] Validation summary in PR body covers successes AND documents any 403/404 limitations
- [ ] Personal/org-specific data scrubbed — no real tokens, org domains, usernames, internal resource names
- [ ] Prompt injection check noted as done in PR body
- [ ] Tool is commercial/publicly available — any M365 subscriber, any Slack customer, etc. (not internal-only)
- [ ] Connection is general — works for any user, not tied to a specific org's VPN or identity provider
- [ ] `sso.py` (if present): follows `check()` + `capture()` pattern, has `--force` flag, `.env` path resolves correctly from both `staging/` and `tool_connections/` paths

If any item fails, comment on the PR with what needs to be fixed and stop.

---

## Step 2: Merge (gives contributor GitHub credit)

```bash
gh pr merge <PR_NUMBER> --repo ZhixiangLuo/10xProductivity --squash --admin
git checkout main && git pull origin main
```

The `--admin` flag bypasses branch protection when needed. The contributor's commits are squash-merged so they appear in the repo history and count toward their contribution graph.

---

## Step 3: Promote to tool_connections/ and clean staging

```bash
# Copy to tool_connections/ (create the verified directory)
cp -r staging/{tool-name}/ tool_connections/{tool-name}/

# Remove from staging — it's now in tool_connections/
rm -rf staging/{tool-name}/

# Verify
ls tool_connections/{tool-name}/
# should have: connection-{auth-method}.md, setup.md, and sso.py if applicable
```

Commit both changes together:

```bash
git add tool_connections/{tool-name}/ staging/{tool-name}/
git commit -m "Promote {tool-name} from staging to tool_connections (PR #<PR_NUMBER>)"
git push origin main
```

Capture the promotion commit hash:

```bash
git rev-parse --short HEAD
# → abc1234
```

---

## Step 4: Acknowledge the contribution

Leave a comment on the PR:

```bash
gh pr comment <PR_NUMBER> --repo ZhixiangLuo/10xProductivity \
  --body "Thanks for the contribution! Promoted to \`tool_connections/{tool-name}/\` in commit \`abc1234\`. 🎉"
```

Replace `abc1234` with the actual commit hash from Step 3.

---

## Summary

| Step | What happens |
|------|-------------|
| Review | Verify checklist — reject with feedback if anything fails |
| Merge | PR merged → contributor gets GitHub contribution credit |
| Promote + clean | Files moved from `staging/` to `tool_connections/` in one commit |
| Comment | PR acknowledged with promotion commit hash |
