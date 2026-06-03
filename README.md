# 10xProductivity — Personal AI Assistant for Work, Built on Coding Agents

**A human-AI interaction platform for building a personal AI assistant for work on top of the coding agents and tools you already use.**

You connect your tools, coach your agent through real work, and gradually turn repeated patterns into reusable skills and trusted workflows.

[![GitHub Stars](https://img.shields.io/github/stars/ZhixiangLuo/10xProductivity?style=social)](https://github.com/ZhixiangLuo/10xProductivity/stargazers)

If this saves you time, consider giving it a star. It helps others discover the project.

## Star History

<a href="https://www.star-history.com/?repos=ZhixiangLuo%2F10xProductivity&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ZhixiangLuo/10xProductivity&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ZhixiangLuo/10xProductivity&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ZhixiangLuo/10xProductivity&type=date&legend=top-left" />
 </picture>
</a>

## The Idea

Coding agents are no longer just coding assistants. Cursor, Claude Code, Codex, Copilot, and similar tools can read files, run scripts, call APIs, use browsers, and work across your local environment.

10xProductivity turns that agent into a personal work assistant.

The shift is not "let an AI run autonomously." The shift is **human-AI interaction**:

- You delegate work in natural language.
- The agent uses your connected tools to search, draft, triage, update, and automate.
- You supervise, correct, and coach when the work is new or important.
- Repeated patterns become reusable agent skills.
- Working sessions become persistent memory.
- Mistakes and tool use become better skills.
- Trusted skills become workflows you can launch from chat or cron.

Tool connections are still the foundation, but they are no longer the whole product. They are the first layer of a broader personal AI assistant for work stack.

## Available Today / Coming Next

| Layer | Status | What it means |
|---|---|---|
| Tool connections | Available today | Pre-built recipes for 25+ tools, plus a playbook for connecting any internal or custom tool |
| Enterprise search | Available today | Search across connected tools like Slack, Confluence, Jira, GitHub, Linear, Notion, and more |
| Agent skills | Available today | Packaged Cursor and Claude Code skills for tool setup, search, workflow creation, UI discovery, and more |
| Reusable workflows | Early | A few workflows exist today; the next step is turning more repeated work into durable workflows |
| Slack interaction | Coming next | Slack becomes the async entry point for trusted jobs and threaded human-AI interaction |
| Scheduled learning and jobs | Coming next | Trusted workflows, memory build, reflection, and capability learning can run on a schedule |

## How It Works

```
Human
  ↓
Slack thread                    Laptop coding-agent session
  ↓                                      ↓
Thin routing layer              Individual skill or workflow
  ↓                                      ↓
Agent skills and workflows      Connected tools directly
  ↓                                      ↓
Connected tools                         |
  ↓                                      ↓
Work done in Slack, Jira, GitHub, docs, calendar, CRM, internal portals, and more
```

### 1. Connect Your Tools

Your agent needs access to the same tools you already use: Slack, Jira, GitHub, Confluence, Google Drive, Outlook, Salesforce, internal portals, or anything else with an API, CLI, browser surface, or local files.

10xProductivity provides agent-readable setup guides in [`tool_connections/`](tool_connections/). The core principle is still zero new infrastructure: your local coding agent acts as you, using your existing access.

For the detailed connection philosophy, see [`tool_connections/README.md`](tool_connections/README.md).

### 2. Coach Through Real Work

The assistant learns by doing real work with you.

When a workflow is new, you supervise from the laptop in Cursor, Claude Code, Codex, or another coding-agent session. You correct mistakes, explain judgment calls, and shape the process. That coaching becomes durable instructions.

### 3. Capture Reusable Agent Skills

A skill is more than an API recipe. It teaches the agent how to do a kind of work:

- Search across tools for context
- Triage a Jira sprint
- Summarize an incident
- Draft a PR description
- Prepare a customer call
- Write a standup update
- Review open follow-ups

Over time, your skill library becomes the operating manual for your personal AI assistant for work.

### 4. Run Trusted Workflows

Once a workflow has been coached and proven, you can run it with less supervision:

- From a Slack thread
- From a scheduled cron job
- From a repeatable workflow prompt
- From your laptop when you want richer interaction

Automation is reserved for workflows you trust. Everything else stays in the human-AI interaction loop.

### 5. Learn Continuously

The assistant should get better the more you use it.

One scheduled loop reviews recent work: what the agent tried, where it got stuck, which tools and skills it used, what the human corrected, and what patterns repeated. That loop turns working sessions into persistent memory and improves the skills that caused friction.

Another loop broadens capability. When the assistant needs to learn a new tool, workflow, domain, or work surface, it follows a guided, battle-tested learning skill with verifiable progress. Sometimes that learning is human-coached; sometimes the agent can learn independently through a structured skill, as long as it can test the result and produce evidence that the capability works. After enough evidence from real use, the new capability can be captured as a reusable skill and eventually become trusted.

This gives the system self-awareness: it should know what it can do reliably, what it has only tried a few times, what it can plausibly learn, and where it still needs human supervision. Capability is evidence-based, not aspirational.

## Interaction Surfaces

**Slack** is the async entry point. It is a natural place to delegate lightweight or trusted work, receive updates, answer questions, and keep a thread as the task conversation.

Slack is where the thin routing layer matters: incoming messages need to be classified, routed to the right skill or workflow, and replied to in the right thread.

**Laptop sessions** are the coaching surface. This is where you supervise complex work, correct the agent, refine skills, and teach the assistant new workflows. On the laptop, you do not need a routing layer first; you can directly invoke the individual skill, workflow, or tool connection you want to work on.

The product is designed around both: quick delegation when the workflow is familiar, active coaching when the workflow is still being learned.

## What's In This Repo

```text
tool_connections/        Pre-built recipes for connecting tools to your agent
workflows/               Multi-tool workflows built on top of connections
.cursor/skills/          Cursor agent skills packaged with the repo
.claude/skills/          Claude Code agent skills packaged with the repo
staging/                 Community contributions under review
setup.md                 Main setup path for connecting tools
add-new-tool.md          Playbook for connecting tools not yet in the repo
setup-python.md          Python and Playwright setup helper
```

Private runtime state lives outside the public repo by default:

```text
~/.10xProductivity/
  .env                    Tokens, cookies, and private config
  personal/               Your active private tool recipes and patched copies
  verified_connections.md Device-specific connection index
```

Set `TENX_PRIVATE_DIR` if you want a different private directory. The repo keeps hooks and `.gitignore` as safety nets, but credentials and browser/session state should not live under the repo tree.

Migration note: older local instructions may point at `/path/to/10xProductivity/.env`, `/path/to/10xProductivity/personal/`, or `/path/to/10xProductivity/verified_connections.md`. Those now map to `TENX_PRIVATE_DIR/.env`, `TENX_PRIVATE_DIR/personal/`, and `TENX_PRIVATE_DIR/verified_connections.md`. The repo `personal/` folder is only a placeholder with this reminder.

The current repo is strongest at the connection layer. The workflow layer exists, but is still early. The next product direction is to build upward from connections into reusable workflows, agent skills, Slack interaction, and trusted scheduled jobs.

## Work Surfaces

This is not a connector-count competition. The point is to cover the surfaces where work actually happens, then teach your agent how to move across them.

| Work surface | Example tools | What this unlocks in real work |
|---|---|---|
| Team communication | [Slack](tool_connections/slack/setup.md), [Microsoft Teams](tool_connections/microsoft-teams/setup.md), [Outlook](tool_connections/outlook/setup.md), etc. | Summarize threads, find decisions, draft replies, prepare for meetings, and keep follow-ups from disappearing |
| Work tracking | [Jira](tool_connections/jira/setup.md), [Linear](tool_connections/linear/setup.md), etc. | Triage tickets, spot stale work, draft updates, connect roadmap items to code, docs, and conversations |
| Code and delivery | [GitHub](tool_connections/github/setup.md), [Bitbucket Server](tool_connections/bitbucket-server/setup.md), [Jenkins](tool_connections/jenkins/setup.md), [Artifactory](tool_connections/artifactory/setup.md), etc. | Review PR context, investigate build failures, trace releases, and connect code changes back to tickets and incidents |
| Knowledge and documents | [Confluence](tool_connections/confluence/setup.md), [Google Drive](tool_connections/google-drive/setup.md), [SharePoint / OneDrive](tool_connections/sharepoint-onedrive/setup.md), [Notion](tool_connections/notion/setup.md), [OneNote](tool_connections/onenote/setup.md), etc. | Find the source of truth, compare stale docs with current discussions, and turn scattered context into usable briefs |
| Web and AI search | [Google AI Mode](tool_connections/google-ai-mode/setup.md) | Real-time web research with AI-synthesized answers and multi-turn follow-up — your agent can search the live web, not just its training data |
| Operations and observability | [PagerDuty](tool_connections/pagerduty/setup.md), [Grafana](tool_connections/grafana/setup.md), [Datadog](tool_connections/datadog/setup.md), etc. | Prepare incident context, connect alerts to owners and tickets, and summarize operational follow-ups |
| Business and collaboration | [Salesforce](tool_connections/salesforce/setup.md), [Figma](tool_connections/figma/setup.md), [Miro](tool_connections/miro/setup.md), etc. | Prep customer calls, inspect design context, and summarize planning boards |

Internal portals and custom company tools matter just as much as commercial SaaS. If a tool has an API, CLI, browser interface, or local files, use [`add-new-tool.md`](add-new-tool.md) to teach your agent how to use it privately.

## Agent Skills and Workflows

Agent skills sit above raw tool connections. They teach your coding agent how to do work, not just how to call an API.

Packaged skills currently cover [tool setup](.cursor/skills/tool-connector/SKILL.md), [enterprise search](.cursor/skills/enterprise-search/SKILL.md), [workflow creation](.cursor/skills/create-workflow/SKILL.md), [UI surface discovery](.cursor/skills/discover-ui-surface/SKILL.md), and [colleague distillation](.cursor/skills/colleague-distillation/SKILL.md).

## Quick Start

1. Install a coding agent such as [Cursor](https://cursor.com/download), Claude Code, Codex, or another agent you trust.

2. Clone and open this repo:

```bash
git clone https://github.com/ZhixiangLuo/10xProductivity.git
cd 10xProductivity
```

3. If needed, set up Python and Playwright:

```text
Read setup-python.md and prepare this repo.
```

4. Ask your agent to set up your personal AI assistant for work. The first step is connecting your tools:

```text
Read setup.md and set up my personal AI assistant for work.
```

5. Try a first workflow:

```text
Read workflows/enterprise-search/enterprise-search.md and search across my connected tools for <topic>.
```

From there, coach the agent through work you actually do. When a pattern repeats, capture it as a skill or workflow.

## Example Workflows and Prompts

**Available today: enterprise search**

```text
Search for everything related to the decision to deprecate the v1 API.
```

The agent searches across connected tools, synthesizes the answer, and links back to source material.

**Available today: real-time web research**

```text
Research the current state of WebAssembly support across major browsers
and summarize what changed in the last 6 months.
```

The agent queries Google AI Mode for AI-synthesized answers grounded in live web sources, with multi-turn follow-up for deeper investigation. No API key — sign in to Google once.

**Coaching example: sprint triage**

```text
Review my Jira sprint, identify stale tickets, and draft follow-up comments.
```

The agent can learn this from connected Jira, docs, and PRs. Once the pattern is reliable, capture it as a workflow or skill.

**Coaching example: morning brief**

```text
Summarize what changed since yesterday across Slack, Jira, GitHub, and my calendar.
```

Once trusted, this can become a scheduled workflow.

## Who This Is For

10xProductivity is for people who already use a coding agent and want it to become useful outside the code editor:

- Developers who want one agent to work across code, tickets, docs, and chat
- Engineering managers who want cross-tool status and follow-up automation
- Product managers, support engineers, analysts, sales teams, and operators who live across many tools
- Power users who want to coach their own personal AI assistant for work instead of waiting for a centralized platform rollout

The same stack works differently for each person because the tools, skills, and trusted workflows are personal.

## Project Direction

10xProductivity started as the tool connection layer for coding agents. It is evolving into an open-source personal AI assistant for work stack:

1. **Tool connections** — let the agent use the tools you already use.
2. **Workflows** — compose connections into repeatable multi-step jobs.
3. **Agent skills** — teach the agent how you want work done.
4. **Human-AI interaction** — delegate from Slack, coach from the laptop.
5. **Learning and memory** — turn sessions, corrections, tool use, and mistakes into persistent improvements.
6. **Self-awareness** — track capabilities and limitations based on evidence from real use.
7. **Trusted automation** — run proven workflows from chat or cron.

The goal is not to replace Cursor, Claude Code, Codex, or Copilot. The goal is to give those approved coding agents the missing layer: tool access, reusable skills, workflows, and a coaching loop that turns them into personal AI assistants for work.

## Contributing

Contributions are welcome for:

- New tool connections
- New auth or deployment variants
- Fixes to existing setup guides
- Useful workflows built on connected tools
- Agent skills that teach repeatable work patterns

See [`contributing.md`](contributing.md) for the full process. The core rule for tool connections is: **run before you write.** Every snippet should be something you executed and saw succeed.

## Legal

Some workflows in this repo automate actions on external platforms. Platform automation may violate Terms of Service. Read [`LEGAL_NOTICE.md`](LEGAL_NOTICE.md) before running automation scripts.

## License

MIT
