# Community Contributions

Tool connections contributed by the community. These are not part of the verified core — quality and maintenance vary by contributor.

## Structure

```
community/
  {tool-name}-{auth-method}.md
```

**Filename convention:** `{tool-name}-{auth-method}.md` — mirrors core exactly (`tool_connections/jenkins-api-token.md` ↔ `community/jenkins-api-token.md`).
- The `author` field in frontmatter captures attribution — no need to repeat it in the filename.
- If two contributors submit different files for the **same tool + auth method**, append a short disambiguator: `datadog-api-key-alice.md`. This is the exception, not the rule.

**Examples:**
```
community/
  linear-api-token.md
  datadog-api-key.md
  datadog-ad-sso.md
  notion-api-token.md
```

## For agents: how to use

Each file has frontmatter declaring the tool, auth method, and verification status. Before loading a community file, check:
1. Does the `auth` field match what your user has available?
2. Is `verified` populated (not blank)?

If multiple files exist for the same tool, prefer the one whose auth method matches what's in `.env`.

## Contributing

**Agent:** load `contribute-connection/SKILL.md` — it walks the full flow: research → validate → write → PR.

For manual guidance see `CONTRIBUTING.md` — specifically the **Community contributions** section. Use the template at `community/TEMPLATE.md`.

The bar for community files is lower than core: one working verified snippet is enough to submit. If a community file gets promoted into `tool_connections/` by the owner after review, the contributor is credited and the original community file is kept as a record.
