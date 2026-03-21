# 10xProductivity

> *Every tool you can use as a human on your laptop, your agent can use too — with zero infrastructure, zero cloud services, zero new permissions.*

[![GitHub Stars](https://img.shields.io/github/stars/ZhixiangLuo/10xProductivity?style=social)](https://github.com/ZhixiangLuo/10xProductivity/stargazers)

If this saves you time, consider giving it a ⭐ — it helps others discover it.

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

## What becomes possible

Each connection you add isn't just a new tool — it compounds with everything else.

Once your agent can see across your tools simultaneously, a new class of capability emerges:

**Connected knowledge**
Ask questions that span systems. "What was the decision behind this change?" pulls the GitHub PR, the Jira ticket it closed, the Slack thread where it was debated, and the Confluence doc that captured the outcome — in one answer, in seconds.

**Cross-tool reasoning**
"Show me all PagerDuty incidents from last week that still have open Jira follow-ups with no activity in 3 days." That query touches three systems, requires no new integration layer, and runs right now. The agent is the integration layer.

**Compound automation**
Repetitive multi-step work — triage a Slack alert, file a Jira ticket, assign it, post a summary back to the channel — becomes a single agent instruction. The tools are already connected; the only thing left is telling it what to do.

**Institutional memory**
Your agent stops being a generic assistant and starts being a contextual one — aware of how your team works, who owns what, what's in flight, and what happened before. That context doesn't live in any one tool. It lives in the connections between them.

The pre-built recipes in this repo are a starting point. The actual ceiling is "everything you can do on your laptop" — which is everything.

---

## What's in this repo

**Agent-readable playbooks** for connecting your local agent to the tools you already use — with no limit on what those tools can be. Each playbook is a skill file — not a tutorial for humans, but a structured document an LLM agent can read, understand, and execute.

`tool_connections/` covers the tools developers commonly share across teams (GitHub, Slack, Jira, etc.), but the same approach works for anything: internal company tools, proprietary systems, niche SaaS products, personal tools you use daily. If it has an API or a browser interface, your agent can use it.

```
personal/                     ← your own recipes (gitignored) — internal tools, patched recipes, anything not in tool_connections/
  {tool-name}/
    setup.md
    connection-{auth-method}.md

tool_connections/             ← pre-built recipes for common tools
  slack/
    setup.md                  ← how to connect (what to ask, which script to run, verify snippet)
    connection-sso.md         ← how to use once connected (API surface, snippets, gotchas)
  jira/
    setup.md
    connection-api-token.md   ← Jira Cloud (API token + Basic auth)
  github/
    setup.md
    connection-api-token.md
  confluence/
    setup.md
    connection-api-token.md
  grafana/
    setup.md
    connection-sso.md
  outlook/
    setup.md
    connection-m365.md        ← work account (Azure AD / Graph + OWA)
    connection-personal.md    ← personal Outlook.com account
  ...                         ← one folder per tool, multiple connection-*.md for variants
  shared_utils/
    browser.py / sso_patterns.py  ← shared SSO utilities for per-tool sso.py scripts
  google-drive/
    ...
    google_drive.py           ← importable helper (Google Drive only)
  outlook/
    ...
    get_outlook_token.py      ← token capture script (Outlook.com only)

workflows/                  ← pre-built workflows that compose multiple tool connections
  search/
    search.md             ← search institutional knowledge across all connected tools simultaneously

staging/                    ← staging-contributed connections (lower validation bar)
  {tool-name}-{auth-method}.md  ← e.g. staging/linear-api-token.md

add-new-tool.md          ← playbook: research auth → ask URL first → try the most likely auth → ask only for missing credentials → validate → write → PR (contribution optional)

utils/
  generate_verified.py            ← generate verified_connections.md from each tool's connection-*.md frontmatter

verified_connections.example.md  ← preamble template and format examples (not a comprehensive list)
env.sample                        ← stub only — real var templates live in each tool's setup.md
```

---

## Quick start

```bash
git clone https://github.com/ZhixiangLuo/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium
touch .env
```

Then point your agent at the setup guide — the most effective way is to paste the full path so your agent can load it immediately:

```
Read /path/to/10xProductivity/setup.md and set up my tool connections.
```

Your agent will ask which tools you use — including your company's internal tools, custom dashboards, and proprietary systems — guide you to get each credential, run SSO where needed, and verify each connection works. Works for any tool: pre-built recipes for common tools, and an identical setup path for anything else.

**Manual setup:** copy the `.env` block from each `tool_connections/{tool}/setup.md` you use into `.env`, then run `python3 utils/generate_verified.py` to build your capability index.

---

## What you can connect

**There is no limit.** Any tool accessible via API, CLI, or browser on your laptop can be connected.

The most valuable connections are usually the internal tools your company runs — the deployment portal, the incident tracker, the internal knowledge base, the custom dashboards. No one outside your org can pre-build those for you, but the setup experience is identical: paste a URL, your agent handles auth, done. They live in `personal/` (gitignored) and never leave your machine.

The pre-built recipes in `tool_connections/` are a head start for the tools most developers share across companies — GitHub, Slack, Jira, Confluence, Grafana, PagerDuty, Google Drive, and more. They save you setup time for the common ones, but they're not the ceiling.

The approach is the same regardless of what you're connecting:
- **Internal company tools** — your team's custom systems, internal portals, proprietary platforms → `personal/` via `add-new-tool.md`
- **Common developer tools** — already in `tool_connections/`, ready to use
- **Personal tools** — anything you use for your own work → same `personal/` path, stays private

---

## Who uses this repo and how

**User** — you want to connect your agent to tools you already use:
1. Follow the [Quick start](#quick-start) above
2. Ask your agent: *"Read /path/to/10xProductivity/setup.md and set up my tool connections"*
3. Setup connects your tools, generates `verified_connections.md`, and creates a local agent skill — from that point your tools and the search workflow are available automatically at the start of every session. No MCP server, no plugin, no admin approval — just your agent reading files and calling APIs you already have access to.

**Contributor** — you want to add a new tool or improve an existing connection:
1. Ask your agent: *"Load add-new-tool.md and add a connection for [Tool]"*
2. The skill walks through: research auth → ask URL first → try the most likely auth → ask only for missing credentials → validate → write → PR (contribution is optional and only for commercial tools)
3. Community files (`staging/`) have a lower bar; core (`tool_connections/`) requires multi-environment validation

---

## Contributing

Contributions are welcome for:
- **New tool** — a tool not yet in the repo
- **New auth variant** — a different auth method for an existing tool (e.g. AD SSO vs API token)
- **New deployment variant** — e.g. Jira Server vs Jira Cloud
- **Improvement to an existing connection** — fixing broken snippets, adding missing endpoints, updating stale auth

If something doesn't work or you want to request a new tool, open an issue.

See [contributing.md](contributing.md) for the full process. The core rule: **run before you write.** Every snippet must be code you actually executed and saw succeed. No copy-paste from docs.

---

## Final Notes

This repo provides the foundational skills to unlock 10x productivity, but it won't work out of the box. Ask your favorite agent to set it up, try it out, and gradually automate everything that can be automated — humans can always be in the loop.

**A real warning:** 10x productivity will not get you 10x rewards. In most organizations, the person who automates their job away doesn't get paid more — they just get more work. Be deliberate about where you direct this leverage.

---

If this repo helped you 10x your workflow, a ⭐ goes a long way — it helps others find it.

---

## License

MIT
