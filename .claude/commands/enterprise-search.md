# Enterprise Search

Search institutional knowledge across every connected tool simultaneously.

One query → Slack + Confluence (always when connected) + any AI-synthesized search tools in `verified_connections.md` + Jira/Linear/Notion/GitHub when relevant → synthesized answer.

## Steps

1. Check connection status:
   ```bash
   ls verified_connections.md 2>/dev/null && grep -c "^##" verified_connections.md || echo "0"
   ```

2. **If 1+ tools connected:** Read `verified_connections.md` (your active tool index), then follow
   `workflows/enterprise-search/enterprise-search.md` to search for: $ARGUMENTS

3. **If not connected / empty:** Read `setup.md`. It walks through connecting each tool you use —
   credentials, SSO, verification — your agent runs the whole flow. ~5 min per tool.
   Once set up, run this command again.

## What this searches

| Tool | What it finds |
|------|--------------|
| Slack | Decisions, incident threads, "why did we do X" |
| Confluence | Runbooks, architecture docs, procedures |
| Jira | Tickets, bugs, epics, sprint history |
| Linear | Project issues and feature requests |
| Notion | Pages and databases |
| GitHub | Code, PRs, issues (code-related queries only) |
| *Other* | If `verified_connections.md` lists an AI assistant or multi-source knowledge search, follow that connection file in parallel — see the workflow. |

Only connected tools are searched. The workflow adapts to whatever is in `verified_connections.md`.
