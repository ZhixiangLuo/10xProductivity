# Setup Guide

This file is for your agent. Point your agent here first:

> *"Read SETUP.md and set up my tool connections."*

Your agent will walk you through which credentials to get, run the SSO refresher where needed, and verify each connection works.

---

## Prerequisites

```bash
# Clone and create Python env
git clone https://github.com/yourusername/10xProductivity.git
cd 10xProductivity
python3 -m venv .venv && source .venv/bin/activate
pip install playwright && playwright install chromium

# Copy env template
cp tool_connections/env.sample .env
```

---

## Step 1: Ask the user which tools they use

Before doing anything, ask:

> *"Which of these tools does your team use? (Select all that apply)"*
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

## Step 2: Set up tools in priority order

Start with **Tier 1** (knowledge tools) — these make everything else easier because your agent can look up how to use the other tools, find credentials, and understand your team's context.

### Tier 1 — Knowledge & Context (do these first)

#### 1. Confluence *(if used)*
Knowledge base, runbooks, architecture docs — your agent's primary reference for "how does X work?"

```bash
# What you need:
# 1. Your Confluence base URL
# 2. A personal API token

# Get token: Confluence → Profile → Personal Access Tokens → Create
# Then add to .env:
# CONFLUENCE_TOKEN=your-token
# CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
```

**Verify:**
```bash
source .env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
  | jq '.results[0] | {id, title}'
# Should return a page title, not an error
```

---

#### 2. Slack *(if used)*
Decisions, context, who to ask — the informal knowledge layer. Slack AI can answer "how do we do X?" in 0.2s.

```bash
# What you need: your Slack workspace URL
# Token is captured automatically via browser SSO

# Add to .env first:
# SLACK_WORKSPACE_URL=https://yourcompany.slack.com/

# Then run (opens browser for ~20s SSO):
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --slack-only
# On a managed machine: SSO completes automatically
# On a personal machine: log in manually when the browser opens
```

**Verify:**
```python
# Load tokens — always use Python to read .env (bash truncates long tokens)
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

```bash
# What you need:
# 1. Your Jira base URL
# 2. A personal API token

# Get token: Jira → Profile → API Tokens → Create
# Then add to .env:
# JIRA_API_TOKEN=your-token
# JIRA_BASE_URL=https://yourcompany.atlassian.net
```

**Verify:**
```bash
source .env
curl -s -H "Authorization: Bearer $JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/2/myself" \
  | jq '{displayName, emailAddress}'
# Should return your name and email
```

---

#### 4. GitHub *(if used)*
Code, PRs, READMEs — source of truth for implementation. Works with github.com and GitHub Enterprise.

```bash
# What you need: a personal access token
# Get token: GitHub → Settings → Developer settings → Personal access tokens → Generate
# Scopes: repo, read:org
# Then add to .env:
# GITHUB_TOKEN=ghp_your-token
# GITHUB_BASE_URL=https://api.github.com
# (For GitHub Enterprise: GITHUB_BASE_URL=https://your-ghe.example.com/api/v3)
```

**Verify:**
```bash
source .env
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/user" \
  | jq '{login, name, email}'
# Should return your GitHub username and name
```

---

#### 5. Microsoft Teams *(if used — placeholder)*
> **Coming soon.** Teams supports a Graph API via Azure AD app registration. Contribution welcome — see `add-new-connection/SKILL.md`.

---

#### 6. Outlook / Microsoft 365 *(if used — placeholder)*
> **Coming soon.** Covers Outlook (email/calendar), OneDrive, SharePoint, Word, Excel via Microsoft Graph API. Contribution welcome — see `add-new-connection/SKILL.md`.

---

### Tier 2 — Observability & Operations

#### 7. Grafana *(if used)*
Metrics and dashboards — makes incident response and performance analysis possible.

```bash
# What you need: your Grafana base URL
# Token is captured automatically via browser SSO

# Add to .env first (BEFORE running the SSO script):
# GRAFANA_BASE_URL=https://grafana.yourcompany.com

# Then run (opens browser for SSO):
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --grafana-only
```

**Verify:**
```bash
source .env
curl -s "$GRAFANA_BASE_URL/api/user" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '{login, email, name}'
# Should return your Grafana user info
```

---

#### 8. PagerDuty *(if used)*
On-call schedules, active incidents, escalation policies.

```bash
# What you need: a personal REST API key
# Get key: PagerDuty → My Profile → User Settings → API Access → Create New API Key
# Then add to .env:
# PAGERDUTY_TOKEN=your-api-key
```

**Verify:**
```bash
source .env
curl -s "https://api.pagerduty.com/users/me" \
  -H "Authorization: Token token=$PAGERDUTY_TOKEN" \
  -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '{name: .user.name, email: .user.email, role: .user.role}'
# Should return your PagerDuty user info
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

```bash
# No API token needed — uses browser session

# Run (opens browser for Google Workspace SSO, ~30s):
source .venv/bin/activate
python3 tool_connections/assets/playwright_sso.py --gdrive-only
# Session saved to ~/.browser_automation/gdrive_auth.json (valid for days/weeks)
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

## Step 3: Tell the user what's ready

After setup, summarize:

```
✓ Confluence  — connected (verified: returned page titles)
✓ Slack       — connected (verified: auth.test → your-name @ your-workspace)
✓ Jira        — connected (verified: /myself → your-name)
✓ GitHub      — connected (verified: /user → your-login)
✗ Grafana     — skipped (not used)
✗ PagerDuty   — skipped (not used)
✗ Google Drive— skipped (not used)
```

Now read `tool_connections/SKILL.md` to understand which tool to use for each task.

---

## Refreshing short-lived tokens

Grafana and Slack sessions expire in ~8h. When a tool stops working, refresh:

```bash
source .venv/bin/activate

# Refresh all (Grafana + Slack):
python3 tool_connections/assets/playwright_sso.py

# Refresh one:
python3 tool_connections/assets/playwright_sso.py --slack-only
python3 tool_connections/assets/playwright_sso.py --grafana-only
python3 tool_connections/assets/playwright_sso.py --gdrive-only
```

Tokens are validated first — the browser only opens if something is actually expired.
