# 10xProductivity

**A human-AI interaction platform for building a personal assistant on top of the coding agents and tools you already use.**

You connect your tools, coach your agent through real work, and gradually turn repeated patterns into reusable skills and trusted workflows.

[![GitHub Stars](https://img.shields.io/github/stars/ZhixiangLuo/10xProductivity?style=social)](https://github.com/ZhixiangLuo/10xProductivity/stargazers)

If this saves you time, consider giving it a star. It helps others discover the project.

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

Tool connections are still the foundation, but they are no longer the whole product. They are the first layer of a broader personal assistant stack.

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

Over time, your skill library becomes the operating manual for your personal assistant.

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
personal/                Your private, gitignored local connections and workflows
setup.md                 Main setup path for connecting tools
add-new-tool.md          Playbook for connecting tools not yet in the repo
setup-python.md          Python and Playwright setup helper
```

The current repo is strongest at the connection layer. The workflow layer exists, but is still early. The next product direction is to build upward from connections into reusable workflows, agent skills, Slack interaction, and trusted scheduled jobs.

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

4. Ask your agent to connect your tools:

```text
Read setup.md and set up my tool connections.
```

5. Try a first workflow:

```text
Read workflows/enterprise-search/enterprise-search.md and search across my connected tools for <topic>.
```

From there, coach the agent through work you actually do. When a pattern repeats, capture it as a skill or workflow.

## Example Workflows

**Enterprise search**

```text
Search for everything related to the decision to deprecate the v1 API.
```

The agent searches across connected tools, synthesizes the answer, and links back to source material.

**Sprint triage**

```text
Review my Jira sprint, identify stale tickets, and draft follow-up comments.
```

The agent reads Jira, checks related docs or PRs, and prepares updates for your review.

**Morning brief**

```text
Summarize what changed since yesterday across Slack, Jira, GitHub, and my calendar.
```

Once trusted, this becomes a scheduled workflow.

## Who This Is For

10xProductivity is for people who already use a coding agent and want it to become useful outside the code editor:

- Developers who want one agent to work across code, tickets, docs, and chat
- Engineering managers who want cross-tool status and follow-up automation
- Product managers, support engineers, analysts, sales teams, and operators who live across many tools
- Power users who want to coach their own personal assistant instead of waiting for a centralized platform rollout

The same stack works differently for each person because the tools, skills, and trusted workflows are personal.

## Project Direction

10xProductivity started as the tool connection layer for coding agents. It is evolving into an open-source personal assistant stack:

1. **Tool connections** — let the agent use the tools you already use.
2. **Workflows** — compose connections into repeatable multi-step jobs.
3. **Agent skills** — teach the agent how you want work done.
4. **Human-AI interaction** — delegate from Slack, coach from the laptop.
5. **Learning and memory** — turn sessions, corrections, tool use, and mistakes into persistent improvements.
6. **Self-awareness** — track capabilities and limitations based on evidence from real use.
7. **Trusted automation** — run proven workflows from chat or cron.

The goal is not to replace Cursor, Claude Code, Codex, or Copilot. The goal is to give those approved coding agents the missing layer: tool access, reusable skills, workflows, and a coaching loop that turns them into personal assistants.

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
