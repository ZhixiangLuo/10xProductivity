---
name: linear
auth: api-token
description: Linear — project management for software teams (GraphQL API). Use when listing teams, browsing or filtering issues, searching issues by keyword, or checking issue state and assignee.
env_vars:
  - LINEAR_API_TOKEN
  - LINEAR_BASE_URL
---

# Linear — API Token

Linear is a project management tool for software teams. Uses a GraphQL API with personal API key auth.

API docs: https://developers.linear.app/docs/graphql/working-with-the-graphql-api

**Verified:** Production (https://api.linear.app/graphql) — viewer, teams, issues, searchIssues — 2026-03. VPN not required.

---

## Credentials

```bash
# Add to .env:
# LINEAR_API_TOKEN=your-token-here
# LINEAR_BASE_URL=https://api.linear.app/graphql
# Generate at: https://linear.app/settings/api → Personal API keys → Create key
# Token lifetime: long-lived (does not expire unless revoked)
```

---

## Auth

Pass the token directly in the `Authorization` header (no `Bearer` prefix needed — Linear accepts both bare token and Bearer).

```bash
source .env
curl -s -X POST "$LINEAR_BASE_URL" \
  -H "Authorization: $LINEAR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ viewer { id name email } }"}' | python3 -m json.tool
# → {"data": {"viewer": {"id": "u_123", "name": "alice@example.com", "email": "alice@example.com"}}}
```

---

## Verified snippets

```bash
source .env
BASE="$LINEAR_BASE_URL"
TOKEN="$LINEAR_API_TOKEN"

# List teams
curl -s -X POST "$BASE" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ teams { nodes { id name key } } }"}' | python3 -m json.tool
# → {"data": {"teams": {"nodes": [{"id": "a5b9cf6d-...", "name": "My Team", "key": "TEAM"}]}}}

# List issues (first 5)
curl -s -X POST "$BASE" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ issues(first: 5) { nodes { id title identifier state { name } assignee { name } } } }"}' | python3 -m json.tool
# → {"data": {"issues": {"nodes": [{"id": "faa61a8e-...", "title": "Connect your tools", "identifier": "TEAM-3", "state": {"name": "Todo"}, "assignee": null}, ...]}}}

# Search issues — use "term" (not "query"; "issueSearch" with "query" arg is deprecated)
curl -s -X POST "$BASE" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ searchIssues(term: \"your search\", first: 5) { nodes { id identifier title state { name } } } }"}' | python3 -m json.tool
# → {"data": {"searchIssues": {"nodes": [{"id": "e829d769-...", "identifier": "TEAM-1", "title": "Get familiar with Linear", "state": {"name": "Todo"}}, ...]}}}
```

---

## Notes

- Search API: `searchIssues(term: "...", first: N)` — use `term` not `query`. The older `issueSearch` query with a `query` argument is deprecated and returns an error.
- No public AI/chat API endpoint — Linear AI features are UI-only, not exposed via GraphQL API.
- Token is long-lived; does not expire unless manually revoked at https://linear.app/settings/api.
