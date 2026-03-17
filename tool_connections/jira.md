---
name: jira
description: All Jira operations — fetch issues, JQL search, update fields, write descriptions/comments, REST API quirks (components, editmeta, Agile/sprint API). Use when fetching a Jira issue, listing tickets, updating fields, writing Jira comments or descriptions, or using the Jira REST API.
---

# Jira

Env: `JIRA_API_TOKEN`, `JIRA_BASE_URL`

```bash
# Set in .env:
# JIRA_API_TOKEN=your-jira-api-token
# JIRA_BASE_URL=https://yourcompany.atlassian.net   # or your self-hosted Jira URL
```

Auth: `Authorization: Bearer $JIRA_API_TOKEN`

**Generate token:** Jira → Profile → API Tokens → Create (Jira Cloud) or Profile → Security → API Tokens (Jira Server/Data Center)

When mentioning issues, link them: `[KEY-123]($JIRA_BASE_URL/browse/KEY-123)`

---

## Fetch and search

```bash
source .env

# Get a specific issue
curl -s -H "Authorization: Bearer $JIRA_API_TOKEN" -H "Accept: application/json" \
  "$JIRA_BASE_URL/rest/api/2/issue/KEY-123" \
  | jq '{key, summary: .fields.summary, status: .fields.status.name, assignee: .fields.assignee.displayName, priority: .fields.priority.name, description: .fields.description}'

# Search with JQL
curl -s -G -H "Authorization: Bearer $JIRA_API_TOKEN" -H "Accept: application/json" \
  "$JIRA_BASE_URL/rest/api/2/search" \
  --data-urlencode "jql=assignee = currentUser() AND status NOT IN (Resolved,Closed,Done) ORDER BY updated DESC" \
  --data-urlencode "maxResults=25" \
  --data-urlencode "fields=summary,status,priority,updated" \
  | jq '.issues[] | {key, summary: .fields.summary, status: .fields.status.name}'
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

```bash
source .env

# Update a field (e.g. summary)
curl -s -X PUT -H "Authorization: Bearer $JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$JIRA_BASE_URL/rest/api/2/issue/KEY-123" \
  -d '{"fields": {"summary": "New summary"}}'

# Update components — must use IDs, not names
curl -s -X PUT -H "Authorization: Bearer $JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$JIRA_BASE_URL/rest/api/2/issue/KEY-123" \
  -d '{"fields": {"components": [{"id": "<COMPONENT_ID>"}]}}'

# Add a comment
curl -s -X POST -H "Authorization: Bearer $JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$JIRA_BASE_URL/rest/api/2/issue/KEY-123/comment" \
  -d '{"body": "Comment text here."}'
```

---

## REST API quirks

**Components:** Use IDs, not names — `{"id": "123456"}` not `{"name": "Component Name"}`. Get component IDs from the project or via editmeta.

**Epic Link in JQL:** Requires quotes — `"Epic Link" = KEY-123`, not `Epic Link = KEY-123`.

**Check editable fields before updating:**
```bash
curl -s -H "Authorization: Bearer $JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/2/issue/KEY-123/editmeta" \
  | python3 -m json.tool
```

**Sprint field:** Cannot be set via the standard REST API. Use the Agile API instead:
```bash
# List boards for a project
curl -s -H "Authorization: Bearer $JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/agile/1.0/board?projectKeyOrId=MYPROJECT"

# Move issue to sprint
curl -s -X POST -H "Authorization: Bearer $JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$JIRA_BASE_URL/rest/agile/1.0/sprint/<sprintId>/issue" \
  -d '{"issues": ["KEY-123"]}'
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
