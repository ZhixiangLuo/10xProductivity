# 10xProductivity

**Turn your coding agent into a personal assistant at work — without any IT hassle.**
**10x the output (not just a single task) of every person in your company — from executives to ICs.**

Cursor, Claude Code, and similar tools are far more than coding assistants. Connected to your work tools, they become agents that can search, triage, draft, and automate — for anyone on your team, from top executives to product managers, analysts, sales, HR, and developers — with full access to the institutional knowledge you can access.

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
No OAuth app approval. No IT ticket. No staging environment. If you can log in, your agent can act. Clone the repo, point your agent at `setup.md`, and it handles the rest.

### Read vs read+write+act

Most AI tools — enterprise search platforms, knowledge bases, even ChatGPT — are **read-only**. They find information and surface it in a chat box. You then manually take that answer and do something with it.

10xProductivity is **read + write + act**. The agent doesn't just find the Jira ticket — it updates it. It doesn't just summarize the Slack thread — it posts the summary back. It doesn't just locate the bug — it opens the PR that fixes it.

The output isn't text in a box. The output is the thing done, in the right place, in the right tool.

This is a categorical difference. Any AI tool that only answers can be replaced by a better search engine. An agent that acts is a different class of capability entirely.

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

## Enterprise search: one question, every tool

Once your tools are connected, the built-in enterprise search workflow lets your agent query all of them simultaneously — Slack, Confluence, Jira, Linear, Notion, GitHub, and more — and synthesize a single answer.

**One prompt, every connected source:**

```
Search for everything related to the decision to deprecate the v1 API.
```

The agent fans out across every connected tool, pulls relevant results, and returns a synthesized answer with citations — no tab switching, no copy-paste, no hunting across systems.

**What it replaces:**
- Opening Slack, searching, scrolling, opening threads
- Switching to Confluence, searching again
- Checking Jira, checking GitHub PRs, checking Linear
- Mentally stitching together five partial answers

**When to use it:** Any time you're asking a question that might be answered in more than one place — "what was the decision on X", "who owns Y", "is there a doc on Z", "any context on this incident", "what did we decide about this feature".

To activate: `Read /path/to/10xProductivity/workflows/enterprise-search/enterprise-search.md`

---

## What's in this repo

**Agent-readable playbooks** for connecting your local agent to the tools you already use — with no limit on what those tools can be.

```
tool_connections/    ← pre-built recipes for common tools (e.g. Slack, GitHub, Jira)
  slack/
    setup.md         ← how to connect
    connection-sso.md

personal/            ← your own recipes (gitignored) — internal tools stay private, never committed
  {tool-name}/
    setup.md
    connection-{auth-method}.md

workflows/           ← pre-built workflows that compose multiple tool connections
  enterprise-search/
    enterprise-search.md  ← search across all your connected tools simultaneously in one query

add-new-tool.md      ← connect anything not in tool_connections/ — internal portals, custom systems, any tool with an API or browser interface

setup-python.md      ← detect OS, try winget/brew/apt then python.org if needed; Python 3.12 + venv + Playwright (no git — you already have this folder)
```

`tool_connections/` has pre-built recipes for tools most teams share. `personal/` is where your internal company tools live — same setup path, stays on your machine. Once connected, workflows like the built-in search let your agent query Slack, Confluence, Jira, and more in a single request.

**The pre-built list is just a head start.** `add-new-tool.md` is a playbook for connecting any tool that isn't there yet — internal portals, proprietary systems, niche SaaS, anything. If it has an API or a browser interface, your agent can use it.

---

## Quick start

1. **Install Cursor** (the editor your agent runs in): open **[cursor.com/download](https://cursor.com/download)**, download the installer for **Windows** or **macOS**, run it, and sign in or create an account when prompted.

```bash
git clone https://github.com/ZhixiangLuo/10xProductivity.git
cd 10xProductivity
```

Open the **`10xProductivity`** folder in Cursor (**File → Open Folder…**).

If you do not have **Python 3** yet (common on a fresh laptop), point your agent at **`setup-python.md`** first — it detects your system, tries **winget / Homebrew / apt** when present, otherwise guides a **python.org** install, then prepares `.venv` + Playwright. **No `git` in that playbook** — you already have this folder.

Then point your agent at the setup guide:

```
Read /path/to/10xProductivity/setup.md and set up my tool connections.
```

Your agent handles the rest — it will ask which tools you use and the URLs, get the credentials it needs, run SSO where required, and verify each connection works. Works for any tool: pre-built recipes for common tools, and an identical setup path for internal or custom tools.

---

## Who this is for

**It works for everyone — not just developers.**

The agent is the same for a CTO and a support rep. What differs is the content: the tools they connect, the skills they build, the workflows they automate. A developer writes a skill to triage GitHub issues. A sales rep writes one to pull CRM context before a call. An executive writes one to get a cross-tool status summary every morning.

Same setup. Same chat interface. Completely different leverage depending on what you do.

The comparison isn't "AI vs no AI." It's **AI vs hiring**. A new hire takes months to onboard, needs hand-holding, and costs $100k+/year. The agent is set up in a day, already knows all your tools, never forgets context, and works at any hour.

**Enterprise deployment model:**
- **IT** installs Cursor, connects shared tools once, sets company-wide rules and skills, runs onboarding workshops
- **Power users** (one or two per team) build the skills and workflows that matter for their team's work
- **Everyone** benefits — the whole team gets access to those skills without building anything themselves
- **Credentials stay personal** — each person's agent acts as them, sees only what they can see, with their name on every action

The skills and workflows a team builds accumulate over time. The longer it runs, the more capable it becomes. That's a compounding advantage no static tool can match.

---

## Who uses this repo and how

**User** — you want to connect your agent to tools you already use:
1. Clone the repo and point your agent at it: *"Read /path/to/10xProductivity/setup.md and set up my tool connections"*
2. Your agent asks which tools you use, handles credentials, runs SSO where needed, and verifies each connection
3. From that point your tools and the search workflow are available automatically at the start of every session — no MCP server, no plugin, no admin approval

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
