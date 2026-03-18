# Setup Guide

This file is for your agent. Point your agent here first:

> *"Read SETUP.md and set up my tool connections."*

---

## Agent UX principles — read this first

**Do as much as possible. Ask as little as possible. Ask non-technically.**

- Run every command yourself. Never paste a command and ask the user to run it.
- Infer everything you can before asking. A Slack message URL tells you the workspace URL. A Jira ticket URL tells you the base URL. Don't ask for what you can derive.
- When you must ask, ask for the one thing only the user can provide (a credential, a URL they're logged into), and phrase it in plain language — not in technical terms.
- As soon as you have what you need, do the work and verify it yourself. Tell the user what succeeded, not what they need to do next.

**Minimum user input by tool:**

| Tool | What to ask for | What you can infer / automate |
|------|----------------|-------------------------------|
| **Slack** | "Send me any Slack message link from your workspace" — that's it | Workspace URL from the link; run `playwright_sso.py --slack-only` to capture tokens automatically |
| **Jira** | "Share any Jira ticket URL" + "Paste your API token (Jira → Profile → API Tokens)" + "Your Atlassian account email" | Base URL from the ticket link; auth is Basic base64(email:token) |
| **GitHub** | "Paste your GitHub personal access token (Settings → Developer settings → Personal access tokens)" | Base URL is `https://api.github.com` unless they share a GHE URL |
| **Confluence** | "Share any Confluence page URL" + "Paste your API token (Confluence → Profile → Personal Access Tokens)" | Base URL from the page link |
| **Grafana** | "Share your Grafana URL" | Run `playwright_sso.py --grafana-only` to capture session automatically |
| **PagerDuty** | "Paste your PagerDuty API key (My Profile → User Settings → API Access)" | Base URL is always `https://api.pagerduty.com` |
| **Microsoft Teams Free** | Nothing — just run the script | Run `playwright_sso.py --teams-only`; browser opens, user logs in once with Microsoft personal account |
| **Outlook / Microsoft 365** | Nothing — just run the script | Run `playwright_sso.py --outlook-only`; browser opens, Azure AD SSO auto-completes on managed machines |
| **Google Drive** | Nothing — just run the script | Run `playwright_sso.py --gdrive-only`; browser opens, user logs in once |

---

## Prerequisites

```bash
# Clone and create Python env
git clone https://github.com/yourusername/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium

# Copy env template
cp env.sample .env
```

---

## Step 1: Ask the user which tools they use

Ask once, simply:

> *"Which of these tools does your team use?"*
> - Confluence (internal wiki / docs)
> - Slack
> - Jira
> - GitHub (or GitHub Enterprise)
> - Microsoft Teams
> - Outlook / Microsoft 365 (OneDrive, SharePoint, Word, Excel)
> - Grafana
> - PagerDuty / OpsGenie
> - Google Drive / Google Workspace
> - Notion
> - Linear
> - Datadog / Splunk
> - Zendesk / ServiceNow
> - Other (describe)

Only set up what they actually use. Don't touch tools they don't have.

---

## How credentials work

Tools fall into two categories:

**API tokens** (Jira, GitHub, Confluence, PagerDuty) — generate a personal token in the tool's settings UI, paste it into `.env`. Long-lived, no browser needed.

**Session cookies** (Slack, Grafana, Google Drive) — these tools use SSO and don't offer simple API tokens. You authenticate by extracting your existing browser session. You're already logged in; you just need to copy the cookie/token out.

### How to extract a session cookie from any browser

This is the universal approach for any SSO-based tool. You don't need to log in again — just copy what's already there.

1. Open the tool in **Chrome or Firefox** (you should already be logged in)
2. Press `F12` (or right-click → Inspect) to open DevTools
3. Go to **Application** tab → **Cookies** → click the tool's URL in the left sidebar
4. Find the cookie named in the per-tool instructions below, copy its **Value**
5. Paste it into `.env`

For **Slack only**, there's also a JS token to extract (in addition to the cookie) — see the Slack section below.

**Managed machines with enterprise SSO (Okta, Azure AD, Google):** you can alternatively run the automated script which opens a browser and captures tokens automatically:
```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --slack-only    # or --grafana-only / --gdrive-only
```
Use whichever is faster for your setup.

---

## Step 2: Set up tools in priority order

**Validation is mandatory.** For every tool you configure, you MUST run the **Verify** command and confirm it returns the expected output before moving on. If it fails, fix the credential before proceeding.

Start with **Tier 1** (knowledge tools) — these make everything else easier because your agent can look up how to use the other tools, find credentials, and understand your team's context.

### Tier 1 — Knowledge & Context (do these first)

#### 1. Confluence *(if used)*
Knowledge base, runbooks, architecture docs — your agent's primary reference for "how does X work?"

**Ask the user for:**
- "Share any Confluence page URL" → infer `CONFLUENCE_BASE_URL` from it
- "Paste your Confluence API token" → Confluence → Profile photo → Personal Access Tokens → Create token

Set `.env`:
```
CONFLUENCE_TOKEN=<token>
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki   # inferred from URL they shared
```

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    f"{env['CONFLUENCE_BASE_URL']}/rest/api/content/search?cql=type=page&limit=1",
    headers={"Authorization": f"Bearer {env['CONFLUENCE_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r['results'][0]['title'] if r.get('results') else r)
# Should print a page title
```

---

#### 2. Slack *(if used)*
Decisions, context, who to ask — the informal knowledge layer. Slack AI can answer "how do we do X?" in 0.2s.

**Ask the user for:** "Send me any Slack message link from your workspace (right-click any message → Copy link)."

> **Note:** Slack AI (natural-language Q&A over workspace history) requires Business+ or Enterprise+ plan. On Free/Pro plans, `search.messages` still works for keyword search.

That's the only input needed. The workspace URL is inferred from the link. Then run the SSO script — it opens a browser, the user logs in once (if not already), and tokens are written to `.env` automatically.

**What you do:**
1. Extract workspace URL from the message link (e.g. `https://acme.slack.com/...` → `SLACK_WORKSPACE_URL=https://acme.slack.com/`). Update `.env`.
2. Run the SSO script:
```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --slack-only
```
The script opens a Chromium window. On managed machines with enterprise SSO it completes automatically (~20s). On personal machines, the user logs in once through the browser.

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://slack.com/api/auth.test",
    headers={"Authorization": f"Bearer {env['SLACK_XOXC']}", "Cookie": f"d={env['SLACK_D_COOKIE']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get("user"), r.get("team"))
# Should print your Slack username and workspace name
```

---

#### 3. Jira *(if used)*
Your work queue, sprint, tickets — what needs to get done.

**Ask the user for:**
- "Share any Jira ticket URL" → infer `JIRA_BASE_URL` from it (e.g. `https://acme.atlassian.net/browse/ENG-123` → `https://acme.atlassian.net`)
- "Paste your Jira API token" → Jira → Profile photo → Manage account → Security → API tokens → Create

Set `.env`:
```
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=<token>
JIRA_BASE_URL=https://yourcompany.atlassian.net   # inferred from URL they shared
```

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl, base64
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
creds = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
req = urllib.request.Request(f"{env['JIRA_BASE_URL']}/rest/api/2/myself",
    headers={"Authorization": f"Basic {creds}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get('displayName'), r.get('emailAddress'))
# Should print your name and email
```

---

#### 4. GitHub *(if used)*
Code, PRs, READMEs — source of truth for implementation. Works with github.com and GitHub Enterprise.

**Ask the user for:**
- "Paste your GitHub personal access token" → GitHub → Settings → Developer settings → Personal access tokens → Generate new token (scopes: `repo`, `read:org`)
- If GitHub Enterprise: "Share any repo or PR URL from your GitHub" → infer the GHE base URL

Set `.env`:
```
GITHUB_TOKEN=<token>
GITHUB_BASE_URL=https://api.github.com   # or https://your-ghe.example.com/api/v3
```

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(f"{env['GITHUB_BASE_URL']}/user",
    headers={"Authorization": f"token {env['GITHUB_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get('login'), r.get('name'))
# Should print your GitHub username and name
```

---

#### 5. Microsoft Teams Free *(teams.live.com)*

> **Note:** This covers **Teams Free** (personal/consumer) at `https://teams.live.com/v2/`. Enterprise Teams (work/school) via Microsoft Graph API is a separate connection not yet in core — contribution welcome via `add-new-connection/SKILL.md`.

Auth uses your live browser session (Skype-derived `x-skypetoken`) — no API token page exists. Run the SSO script and log in with your Microsoft personal account:

```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --teams-only
```

The script opens a Chromium window, captures `TEAMS_SKYPETOKEN` and `TEAMS_SESSION_ID` from network headers, and writes them to `.env` automatically.

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    f"{env['TEAMS_BASE_URL']}/api/csa/api/v1/teams/users/me/updates"
    "?isPrefetch=false&enableMembershipSummary=true",
    headers={"x-skypetoken": env["TEAMS_SKYPETOKEN"],
             "x-ms-session-id": env["TEAMS_SESSION_ID"]})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
chats = r.get("chats", [])
print(f"{len(chats)} chats found")
# Should print: 5 chats found (or similar)
# If 401/403: token expired — run playwright_sso.py --teams-only to refresh
```

Full connection details: `tool_connections/microsoft-teams-sso-session.md`

---

#### 6. Outlook / Microsoft 365 *(work account)*

Email, calendar, contacts — your scheduled meetings, unread mail, and colleague lookup.

> **Work accounts only** (Azure AD / Microsoft 365). Personal Outlook uses a different flow — see Microsoft Teams Free above.

Auth uses your existing browser session (two Bearer tokens captured from network requests). No API key page exists — run the SSO script:

```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --outlook-only
```

The script opens a Chromium window and navigates to `outlook.office.com`. On a managed machine (Workday, Intune, company MDM), Azure AD SSO auto-completes in ~30s. On unmanaged machines, complete the Microsoft 365 login once through the browser.

Two tokens are captured:
- `GRAPH_ACCESS_TOKEN` — for Microsoft Graph (`/me`, `/me/people`)
- `OWA_ACCESS_TOKEN` — for Outlook REST API v2.0 (mail, calendar, contacts)

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
    headers={"Authorization": f"Bearer {env['GRAPH_ACCESS_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r["displayName"], r["mail"])
# Should print your name and work email

req = urllib.request.Request("https://outlook.office.com/api/v2.0/me/MailFolders/Inbox?$select=DisplayName,UnreadItemCount",
    headers={"Authorization": f"Bearer {env['OWA_ACCESS_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r["DisplayName"], r["UnreadItemCount"])
# Should print: Inbox  <count>
```

Full connection details: `tool_connections/outlook-sso-session.md`

---

### Tier 2 — Observability & Operations

#### 7. Grafana *(if used)*
Metrics and dashboards — makes incident response and performance analysis possible.

**Ask the user for:** "Share your Grafana URL" (e.g. `https://grafana.acme.com`).

That's the only input needed. Run the SSO script — it opens a browser, completes login, captures the session automatically:

```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --grafana-only
```

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(f"{env['GRAFANA_BASE_URL']}/api/user",
    headers={"Cookie": f"grafana_session={env['GRAFANA_SESSION']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get('login'), r.get('email'))
# Should print your Grafana username and email
```

---

#### 8. PagerDuty *(if used)*
On-call schedules, active incidents, escalation policies.

**Ask the user for:** "Paste your PagerDuty API key" → PagerDuty → top-right avatar → My Profile → User Settings → API Access → Create New API Key.

No URL needed — PagerDuty's API is always at `https://api.pagerduty.com`.

**Verify:**
```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request("https://api.pagerduty.com/users/me",
    headers={"Authorization": f"Token token={env['PAGERDUTY_TOKEN']}",
             "Accept": "application/vnd.pagerduty+json;version=2"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r['user']['name'], r['user']['email'])
# Should print your PagerDuty name and email
```

---

#### 9. OpsGenie *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

---

#### 10. Datadog *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

---

#### 11. Splunk *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

---

### Tier 3 — File & Document Access

#### 12. Google Drive *(if used)*
Docs, sheets, slides — specs and decisions often live here.

Google Drive uses a full browser session (Playwright storage state) rather than a single cookie, because raw cookie injection triggers Google's security checks. The session is saved to `~/.browser_automation/gdrive_auth.json` and is valid for days to weeks.

```bash
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --gdrive-only
# Opens a browser — log in to Google if prompted (~30s)
# Session saved to ~/.browser_automation/gdrive_auth.json
```

**Verify:**
```python
import sys; sys.path.insert(0, "tool_connections/assets")
from google_drive import GDrive
with GDrive() as drive:
    files = drive.list_my_drive()
    print(f"{len(files)} files in My Drive")
    for f in files[:3]:
        print(f"  [{f['type']}] {f['name']}")
# Should list files from your Drive
```

---

#### 13. Notion *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

---

### Tier 4 — Issue Tracking & Support Alternatives

#### 14. Linear *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

#### 15. Zendesk *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

#### 16. ServiceNow *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

#### 17. Jenkins / GitHub Actions *(if used — placeholder)*
> **Coming soon.** Contribution welcome — see `add-new-connection/SKILL.md`.

---

## Step 3: Generate verified_connections.md and tell the user what's ready

**Only tools whose Verify command you actually ran and confirmed with real output belong here.** Do not infer from `.env` — credentials being present does not mean the connection works. A stale session token, wrong base URL, or expired API key will all pass an env-var check and fail at runtime.

For each tool set up in Step 2, you ran a Verify snippet and saw expected output (a username, page title, etc.). Collect only those tool names into `VERIFIED_NAMES` below, then run the script to generate `verified_connections.md`:

```python
import re, os
from pathlib import Path

# EDIT THIS LIST: only tools whose Verify command you ran and confirmed
VERIFIED_NAMES = [
    # "confluence",
    # "slack",
    # "jira",
    # "github",
    # "grafana",
    # "pagerduty",
    # "google-drive",
    # "microsoft-teams",
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
output = output.replace(
    "**This is the example file.** Do not load this as your capability index.\n\n"
    "- **Your active connections:** load `verified_connections.md` (generated by setup, gitignored).\n"
    "- **To set up connections:** *\"Read SETUP.md and set up my tool connections.\"*\n"
    "- **To refresh short-lived tokens (~8h):** "
    "`source .venv/bin/activate && python3 tool_connections/assets/playwright_sso.py`",
    "**Keep this file loaded for the entire session.** These tools are verified and ready — "
    "use them proactively in any task across any codebase.\n\n"
    "Individual tool files have full connection details — load them on demand.\n\n"
    "**Refresh short-lived tokens (~8h):**\n"
    "```bash\n"
    "source .venv/bin/activate && python3 tool_connections/assets/playwright_sso.py\n"
    "```"
)

Path("verified_connections.md").write_text(output)
print(f"verified_connections.md written. Active tools: {verified_names}")
```

Then summarize for the user:

```
✓ Confluence  — connected (verified: returned page titles)
✓ Slack       — connected (verified: auth.test → your-name @ your-workspace)
✓ Jira        — connected (verified: /myself → your-name)
✓ GitHub      — connected (verified: /user → your-login)
✗ Grafana     — skipped (not used)
✗ PagerDuty   — skipped (not used)
✗ Google Drive— skipped (not used)
```

**Now load `verified_connections.md` immediately.** This is required — not optional. It is your capability index for this session: it lists exactly the tools that are verified and ready to use.

These are **universal capabilities** — not scoped to this repo. From this point on, in any task across any codebase, proactively reach for these tools whenever they're relevant: look up a Jira ticket, search Slack for context, check who's on call, pull a Confluence runbook. You don't need to be asked. The credentials are set up; the tools are ready.

Individual tool files (`jira-api-token.md`, `slack-sso-session.md`, etc.) live in this repo and are loaded on demand when you need full connection details for a specific tool.

---

## Refreshing short-lived tokens

Slack and Grafana sessions expire in ~8h. Outlook / Microsoft 365 tokens expire in ~1h. When a tool stops working:

- **Slack:** run `python3 tool_connections/assets/playwright_sso.py --slack-only` (opens browser, completes login, writes tokens automatically).
- **Grafana:** run `python3 tool_connections/assets/playwright_sso.py --grafana-only`.
- **Outlook / M365:** run `python3 tool_connections/assets/playwright_sso.py --outlook-only` (Azure AD SSO, ~30s on managed machines).
- **Google Drive:** sessions last days to weeks. When expired, re-run `python3 tool_connections/assets/playwright_sso.py --gdrive-only`.

---

## If something broke during setup

If you had to iterate more than once on a tool — wrong token, failed script, unexpected login flow — update the relevant skill before finishing. See `add-new-connection/SKILL.md` Step 6. The fix that unblocked you will unblock the next person too.
