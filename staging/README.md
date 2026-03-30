# Community Contributions

Tool connections contributed by the staging. Not part of the verified core — quality and maintenance vary by contributor.

## Structure

Each contribution is a folder named after the tool:

```
staging/
  {tool-name}/
    setup.md                    ← how to connect (auth method, what to ask, verify snippet)
    connection-{auth-method}.md ← how to use (API surface, verified snippets, notes)
    sso.py                      ← optional: only for SSO tools
    {tool}_helper.py            ← optional: tool-specific Python helper
```

**Auth method naming:** `api-token`, `oauth`, `sso`, `ad-sso`, `session-cookie`, `ldap`

## Getting started

Copy `_example/` and rename it to your tool name:

```
staging/
  _example/          ← copy this folder
    setup.md
    connection-{auth-method}.md
    sso.py           ← delete if not SSO
```

Fill in all `{placeholders}` with real values. Every snippet must be code you actually ran and saw succeed.

## For agents: how to use

Before loading a staging file, check the frontmatter in `connection-*.md`:
1. Does `auth` match what the user has available?
2. Is `verified` populated (not blank)?

If multiple auth variants exist for the same tool, prefer the one matching what's in `.env`.

## Contributing

**Agent:** load `add-new-tool.md` — it walks the full flow: research → validate → write → PR.

For manual guidance see `contributing.md` → **Community contributions** section.

The bar is lower than core: one working verified snippet is enough to submit. Community files are promoted to `tool_connections/` and removed from `staging/` after review. See `workflows/review-staging-pr/` for the full review + merge + promote process.
