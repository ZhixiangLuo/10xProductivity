---
name: tool-connector
description: Connect any tool you use at work to your agent — including internal company tools, custom-built systems, deployment portals, incident trackers, internal knowledge bases, HR systems, and commercial tools like Slack, Confluence, Jira, Linear, GitHub, Outlook, Datadog, and PagerDuty. Use when the user wants to set up a tool connection, connect an internal or custom-built tool, or add a new tool integration from scratch.
source: https://github.com/zhixiangluo/10xProductivity
author: zhixiangluo
---

# Tool Connector — Connect Any Work Tool to Your Agent

> **Requires the repo cloned locally.** Check if it's already present (`ls setup.md`), then read `setup.md` — that is the full entry point. The sections below summarize the approach for reference.

Full methodology and pre-built recipes: https://github.com/zhixiangluo/10xProductivity

## Internal tools are first-class citizens

Internal and custom-built tools are often the most valuable to connect — deployment portals, incident trackers, internal knowledge bases, custom dashboards, HR systems, anything your company built or runs. They follow the exact same setup path as commercial tools and stay private in `personal/` (gitignored, never committed).

If a tool has an API or a web UI, it can be connected.

## Core principles

- **Ask for a URL first, not credentials** — a URL the user has open reveals the base URL, workspace, and regional variant without requiring them to know anything about auth
- **Run every command yourself** — never paste a command and ask the user to run it
- **Validate with real output before marking anything done** — no illustrative output, no copy-paste from docs
- **Zero friction** — never require the user to create an OAuth app, register redirect URIs, or configure anything outside of this flow

## Routing

| Situation | Action |
|-----------|--------|
| Tool already in `verified_connections.md` | Reverify — run its verify snippet; if it passes, done |
| Tool has a recipe in `personal/{tool}/` | Load it and try; patch in `personal/` if it fails |
| Tool has a recipe in `tool_connections/{tool}/` | Read that tool's `setup.md` and follow it |
| Tool not found anywhere | Follow `add-new-tool.md` to build a recipe from scratch |

Never edit `tool_connections/` directly — copy to `personal/{tool}/` and patch there.

## Auth priority order

| Priority | Method | User friction |
|----------|--------|---------------|
| 1 | API token | ~30s — generate in tool settings |
| 2 | Browser session (SSO, cached) | Run once — session cached for days/weeks |
| 3 | Browser session (per operation) | Playwright on every call — only if no API exists |
| 4 | Username + password | Legacy tools only |
| ✗ | OAuth requiring user to create their own app | Never — too much friction |

## Pre-built recipes available

Slack, Confluence, Jira, Linear, GitHub, Microsoft Teams, Outlook, Google Drive, Datadog, Grafana, PagerDuty, Jenkins, Backstage, Bitbucket Server, Artifactory.

Internal and custom tools follow the same path — they stay private in `personal/` (gitignored).

## Getting started

First, check if you already have the repo:

```bash
ls setup.md 2>/dev/null && echo "repo present" || echo "need to clone"
```

**Repo present** → read `setup.md` now — it is the full entry point.

**Need to clone** →

```bash
git clone https://github.com/zhixiangluo/10xProductivity.git
cd 10xProductivity
```

Then read `setup.md`. It routes to pre-built recipes, your own recipes, and `add-new-tool.md` for anything new.
