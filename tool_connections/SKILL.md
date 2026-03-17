---
name: tool_connections
description: Index of all tool connection playbooks. Load this first to find the right tool, then load the relevant file for full connection details. Covers Confluence, Slack, Jira, GitHub, Grafana, PagerDuty, Google Drive, and more.
---

# Tool connections

**Keep this file loaded for the entire session.** It is the capability index — it tells you which tools are available and when to reach for each one.

These are **universal capabilities**, not scoped to any single repo or project. Whenever a task calls for it — in any codebase, any context — proactively use these tools: look up a Jira ticket, search Slack for a decision, fetch a Confluence runbook, check PagerDuty. You don't need to be asked. Load individual tool files (`jira.md`, `slack.md`, etc.) on demand when you need full connection details for a specific tool.

Credentials (tokens, passwords) live in `.env` at the repo root (see `env.sample` for the required vars). Each tool has its own file in this folder with full connection details.

**New here?** Read `SETUP.md` first — it walks through which credentials to get, runs SSO where needed, and verifies each connection. Key principle: **do as much as possible yourself; ask the user only for what only they can provide, phrased non-technically.**

**Short-lived tokens** (`GRAFANA_SESSION`, `SLACK_XOXC`, `SLACK_D_COOKIE` — ~8h): refresh with:
```bash
source .venv/bin/activate && python3 tool_connections/assets/playwright_sso.py
```

**Google Drive session** (long-lived, days/weeks):
```bash
source .venv/bin/activate && python3 tool_connections/assets/playwright_sso.py --gdrive-only
```

---

## Tool quick-reference

Tools are ordered by **information value** — start with Tier 1. Once Confluence, Slack, Jira, and GitHub are connected, your agent can answer almost any question about your codebase, your team's decisions, and your current work. Everything else extends from there.

### Tier 1 — Knowledge & Context (start here)

| Tool | What it is | Details | Use when |
|------|-----------|---------|----------|
| **Confluence** | Internal wiki / docs | `confluence.md` | Looking up runbooks, architecture, procedures, how-tos |
| **Slack** | Team messaging — search + AI | `slack.md` | Decisions, context, who to ask; Slack AI synthesizes answers from all Slack history |
| **Jira** | Issue tracker | `jira.md` | Fetching/creating/updating tickets, JQL search, sprint management |
| **GitHub** | Git hosting + code search | `github.md` | Browsing repos, reading READMEs/API docs, searching code, PRs, issues |
| **Microsoft Teams** | Team messaging (Microsoft) | *(coming soon)* | Decisions and context for Teams-based organizations |
| **Outlook / M365** | Email, calendar, OneDrive, SharePoint | *(coming soon)* | Reading email/calendar, accessing SharePoint/OneDrive docs, Excel/Word files |

### Tier 2 — Observability & Operations

| Tool | What it is | Details | Use when |
|------|-----------|---------|----------|
| **Grafana** | Dashboard viewer — PromQL extraction | `grafana.md` | Extracting PromQL from dashboard panels, finding dashboard UIDs |
| **PagerDuty** | Incident management — on-call, alerts | `pagerduty.md` | Who's on call, active incidents, service status, escalation policies |
| **OpsGenie** | Incident management (Atlassian) | *(coming soon)* | On-call and alerting for OpsGenie-based orgs |
| **Datadog** | Metrics, logs, APM | *(coming soon)* | Time-series metrics, log search, APM traces |
| **Splunk** | Log analysis | *(coming soon)* | Log search and analysis for Splunk-based orgs |

### Tier 3 — File & Document Access

| Tool | What it is | Details | Use when |
|------|-----------|---------|----------|
| **Google Drive** | Cloud file storage | `google-drive.md` | Listing, searching, reading, exporting Docs/Sheets/Slides |
| **Notion** | Docs + project management | *(coming soon)* | Teams using Notion as their primary knowledge base |

### Tier 4 — Issue Tracking & Support Alternatives

| Tool | What it is | Details | Use when |
|------|-----------|---------|----------|
| **Linear** | Issue tracker (developer-focused) | *(coming soon)* | Teams using Linear instead of Jira |
| **Zendesk** | Customer support tickets | *(coming soon)* | Looking up customer tickets, support history |
| **ServiceNow** | Enterprise ITSM | *(coming soon)* | IT service management, change requests |
| **Jenkins / GitHub Actions** | CI/CD pipelines | *(coming soon)* | Triggering builds, checking pipeline status and logs |

---

## Confluence → load `confluence.md`

**Use when:** looking up internal documentation, runbooks, architecture pages, procedures, or any "how does X work?" question.
Env: `CONFLUENCE_TOKEN`, `CONFLUENCE_BASE_URL`

---

## Slack → load `slack.md`

**Use when:** asking natural-language questions over Slack content (Slack AI), searching for specific messages or decisions (`search.messages`), reading a channel's history, fetching a thread from a URL, or posting a message.
Env: `SLACK_XOXC`, `SLACK_D_COOKIE` (~8h — refresh with `assets/playwright_sso.py --slack-only`)

---

## Jira → load `jira.md`

**Use when:** creating, updating, searching, or transitioning tickets; JQL queries; sprint or component management.
Env: `JIRA_API_TOKEN`, `JIRA_BASE_URL`

---

## GitHub → load `github.md`

**Use when:** browsing repos, fetching READMEs or API docs, searching code, managing PRs or issues.
Env: `GITHUB_TOKEN`, `GITHUB_BASE_URL`

---

## Grafana → load `grafana.md`

**Use when:** extracting PromQL from dashboard panels (for analysis or alerting), finding dashboard UIDs, querying the Grafana API.
Env: `GRAFANA_BASE_URL` (set this first), `GRAFANA_SESSION` (session cookie, ~8h — refresh with `assets/playwright_sso.py`)

---

## PagerDuty → load `pagerduty.md`

**Use when:** looking up who is on call, querying active incidents, checking service status, reading escalation policies or schedules.
Env: `PAGERDUTY_TOKEN` (personal REST API key — long-lived)

---

## Google Drive → load `google-drive.md`

**Use when:** listing or searching Google Drive files, reading a Google Doc/Sheet/Slide's content, or exporting files when other search tools don't surface the raw content.
Auth: `~/.browser_automation/gdrive_auth.json` (Playwright storage_state — refresh with `playwright_sso.py --gdrive-only`)

---

## Standards for adding new tool connections

For the full process of researching, validating, and wiring in a new connection, load the **`add-new-connection` skill** (`add-new-connection/SKILL.md`).

Key principles:
1. **Verify before writing** — don't document an endpoint until you've run it and seen the output.
2. **Document what you tested** — mark snippets as verified; note permission errors vs bugs.
3. **Keep short-lived tokens in .env** — `GRAFANA_SESSION`, `SLACK_XOXC`. Run `assets/playwright_sso.py` to refresh.
4. **Set base URLs in .env before running the SSO script** — `GRAFANA_BASE_URL`, `SLACK_WORKSPACE_URL` must be filled in first.
