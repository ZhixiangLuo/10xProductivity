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
- **If a recipe fails, do not modify `tool_connections/` directly.** Copy the relevant files to `personal/{tool-name}/`, patch and verify there, then follow `contributing.md` to propose the fix upstream. Never silently change a shared recipe as a side effect of setup.

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

To prompt recognition, you can offer examples of tools with pre-built recipes in `tool_connections/`:

> *Examples with pre-built recipes: Confluence, Slack, Jira, GitHub, Microsoft Teams, Outlook, Grafana, PagerDuty, Google Drive, Datadog, Artifactory, Bitbucket Server, Jenkins, Backstage — but you're not limited to these.*

Only set up what they actually use. Don't touch tools they don't have.

Any tool — whether it has a pre-built recipe, an existing personal recipe, or no recipe at all — is handled by the routing in Step 2.

---

## Step 2: Set up each tool

For each tool the user selected, follow this routing in order — stop at the first path that succeeds:

| # | Situation | Action |
|---|-----------|--------|
| 1 | Tool is already in the user's `verified_connections.md` | Reverify — run its verify snippet; if it passes, done for this tool |
| 2 | Tool has a recipe in `personal/{tool-name}/` | Load it and try; if it passes, done; if it fails, patch in `personal/{tool-name}/` |
| 3 | Tool has a recipe in `tool_connections/{tool-name}/` | Read `tool_connections/{tool}/setup.md` and follow it; if it fails, copy to `personal/{tool-name}/` and patch there — never edit `tool_connections/` directly |
| 4 | Tool not found anywhere | Run `add-new-tool.md` — it builds a recipe in `personal/{tool-name}/` from scratch |

**Validation is mandatory on all paths.** Run the verify snippet and confirm it returns expected output before marking a tool as done.

---

### Finding recipes (path 3)

There is no fixed list of supported tools — any tool with an API or browser interface can be connected. Pre-built community recipes live in `tool_connections/` (one subfolder per tool, each with its own `setup.md`). Your own recipes — for internal tools, patched fixes, or anything not in `tool_connections/` — live in `personal/` (gitignored).

- Browse `tool_connections/` for pre-built recipes
- Browse `personal/` for your own recipes
- If neither has what you need → path 4: `add-new-tool.md`

---

## Step 3: Generate verified_connections.md

**Only tools whose Verify command you actually ran and confirmed with real output belong here.**

Edit `VERIFIED_NAMES` at the top of `utils/generate_verified.py` to include the tools you verified, then run it from the repo root:

```bash
python3 utils/generate_verified.py
```

Then summarize for the user what connected and what was skipped.

**Now load `verified_connections.md` immediately.** It is your capability index for this session.

---

## Contributing fixes upstream

If you patched a `tool_connections/` recipe in `personal/` and it works, the fix may help others. See `contributing.md` ("Fixes and improvements") to propose it upstream.
