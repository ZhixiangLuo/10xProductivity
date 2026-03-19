# Setup Guide

> **What this file is for:** The tool already has a recipe in `tool_connections/`. You are connecting your own instance of it — putting credentials in `.env` and verifying they work.
>
> **Wrong file?** If the tool doesn't exist in `tool_connections/` yet, use `add-new-tool.md` instead — that one builds the recipe from scratch.

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

**Minimum user input by tool:**

| Tool | What to ask for | Auth method |
|------|----------------|-------------|
| **Slack** | Any Slack message link | SSO → run `tool_connections/slack/sso.py` |
| **Jira** | Any Jira ticket URL + API token + email | API token (Basic auth) |
| **GitHub** | PAT (+ repo URL if GHE) | API token (Bearer) |
| **Confluence** | Any Confluence page URL + API token + email | API token (Basic auth) |
| **Grafana** | Grafana URL | SSO → run `tool_connections/grafana/sso.py` |
| **PagerDuty** | API key | API token |
| **Microsoft Teams** | Any Teams link | SSO → run `tool_connections/microsoft-teams/sso.py` |
| **Outlook / M365** | Any Outlook URL | SSO → run `tool_connections/outlook/sso.py` |
| **Outlook.com** | Any Outlook URL | Token capture → run `tool_connections/outlook/get_outlook_token.py` |
| **Google Drive** | Nothing | Browser session → run `tool_connections/google-drive/sso.py` |
| **Notion** | API token from notion.so/my-integrations | API token (Bearer) — then grant page access via Settings → Integrations → Edit → Content access |
| **Datadog** | Datadog URL + API key + App key | API key |

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

Ask once, simply:

> *"Which of these tools does your team use?"*
> - Confluence (internal wiki / docs)
> - Slack
> - Jira
> - GitHub (or GitHub Enterprise)
> - Microsoft Teams ("Share any Teams link — I'll detect personal vs enterprise")
> - Outlook ("Share any Outlook link — I'll detect Outlook.com vs Microsoft 365")
> - Grafana
> - PagerDuty / OpsGenie
> - Google Drive / Google Workspace
> - Datadog / Splunk
> - Artifactory
> - Bitbucket Server
> - Jenkins
> - Backstage
> - Other (describe — check `personal/` for existing recipes, or run `add-new-tool.md` to build one)

Only set up what they actually use. Don't touch tools they don't have.

**Tool not in the list above?** Check `personal/` first — if a recipe exists there, use it. If not, run `add-new-tool.md` to build one from scratch (it will write to `personal/`).

---

## Step 2: Set up tools in priority order

**Validation is mandatory.** For every tool, run the verify snippet and confirm it returns expected output before moving on.

Start with **Tier 1** — these make everything else easier.

### Tier 1 — Knowledge & Context

| Tool | Setup file |
|------|-----------|
| Confluence | `tool_connections/confluence/setup.md` |
| Slack | `tool_connections/slack/setup.md` |
| Jira | `tool_connections/jira/setup.md` |
| GitHub | `tool_connections/github/setup.md` |
| Microsoft Teams | `tool_connections/microsoft-teams/setup.md` |
| Outlook | `tool_connections/outlook/setup.md` |

### Tier 2 — Observability & Operations

| Tool | Setup file |
|------|-----------|
| Grafana | `tool_connections/grafana/setup.md` |
| PagerDuty | `tool_connections/pagerduty/setup.md` |
| Datadog | `tool_connections/datadog/setup.md` |

### Tier 3 — File & Document Access

| Tool | Setup file |
|------|-----------|
| Google Drive | `tool_connections/google-drive/setup.md` |

### Tier 4 — Dev Infrastructure

| Tool | Setup file |
|------|-----------|
| Artifactory | `tool_connections/artifactory/setup.md` |
| Bitbucket Server | `tool_connections/bitbucket-server/setup.md` |
| Jenkins | `tool_connections/jenkins/setup.md` |
| Backstage | `tool_connections/backstage/setup.md` |

For each tool: read its `setup.md`, follow the steps, run the verify snippet, confirm it passes.

---

## Step 3: Generate verified_connections.md

**Only tools whose Verify command you actually ran and confirmed with real output belong here.**

For each tool set up in Step 2, you ran a Verify snippet and saw expected output. Collect only those tool names into `VERIFIED_NAMES` below, then run the script to generate `verified_connections.md`.

Tools can come from `tool_connections/` (core) or `personal/` (your own) — include them all here regardless of origin.

```python
import re, os
from pathlib import Path

# EDIT THIS LIST: only tools whose Verify command you ran and confirmed
# Include tools from tool_connections/ AND personal/ — origin doesn't matter
VERIFIED_NAMES = [
    # Core tools (tool_connections/):
    # "confluence",
    # "slack",
    # "jira",
    # "github",
    # "grafana",
    # "pagerduty",
    # "google-drive",
    # "microsoft-teams",
    # "outlook",
    # "datadog",
    # "artifactory",
    # "bitbucket-server",
    # "jenkins",
    # "backstage",
    # Personal tools (personal/):
    # "my-internal-tool",
]

# Determine which tools are verified
verified_names = VERIFIED_NAMES

# Build verified_connections.md by filtering the example to verified tools only
example = Path("verified_connections.example.md").read_text()
chunks = re.split(r"\n---\n", example)

def tool_slug(name):
    return name.lower().replace(" ", "-").replace("/", "-")

def is_verified_section(chunk):
    m = re.match(r"^##\s+(\S+)", chunk.strip())
    if not m:
        return False
    slug = tool_slug(m.group(1))
    return any(v in slug or slug in v for v in verified_names)

def filter_table_rows(text):
    lines = text.splitlines()
    out = []
    in_table = False
    for line in lines:
        if "| Tool" in line or line.startswith("|---"):
            in_table = True
            out.append(line)
        elif in_table and line.startswith("|"):
            tool_m = re.search(r"\*\*(.+?)\*\*", line)
            if tool_m:
                slug = tool_slug(tool_m.group(1))
                if any(v in slug or slug in v for v in verified_names):
                    out.append(line)
        else:
            in_table = False
            out.append(line)
    return "\n".join(out)

header_chunks, section_chunks = [], []
for chunk in chunks:
    (section_chunks if re.match(r"^##\s+\w", chunk.strip()) else header_chunks).append(chunk)

filtered_header = "\n---\n".join(
    filter_table_rows(c) if "| Tool" in c else c for c in header_chunks
)
verified_sections = [c for c in section_chunks if is_verified_section(c)]

output = filtered_header
if verified_sections:
    output += "\n---\n" + "\n---\n".join(verified_sections)

tool_list = ", ".join(verified_names) if verified_names else "none"
output = re.sub(
    r"(description: ).*?(\n)",
    lambda m_: m_.group(1) + f"Your active tool connections — verified and ready. Covers: {tool_list}. Load at session start." + m_.group(2),
    output, count=1
)
new_preamble = (
    "**Keep this file loaded for the entire session.** These tools are verified and ready — "
    "use them proactively in any task across any codebase.\n\n"
    "Individual tool files have full connection details — load them on demand.\n\n"
    "**Refresh short-lived tokens (~8h):** run the tool's `sso.py` "
    "(e.g. `source .venv/bin/activate && python3 tool_connections/slack/sso.py`)"
)
output = re.sub(
    r"\*\*This is the example file\.\*\*.*?(?=\n---\n|\n## )",
    new_preamble,
    output,
    flags=re.DOTALL
)

Path("verified_connections.md").write_text(output)
print(f"verified_connections.md written. Active tools: {verified_names}")
```

Then summarize for the user what connected and what was skipped.

**Now load `verified_connections.md` immediately.** It is your capability index for this session.

---

## Refreshing short-lived tokens

| Tool | Command | TTL |
|------|---------|-----|
| Slack | `python3 tool_connections/slack/sso.py` | ~8h |
| Grafana | `python3 tool_connections/grafana/sso.py` | ~8h |
| Outlook / M365 | `python3 tool_connections/outlook/sso.py` | ~1h |
| Outlook.com | `python3 tool_connections/outlook/get_outlook_token.py` | ~1h |
| Teams (personal) | `python3 tool_connections/microsoft-teams/sso.py` | ~24h |
| Google Drive | `python3 tool_connections/google-drive/sso.py` | days–weeks |

Always `source .venv/bin/activate` first.

---

## If something broke during setup

**Do not edit `tool_connections/` directly.** That folder is shared — changes made here affect everyone.

Instead:
1. Copy `tool_connections/{tool}/` → `personal/{tool}/`
2. Patch and verify it there
3. Use the patched `personal/{tool}/` recipe for your session
4. Follow `contributing.md` ("Fixes and improvements") to propose the fix upstream

| What broke | Where to look for the cause |
|------------|-----------------------------|
| Wrong setup instructions | `tool_connections/{tool}/setup.md` (read to understand, patch in `personal/`) |
| Wrong API snippet | `tool_connections/{tool}/connection-*.md` (read to understand, patch in `personal/`) |
| SSO script failure | `tool_connections/{tool}/sso.py` (read to understand, patch in `personal/`) |

See `add-new-tool.md` for creating connections for tools that don't exist in the repo yet.
