---
name: enterprise-search
description: >
  Search your entire company's institutional knowledge in one query — Slack,
  Confluence, Jira, Linear, Notion, GitHub, plus any AI or multi-source search
  tool listed in verified_connections.md. Follow workflows/enterprise-search.
  One question, every connected tool, synthesized answer in seconds. No tab
  switching. No copy-paste. Use when the user asks about a decision, an incident,
  a topic, a person, a past discussion, or anything that might be documented
  across work tools. Also triggers on: "find", "search for", "who worked on",
  "what was the decision about", "is there a doc on", "any Slack about".
source: https://github.com/zhixiangluo/10xProductivity
---

# Enterprise Search

> One question. Every connected tool. One synthesized answer.

Search your company's knowledge across Slack, Confluence, Jira, Linear, Notion,
GitHub, and more — simultaneously, in a single query.

---

## Before you search: check connection status

```bash
ls verified_connections.md 2>/dev/null && grep -c "^##" verified_connections.md || echo "0"
```

- **1+ tools connected** → read `verified_connections.md` (capability index), then follow `workflows/enterprise-search/enterprise-search.md` for the search. That workflow always uses Slack + Confluence when connected, may include AI-synthesized search tools listed only in `verified_connections.md` (per each connection file), and adds Jira/Linear/Notion/GitHub when relevant.
- **Not connected / empty** → read `setup.md`. Your agent handles the full connection flow — credentials, SSO, verification — in one session. ~5 minutes per tool.

---

## What you can ask

- *"Search for the discussion about the database migration"*
- *"Find any Jira tickets related to the login timeout bug"*
- *"What was the decision about the API versioning approach?"*
- *"Is there a Confluence runbook for on-call handoffs?"*
- *"Who worked on the payments refactor and what did they decide?"*

The search workflow handles routing, parallel execution across tools, and synthesized results. You don't need to specify which tool — the agent figures that out.
