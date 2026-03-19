---
name: confluence
auth: api-token
description: Confluence wiki — search pages, fetch content, browse spaces. Use when looking up internal documentation, runbooks, architecture pages, procedures, or any content stored in Confluence.
env_vars:
  - CONFLUENCE_TOKEN
  - CONFLUENCE_EMAIL
  - CONFLUENCE_BASE_URL
---

# Confluence

Env: `CONFLUENCE_TOKEN`, `CONFLUENCE_EMAIL`, `CONFLUENCE_BASE_URL`

**Confluence Cloud** uses HTTP Basic auth: `email:api-token` (NOT Bearer).
**Confluence Server/Data Center** uses Bearer token (Personal Access Token).

```bash
# Set in .env:
# CONFLUENCE_EMAIL=your-email@example.com        # Atlassian account email
# CONFLUENCE_TOKEN=your-atlassian-api-token      # Same token as JIRA_API_TOKEN if using same account
# CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki  # Confluence Cloud
# CONFLUENCE_BASE_URL=https://confluence.yourcompany.com      # Confluence Server/Data Center
```

**Generate token:** https://id.atlassian.com/manage-profile/security/api-tokens → Create API token

For Confluence Cloud, the token is the same as your Jira API token (same Atlassian account).

## Verify connection

```bash
source .env

# Confluence Cloud (Basic auth with email:token)
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
  | jq '{total: .size, first: .results[0].title}'
# → {"total": 1, "first": "Template - Decision documentation"}

# Confluence Server/Data Center (Bearer token)
# curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
#   "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
#   | jq '{total: .size, first: .results[0].title}'
```

**Verified:** Production (get10xproductivity.atlassian.net/wiki) — /rest/api/content/search + /rest/api/space — 2026-03-18. No VPN required.

---

## Search pages

```bash
source .env

# Search by title
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=title~%22<keyword>%22&limit=5&expand=space" \
  | jq '.results[] | {id, title, space: .space.key}'

# Search body text
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=text~%22<keyword>%22&limit=5&expand=space" \
  | jq '.results[] | {id, title, space: .space.key}'

# Search by title AND body keyword
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=title~%22<keyword1>%22+AND+text~%22<keyword2>%22&limit=5&expand=space" \
  | jq '.results[] | {id, title, space: .space.key}'

# Search in a specific space
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=space=%22MYSPACE%22+AND+text~%22<keyword>%22&limit=10" \
  | jq '.results[] | {id, title}'
```

---

## Fetch page content

```bash
source .env

# Fetch a page by ID (strip HTML tags for readable text)
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/<PAGE_ID>?expand=body.view" \
  | jq -r '.body.view.value' | sed 's/<[^>]*>//g' | tr -s ' \n' | head -c 3000

# Get page metadata (title, space, version, last modified)
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/<PAGE_ID>?expand=version,space" \
  | jq '{id, title, space: .space.key, version: .version.number, lastModified: .version.when}'

# Get child pages
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/<PAGE_ID>/child/page?limit=20" \
  | jq '.results[] | {id, title}'
```

---

## Browse spaces

```bash
source .env

# List all spaces
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/space?limit=25&expand=description.plain" \
  | jq '.results[] | {key, name, description: .description.plain.value}'

# Get a space's homepage
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/space/<SPACE_KEY>?expand=homepage" \
  | jq '{key, name, homepage: .homepage.id}'

# List all pages in a space
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/space/<SPACE_KEY>/content?limit=25" \
  | jq '.page.results[] | {id, title}'
```

---

## CQL (Confluence Query Language) reference

| Goal | CQL |
|------|-----|
| Page by title | `title = "Exact Title"` |
| Title contains keyword | `title ~ "keyword"` |
| Body contains text | `text ~ "keyword"` |
| In specific space | `space = "SPACEKEY"` |
| Updated after date | `lastModified > "2026-01-01"` |
| By a specific author | `creator = "username"` |
| Pages only (not blog posts) | `type = "page"` |
| Combine filters | `space = "ENG" AND text ~ "deployment" AND lastModified > "2026-01-01"` |
