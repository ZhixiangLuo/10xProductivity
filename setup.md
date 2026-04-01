# Setup Guide

> **What this file is for:** Setting up any tool connection — whether a pre-built recipe exists or not. This is the single entry point: it routes to `verified_connections.md` (already set up), `personal/` (your own recipes), `tool_connections/` (pre-built community recipes), or `add-new-tool.md` (build from scratch) based on what already exists.

This file is for your agent. Point your agent here first:

> *"Read setup.md and set up my tool connections."*

---

## Agent UX principles — read this first

**Do as much as possible. Ask as little as possible. Ask non-technically.**

- Run every command yourself. Never paste a command and ask the user to run it.
- **Ask for a URL first.** For any tool, the best minimal input is a URL the user already has open (a ticket, a message link, a dashboard URL). It reveals the base URL, workspace, and regional variant — without requiring the user to know anything about auth.
- **Infer the auth method from the URL, then try it.** Check the tool's `setup.md` to determine the auth method. For SSO/browser-session tools, attempt Playwright immediately — no further questions needed. For API token tools, check `.env` first — the token may already be there.
- **Ask for credentials only if actually missing, and only for the specific thing that's missing.** Never ask vague questions like "do you have credentials?" Know what you need before you ask.
- When you must ask, phrase it in plain language — not in technical terms.
- As soon as you have what you need, do the work and verify it yourself. Tell the user what succeeded, not what they need to do next.
- **Always run tools from `personal/{tool-name}/`, not directly from `tool_connections/`.** On first setup, copy `tool_connections/{tool-name}/` → `personal/{tool-name}/` and work from the copy. This isolates your working connections from upstream repo changes — a `git pull` will never silently break a tool you depend on.
- **If a recipe fails, patch `personal/{tool-name}/` directly — never modify `tool_connections/`.** Then follow `contributing.md` to propose the fix upstream.

---

## Prerequisites

```bash
# Clone and create Python env
git clone https://github.com/yourusername/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium

# Create .env (empty — fill from each tool's setup.md as you connect)
touch .env
```

---

## Step 1: Ask the user which tools they use

Ask once, openly — don't limit the user to a preset list:

> *"Which tools do you use daily — for work or personal use? Include internal company tools, anything custom your team built, and any tool you want your agent to be able to use."*

To prompt recognition, you can offer examples — lead with internal tools, since those are often the most valuable:

> *Your internal tools matter most: deployment portals, incident trackers, internal knowledge bases, custom dashboards, HR systems — anything your company built or runs internally. Also: Confluence, Slack, Jira, GitHub, Microsoft Teams, Outlook, Grafana, PagerDuty, Google Drive, Datadog, and more. Pre-built recipes exist for common tools; internal tools follow the same setup path and stay private on your machine.*

Only set up what they actually use. Don't touch tools they don't have.

Any tool — whether it has a pre-built recipe, an existing personal recipe, or no recipe at all — is handled by the routing in Step 2.

---

## Step 2: Set up each tool

**`personal/` is the active working layer.** All tools are run from `personal/{tool-name}/` — whether the recipe was built from scratch or copied from `tool_connections/`. This means upstream changes to `tool_connections/` never silently break your working connections; you opt in to updates manually.

For each tool the user selected, follow this routing in order — stop at the first path that succeeds:

| # | Situation | Action |
|---|-----------|--------|
| 1 | Tool is already in the user's `verified_connections.md` | Reverify — run its verify snippet; if it passes, done for this tool |
| 2 | Tool has a recipe in `personal/{tool-name}/` | Load it and try; if it passes, done; if it fails, patch in `personal/{tool-name}/` |
| 3 | Tool has a recipe in `tool_connections/{tool-name}/` | Copy `tool_connections/{tool-name}/` → `personal/{tool-name}/` (exact copy), then load `personal/{tool-name}/setup.md` and follow it — never run directly from `tool_connections/`, never edit `tool_connections/` directly |
| 4 | Tool not found anywhere | Run `add-new-tool.md` — it builds a recipe in `personal/{tool-name}/` from scratch |

**Validation is mandatory on all paths.** Run the verify snippet and confirm it returns expected output before marking a tool as done.

**SSO tools need bootstrapping first.** For tools that use browser session auth (Slack, Grafana, Google Drive, etc.), credentials are not manually filled in — they are written to `.env` by `playwright_sso.py`. The verify snippet will fail with a missing key error until you run the SSO script at least once. Check the tool's `setup.md` for the exact command (usually `source .venv/bin/activate && python3 tool_connections/shared_utils/playwright_sso.py --tool-only`).

---

### Finding recipes (path 3)

There is no fixed list of supported tools — any tool with an API or browser interface can be connected. Pre-built community recipes live in `tool_connections/` (one subfolder per tool, each with its own `setup.md`). Your active recipes — copies from `tool_connections/`, internal tools, patched fixes, or anything you built — live in `personal/` (gitignored).

- Browse `personal/` first — your active copies live here
- Browse `tool_connections/` for pre-built recipes to copy from
- If neither has what you need → path 4: `add-new-tool.md`

---

## Step 3: Update verified_connections.md

**Only tools whose Verify command you actually ran and confirmed with real output belong here.**

After each tool passes verification, append its section to `verified_connections.md`. Write the **resolved** state — not the generic frontmatter. The entry must reflect what actually worked on this device, so the agent can use it immediately without re-reading the connection file or re-inferring the auth method.

```markdown
---

## {Tool Display Name} → `{path/to/connection-*.md}`

{description from frontmatter}
Instance: `{actual base URL — not a template, the real URL}`
Auth: {exact method and header format — e.g. "Bearer PAT — `Authorization: Bearer $TOKEN`"}
Active env: `ACTIVE_VAR_1`, `ACTIVE_VAR_2`  ← only vars that are set and used; omit placeholders
Refresh: {how and how often, if token is short-lived}  ← omit if long-lived
Note: {any critical gotcha that would cause silent failure}  ← omit if none
```

**Rules for each field:**
- **Instance** — the real URL the verify snippet hit (e.g. `https://jira2.workday.com`, not `https://jira.yourcompany.com`). Include prod vs dev if both exist.
- **Auth** — the method that actually passed verification. For tools with Cloud vs Server/DC variants (Jira, Confluence), name the variant explicitly. Never list both — only the one in use.
- **Active env** — only vars that are populated with real values. If a var is present in `.env` but is a placeholder (e.g. `you@yourcompany.com`), omit it and add a Note explaining it should be ignored.
- **Refresh** — include for any token with a lifetime under ~24h (SSO sessions, Coveo JWTs, xoxc). Omit for long-lived API tokens and PATs.
- **Note** — include only if there is a silent failure risk: a placeholder var that must be ignored, a CLI that must be used instead of REST, a required prerequisite (VPN, `/etc/hosts`, Zscaler), or a common misidentification (e.g. PHX-XXXXX vs PHOENIX-XXXX).

The preamble (frontmatter + intro block) comes from `verified_connections.example.md` — copy it on first run, then only append sections for each new tool.

Then summarize for the user what connected and what was skipped.

**Now load `verified_connections.md` immediately.** It is your capability index for this session.

---

## Step 3b: Test the search workflow

Read `workflows/search/search.md` and run a test search across all connected tools using a simple query the user would actually care about — e.g. the name of a project, team, or recent topic they mentioned. This confirms the tools work end-to-end together, not just in isolation.

If any tool fails during the search (wrong auth format, missing env var, etc.), patch it now before moving on.

---

## Step 4: Create the agent skill

This step makes your tools available automatically in every future session — no manual loading required.

Determine the absolute path to this repo:

```bash
pwd
# → /absolute/path/to/10xProductivity
```

Create the skill file at `~/.cursor/skills/tool-connections/SKILL.md` with that path filled in:

```markdown
---
name: tool-connections
description: Loads connected tools and enables cross-tool search. Use at the start of any session where the user may want to use connected tools (Slack, Confluence, Jira, Linear, Notion, GitHub, etc.), when the user asks to search for something, or when the user mentions any tool by name.
source: https://github.com/zhixiangluo/10xProductivity
---

# Tool Connections

> Generated by [10xProductivity](https://github.com/zhixiangluo/10xProductivity). To connect new tools or add integrations, see that repo.

Repo: `/absolute/path/to/10xProductivity`

## Session start

Read these two files immediately:

1. `/absolute/path/to/10xProductivity/verified_connections.md` — active tool connections and capability index
2. `/absolute/path/to/10xProductivity/workflows/enterprise-search/enterprise-search.md` — cross-tool search workflow

## Routing

| Situation | Action |
|-----------|--------|
| User asks to search for something | Follow `workflows/enterprise-search/enterprise-search.md` (already loaded) |
| User wants to use a specific tool | Read its connection file — path is listed in `verified_connections.md` |
| A tool is mentioned but not in `verified_connections.md` | Read `setup.md` to connect it |
| A tool has no recipe in `tool_connections/` | Read `add-new-tool.md` to build one |
```

Replace every occurrence of `/absolute/path/to/10xProductivity` with the actual path from `pwd`.

Create the directory and write the file:

```bash
mkdir -p ~/.cursor/skills/tool-connections
# then write the file above to ~/.cursor/skills/tool-connections/SKILL.md
```

Once written, the skill is active. Cursor and Claude Code will load `verified_connections.md` and the search workflow automatically at the start of every session.

---

## Contributing fixes upstream

If you patched a `tool_connections/` recipe in `personal/` and it works, the fix may help others. See `contributing.md` ("Fixes and improvements") to propose it upstream.
