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
  SKILL.md                  ← index: which tool to use when (keep loaded)
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
env.sample                    ← credential variable reference (copy to .env)

community/
  README.md                 ← how community files are organized
  TEMPLATE.md               ← template for new contributions
  {tool-name}/
    {auth-method}-{author}.md  ← e.g. linear/api-token-alice.md

add-new-connection/
  SKILL.md                  ← playbook: how to research, validate, and add a new tool
```

---

## Quick start

```bash
git clone https://github.com/yourusername/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium
cp env.sample .env
```

Then point your agent at the setup guide:

```
Read SETUP.md and set up my tool connections.
```

Your agent will ask which tools you use, guide you to get each credential, run SSO where needed, and verify each connection works. Tools are set up in priority order — knowledge tools first (Confluence, Slack, Jira, GitHub), then observability, then file access.

**Manual setup:** edit `.env` with your credentials, then see `tool_connections/SKILL.md` for the full tool reference.

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

## Final Notes

This repo provides the foundational skills to unlock 10x productivity, but it won't work out of the box. Ask your favorite agent to set it up, try it out, and gradually automate everything that can be automated — humans can always be in the loop.

**A real warning:** 10x productivity will not get you 10x rewards. In most organizations, the person who automates their job away doesn't get paid more — they just get more work. Be deliberate about where you direct this leverage.

---

## License

MIT
