---
name: jira
auth: api-token
description: All Jira operations — fetch issues, JQL search, update fields, write descriptions/comments, REST API quirks (components, editmeta, Agile/sprint API). Use when fetching a Jira issue, listing tickets, updating fields, writing Jira comments or descriptions, or using the Jira REST API.
env_vars:
  - JIRA_API_TOKEN
  - JIRA_BASE_URL
  - JIRA_EMAIL       # Cloud only — omit for Server/Data Center
---

# Jira

**Cloud** (`*.atlassian.net`): Basic auth — `JIRA_EMAIL` + `JIRA_API_TOKEN`
**Server / Data Center** (self-hosted): Bearer PAT — `JIRA_API_TOKEN` only, no email

```bash
# Cloud (.env):
# JIRA_EMAIL=you@yourcompany.com
# JIRA_API_TOKEN=your-jira-api-token
# JIRA_BASE_URL=https://yourcompany.atlassian.net

# Server/DC (.env) — no JIRA_EMAIL:
# JIRA_API_TOKEN=your-jira-pat
# JIRA_BASE_URL=https://jira.yourcompany.com
```

**⚠ Always load credentials in Python, not bash `source .env`** — avoids silent truncation of long tokens.

```python
from pathlib import Path
import base64
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
if "JIRA_EMAIL" in env:
    creds = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
else:
    headers = {"Authorization": f"Bearer {env['JIRA_API_TOKEN']}", "Accept": "application/json"}
```

**Generate token:**
- Cloud: Jira → Profile photo → Manage account → Security → API tokens → Create
- Server/DC: Jira → Profile photo → Personal Access Tokens → Create token

When mentioning issues, link them: `[KEY-123]($JIRA_BASE_URL/browse/KEY-123)`

## Verify connection

```python
from pathlib import Path
import urllib.request, json, ssl, base64
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
if "JIRA_EMAIL" in env:
    creds = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    auth_header = f"Basic {creds}"
else:
    auth_header = f"Bearer {env['JIRA_API_TOKEN']}"
req = urllib.request.Request(f"{env['JIRA_BASE_URL']}/rest/api/2/myself",
    headers={"Authorization": auth_header})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r.get('displayName'), r.get('emailAddress'))
# → Alice Smith alice@example.com
# If 401: wrong email or token. If 403: token lacks permissions.
```

---

## Fetch and search

```python
from pathlib import Path
import urllib.request, json, ssl, base64, urllib.parse
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
if "JIRA_EMAIL" in env:
    creds = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    auth_header = f"Basic {creds}"
else:
    auth_header = f"Bearer {env['JIRA_API_TOKEN']}"
headers = {"Authorization": auth_header, "Accept": "application/json", "Content-Type": "application/json"}

def jira_get(path):
    req = urllib.request.Request(f"{env['JIRA_BASE_URL']}{path}", headers=headers)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())

def jira_post(path, data):
    req = urllib.request.Request(f"{env['JIRA_BASE_URL']}{path}",
        data=json.dumps(data).encode(), headers=headers, method="POST")
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())

def jira_put(path, data):
    req = urllib.request.Request(f"{env['JIRA_BASE_URL']}{path}",
        data=json.dumps(data).encode(), headers=headers, method="PUT")
    urllib.request.urlopen(req, context=ctx, timeout=10)

# Get a specific issue
issue = jira_get("/rest/api/2/issue/KEY-123")
print(issue['key'], issue['fields']['summary'], issue['fields']['status']['name'])

# Search with JQL
jql = "assignee = currentUser() AND status NOT IN (Resolved,Closed,Done) ORDER BY updated DESC"
results = jira_get(f"/rest/api/2/search?{urllib.parse.urlencode({'jql': jql, 'maxResults': 25, 'fields': 'summary,status,priority,updated'})}")
for i in results['issues']:
    print(i['key'], i['fields']['summary'], i['fields']['status']['name'])
```

## Common JQL patterns

| Goal | JQL |
|------|-----|
| My open issues | `assignee = currentUser() AND status NOT IN (Resolved,Closed,Done) ORDER BY updated DESC` |
| My sprint issues | `assignee = currentUser() AND sprint in openSprints() ORDER BY rank` |
| Issues updated today | `assignee = currentUser() AND updated >= startOfDay()` |
| Issues in project | `project = MYPROJECT AND status = "In Progress"` |
| By epic | `"Epic Link" = KEY-123 AND status != Closed` (quotes required around "Epic Link") |

---

## Update fields

```python
# Update a field (e.g. summary) — uses jira_put() from above
jira_put("/rest/api/2/issue/KEY-123", {"fields": {"summary": "New summary"}})

# Update components — must use IDs, not names
jira_put("/rest/api/2/issue/KEY-123", {"fields": {"components": [{"id": "<COMPONENT_ID>"}]}})

# Add a comment
jira_post("/rest/api/2/issue/KEY-123/comment", {"body": "Comment text here."})

# Create an issue
new_issue = jira_post("/rest/api/2/issue", {
    "fields": {
        "project": {"key": "MYPROJECT"},
        "summary": "Issue summary",
        "description": "Issue description.",
        "issuetype": {"name": "Task"}
    }
})
print(f"Created: {new_issue['key']} — {env['JIRA_BASE_URL']}/browse/{new_issue['key']}")
```

---

## REST API quirks

**Components:** Use IDs, not names — `{"id": "123456"}` not `{"name": "Component Name"}`. Get component IDs from the project or via editmeta.

**Epic Link in JQL:** Requires quotes — `"Epic Link" = KEY-123`, not `Epic Link = KEY-123`.

**Check editable fields before updating:**
```python
editmeta = jira_get("/rest/api/2/issue/KEY-123/editmeta")
print(json.dumps(editmeta, indent=2))
```

**Sprint field:** Cannot be set via the standard REST API. Use the Agile API instead:
```python
# List boards for a project
boards = jira_get("/rest/agile/1.0/board?projectKeyOrId=MYPROJECT")
for b in boards['values']:
    print(b['id'], b['name'])

# Move issue to sprint
jira_post(f"/rest/agile/1.0/sprint/<sprintId>/issue", {"issues": ["KEY-123"]})
```

---

## Formatting (wiki markup)

Jira uses **wiki markup**, not markdown. Use this when writing descriptions or comments.

| Element | Markdown (don't use) | Jira wiki markup (use this) |
|---------|----------------------|-----------------------------|
| Heading 1 | `# Title` | `h1. Title` |
| Heading 2 | `## Title` | `h2. Title` |
| Bold | `**text**` | `*text*` |
| Italic | `*text*` | `_text_` |
| Bullet list | `- item` | `* item` |
| Nested bullet | `  - sub` | `** sub` |
| Numbered list | `1. item` | `# item` |
| Code block | ` ```json ` | `{code:json}...{code}` |
| Inline code | `` `code` `` | `{{code}}` |
| Link | `[text](url)` | `[text\|url]` |
| Horizontal rule | `---` | `----` |

Example:
```
h2. Section Title

* First bullet
** Nested bullet

*Bold text* and _italic text_

{code:python}
def example():
    pass
{code}

File path: {{src/file.py}}
```

Tone: professional, no emojis.
