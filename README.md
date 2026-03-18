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
tool_connections/             ← core, validated connection files
  github-api-token.md
  slack-sso-session.md
  jira-api-token.md
  confluence-api-token.md
  grafana-sso-session.md
  ...
  assets/
    playwright_sso.py         ← SSO session automation (Okta, Google, Microsoft)

community/                    ← community-contributed connections (lower validation bar)
  {tool-name}/
    {auth-method}-{author}.md ← e.g. community/linear/api-token-alice.md

add-new-connection/
  SKILL.md                    ← playbook: research, validate, and write a new connection file

contribute-connection/
  SKILL.md                    ← playbook: full flow from research to merged PR

verified_connections.example.md  ← master catalog of all available connections
env.sample                        ← credential variable reference (copy to .env)
```

---

## Quick start

```bash
git clone https://github.com/ZhixiangLuo/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium
cp env.sample .env
```

Then point your agent at the setup guide — the most effective way is to paste the full path so your agent can load it immediately:

```
Read /path/to/10xProductivity/SETUP.md and set up my tool connections.
```

Your agent will ask which tools you use, guide you to get each credential, run SSO where needed, and verify each connection works.

**Manual setup:** edit `.env` with your credentials, then see `verified_connections.example.md` for the full tool catalog.

---

## Supported tools

The repo currently covers the tools developers use most across their daily work — and the list grows with every contribution.

**Dev tools:** GitHub (repos, PRs, issues, code search), Jira (fetch, search, create, update tickets), Confluence (search and read internal docs), Grafana (extract PromQL, find dashboards), PagerDuty (on-call schedules, active incidents).

**Communication:** Slack (AI search, message search, read threads, post messages).

**File access:** Google Drive (list, search, read, export Docs/Sheets/Slides).

See `verified_connections.example.md` for the full catalog including community contributions.

---

## Who uses this repo and how

**User** — you want to connect your agent to tools you already use:
1. Follow the [Quick start](#quick-start) above
2. Ask your agent: *"Read /path/to/10xProductivity/SETUP.md and set up my tool connections"*
3. Your agent generates `verified_connections.md` — load it at session start

**Contributor** — you want to add a new tool or improve an existing connection:
1. Ask your agent: *"Load contribute-connection/SKILL.md and add a connection for [Tool]"*
2. The skill walks through: research → validate → write → PR
3. Community files (`community/`) have a lower bar; core (`tool_connections/`) requires multi-environment validation

---

## Contributing

Contributions are welcome for:
- **New tool** — a tool not yet in the repo
- **New auth variant** — a different auth method for an existing tool (e.g. AD SSO vs API token)
- **New deployment variant** — e.g. Jira Server vs Jira Cloud
- **Improvement to an existing connection** — fixing broken snippets, adding missing endpoints, updating stale auth

If something doesn't work or you want to request a new tool, open an issue.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full process. The core rule: **run before you write.** Every snippet must be code you actually executed and saw succeed. No copy-paste from docs.

---

## Final Notes

This repo provides the foundational skills to unlock 10x productivity, but it won't work out of the box. Ask your favorite agent to set it up, try it out, and gradually automate everything that can be automated — humans can always be in the loop.

**A real warning:** 10x productivity will not get you 10x rewards. In most organizations, the person who automates their job away doesn't get paid more — they just get more work. Be deliberate about where you direct this leverage.

---

## License

MIT
