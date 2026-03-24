---
name: verified_connections
device: your-device-name
description: "[your-device-name] Your active tool connections — verified and ready on this device. Gitignored — device-specific, never committed. Covers: ... Load at session start."
---

# Tool Connections — Master Catalog

**This is the example file.** Do not load this as your capability index.

- **Your active connections:** load `verified_connections.md` (gitignored — device-specific, never committed).
- **To set up connections:** *"Read setup.md and set up my tool connections."*
- **To refresh short-lived tokens (~8h):** run the tool's `sso.py` (e.g. `source .venv/bin/activate && python3 tool_connections/slack/sso.py`)

> **`device:`** Set this to your machine name (e.g. `my-macbook`, `work-laptop`). Because `verified_connections.md` is gitignored and device-specific — each machine has its own set of verified tokens — the device field lets the agent know which machine it's running on and prevents confusion when context from multiple devices appears in the same session.

The sections below illustrate the format. After verifying a tool, append its section to `verified_connections.md` using the same format — read the tool's `connection-*.md` frontmatter for name, description, and env_vars.

---

## Jira → `tool_connections/jira/connection-api-token.md`

All Jira operations — fetch issues, JQL search, update fields, write descriptions/comments, REST API quirks (components, editmeta, Agile/sprint API). Use when fetching a Jira issue, listing tickets, updating fields, writing Jira comments or descriptions, or using the Jira REST API.
Env: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_BASE_URL`

---

## Slack → `tool_connections/slack/connection-sso.md`

Slack — two complementary modes. (1) Slack AI: post a natural-language question to the Slackbot DM and get a synthesized AI answer drawn from all Slack content. (2) search.messages: raw full-text search. Also: read channel/thread history, post messages.
Env: `SLACK_XOXC`, `SLACK_D_COOKIE` (~8h — refresh with `python3 tool_connections/slack/sso.py`)

---

## Adding new connections

Add `tool_connections/{tool}/connection-*.md` with core frontmatter (`name`, `auth`, `description`, `env_vars`). After verifying, append a section to `verified_connections.md` following the format above.
