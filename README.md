# 10xProductivity

> *Every tool you can use as a human on your laptop, your agent can use too — with zero infrastructure, zero cloud services, zero new permissions.*

## The Philosophy

Most "AI integration" approaches ask you to:
- Set up cloud middleware (Zapier, MCP servers, hosted agents)
- Request IT-approved service accounts
- Wait for admin provisioning
- Accept new attack surfaces and vendor lock-in

**10xProductivity flips this completely.**

Apps are built for humans on laptops. Browsers, CLIs, REST APIs — they're all already there. Your agent uses the same surface. No integration layer, no middleware, no new permissions.

### Four principles

**1. Local agent as the universal client**
Your laptop is the platform. The agent is just a smarter version of you running scripts. No new infrastructure required.

**2. Security by locality**
The threat model is identical to you doing it manually. Nothing new is exposed. No cloud service sits between you and your tools holding your credentials. The only trust you extend is to the agent runtime itself (Cursor, Claude Code, Codex, Copilot, etc.) — which you've already decided to trust.

**3. Identity = accountability**
Your personal token. Your name on every action. This is a stronger audit trail than most enterprise automation, where actions are taken by service accounts with shared credentials. The agent acts *as you*: you get the credit, you get the blame, and the audit log is already there in every system you use.

**4. Zero friction to start**
No OAuth app approval. No IT ticket. No staging environment. If you can log in, your agent can act. The barrier is "do you have a terminal and an API token" — which any developer already has.

### The result

If every individual is 10x productive, the team and company is 10x as a result. Not through a top-down platform rollout — through individuals who are dramatically more capable, spreading organically.

---

## What's in this repo

**Agent-readable playbooks** for connecting your local agent to the tools you already use. Each playbook is a skill file — not a tutorial for humans, but a structured document an LLM agent can read, understand, and execute.

```
tool_connections/
  SKILL.md                  ← index: which tool to use when
  jira.md                   ← Jira: fetch, search, create, update issues
  github.md                 ← GitHub: repos, PRs, issues, code search
  confluence.md             ← Confluence: search and read internal docs
  grafana.md                ← Grafana: extract PromQL, find dashboards
  pagerduty.md              ← PagerDuty: on-call, incidents, services
  slack.md                  ← Slack: AI search, message search, post
  google-drive.md           ← Google Drive: list, search, read, export
  assets/
    playwright_sso.py       ← SSO session automation (Okta, Google)
    google_drive.py         ← Google Drive helper class
  env.sample                ← credential variable reference

add-new-connection/
  SKILL.md                  ← playbook: how to research, validate, and add a new tool
```

---

## Quick start

**1. Clone and set up Python env**
```bash
git clone https://github.com/yourusername/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium
```

**2. Copy env.sample and fill in your credentials**
```bash
cp tool_connections/env.sample .env
# Edit .env — add your personal API tokens
```

**3. For SSO-based tools (Grafana, Slack, Google Drive), run the session refresher**
```bash
python3 tool_connections/assets/playwright_sso.py
```
A browser window opens briefly, SSO completes automatically on a managed machine, and tokens are written to `.env`.

**4. Point your agent at the skill files**

In Cursor, Claude Code, Codex, or any agent runtime — reference the relevant skill file:
```
Read tool_connections/SKILL.md to understand which tool to use, then load the specific tool file for the full connection details.
```

Your agent now has authenticated access to every tool in the library.

---

## Supported tools

| Tool | Auth | What your agent can do |
|------|------|------------------------|
| **Jira** | API token | Fetch issues, JQL search, create/update tickets, add comments |
| **GitHub** | Personal access token | Browse repos, search code, read READMEs, manage PRs and issues |
| **Confluence** | API token | Search pages, fetch content, browse spaces |
| **Grafana** | Session cookie (SSO) | Extract PromQL from dashboards, find dashboard UIDs |
| **PagerDuty** | Personal API key | Who's on call, active incidents, service status, schedules |
| **Slack** | Session token (SSO) | Slack AI search, message search, read threads, post messages |
| **Google Drive** | Browser session (SSO) | List, search, read, export Docs/Sheets/Slides |

---

## How SSO session auth works

Some tools (Grafana, Slack, Google Drive) don't offer simple API tokens — they use SSO. The `playwright_sso.py` script handles this:

1. Opens a headed Chromium window
2. Navigates to the tool's login page
3. macOS enterprise SSO (or manual login) completes authentication
4. Extracts session tokens/cookies and writes them to `.env`
5. Checks existing tokens first — only opens a browser if they're expired

For tools with simple API tokens (Jira, GitHub, PagerDuty), no browser automation is needed.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

The core rule: **run before you write.** Every snippet in a connection file must be code you actually executed and saw succeed. No copy-paste from docs.

---

## License

MIT
