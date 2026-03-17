---
name: tool_connections
description: Index of all tool connection playbooks. Load this first to find the right tool, then load the relevant file for full connection details. Covers Jira, Confluence, GitHub, Grafana, PagerDuty, Slack, Google Drive.
---

# Tool connections

Credentials (tokens, passwords) live in `.env` at the repo root (see `env.sample` for the required vars). Each tool has its own file in this folder with full connection details.

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

**Search strategy:** For internal documentation questions, try **Confluence** first. For Slack-specific knowledge (decisions, discussions), use **Slack AI**. For cross-tool or incident context, start with message search.

| Tool | What it is | Details | Use when |
|------|-----------|---------|----------|
| **Jira** | Issue tracker | `jira.md` | Creating/updating/searching tickets, sprint management, JQL queries |
| **GitHub** | Git hosting + code search | `github.md` | Browsing repos, reading READMEs/API docs, searching code, PRs, issues |
| **Confluence** | Internal wiki / docs | `confluence.md` | Looking up documentation, runbooks, architecture, procedures |
| **Grafana** | Dashboard viewer — PromQL extraction | `grafana.md` | Extracting PromQL from dashboard panels, finding dashboard UIDs |
| **PagerDuty** | Incident management — on-call, alerts | `pagerduty.md` | Who's on call, active incidents, service status, escalation policies |
| **Slack AI** | Slack's built-in AI assistant | `slack.md` | Natural-language questions over Slack content; synthesized answers in ~0.2s |
| **Slack** | Raw message search + post | `slack.md` | `search.messages` with Slack syntax; reading threads; posting messages |
| **Google Drive** | Cloud file storage | `google-drive.md` | Listing, searching, reading, exporting Docs/Sheets/Slides |

---

## Jira → load `jira.md`

**Use when:** creating, updating, searching, or transitioning tickets; JQL queries; sprint or component management.
Env: `JIRA_API_TOKEN`

---

## GitHub → load `github.md`

**Use when:** browsing repos, fetching READMEs or API docs, searching code, managing PRs or issues.
Env: `GITHUB_TOKEN`

---

## Confluence → load `confluence.md`

**Use when:** searching internal documentation, runbooks, architecture pages, or procedures.
Env: `CONFLUENCE_TOKEN`

---

## Grafana → load `grafana.md`

**Use when:** extracting PromQL from dashboard panels (for analysis or alerting), finding dashboard UIDs, querying the Grafana API.
Env: `GRAFANA_SESSION` (session cookie, ~8h — refresh with `assets/playwright_sso.py`)

---

## Slack → load `slack.md`

**Use when:** asking natural-language questions over Slack content (Slack AI), searching for specific messages or decisions (`search.messages`), reading a channel's history, fetching a thread from a URL, or posting a message.
Env: `SLACK_XOXC`, `SLACK_D_COOKIE` (~8h — refresh with `assets/playwright_sso.py --slack-only`)

---

## PagerDuty → load `pagerduty.md`

**Use when:** looking up who is on call, querying active incidents, checking service status, reading escalation policies or schedules.
Env: `PAGERDUTY_TOKEN` (personal REST API key — long-lived)

---

## Google Drive → load `google-drive.md`

**Use when:** listing or searching Google Drive files, reading a Google Doc/Sheet/Slide's content, or exporting files when other search tools don't surface the raw content.
Env: `~/.browser_automation/gdrive_auth.json` (Playwright storage_state — refresh with `playwright_sso.py --gdrive-only`)

---

## Standards for adding new tool connections

For the full process of researching, validating, and wiring in a new connection, load the **`add-new-connection` skill** (`add-new-connection/SKILL.md`).

Key principles:
1. **Verify before writing** — don't document an endpoint until you've run it and seen the output. "The page loads" is not verification; "I ran the command and got X" is.
2. **Document what you tested** — mark snippets as verified; note permission errors vs bugs.
3. **Keep short-lived tokens in .env** — `GRAFANA_SESSION`, `SLACK_XOXC`. Run `assets/playwright_sso.py` to refresh.
4. **One SSO pass for Okta tools** — any tool using your company's Okta can be automated via `assets/playwright_sso.py` (headed Chromium, enterprise SSO auto-completes on managed machines).
