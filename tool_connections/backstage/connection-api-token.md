---
name: backstage
auth: api-token
description: Backstage — Internal Developer Portal for software catalog management. Use when finding service owners, looking up team members, discovering PagerDuty/GitHub/Slack annotations for any component, or browsing the catalog.
env_vars:
  - BACKSTAGE_TOKEN
  - BACKSTAGE_BASE_URL
---

# Backstage — API token (Bearer auth)

Backstage is Spotify's open-source Internal Developer Portal, used by many engineering organizations to manage a software catalog of services, teams, users, and resources. Common use cases: find who owns a service, look up a team's members, discover PagerDuty/Slack/GitHub annotations for any component.

API docs: https://backstage.io/docs/features/software-catalog/software-catalog-api

**Verified:** Production (self-hosted Backstage) — `/api/catalog/entity-facets` + `/api/catalog/entities/by-query` + `/api/catalog/entities/by-name` — 2026-03. No VPN required (depends on your deployment).

---

## Credentials

```bash
# Add to .env:
# BACKSTAGE_TOKEN=your-backstage-token
# BACKSTAGE_BASE_URL=https://backstage.yourcompany.com
#
# Token type depends on your Backstage deployment:
#   Static token (long-lived): set in app-config.yaml under backend.auth.keys
#     Ask your platform team: "Can I get a static Backstage token for local agent use?"
#   SSO-issued JWT (short-lived, ~8h): log in via your identity provider and capture the token
#     from your browser's local storage: DevTools → Application → Local Storage → backstage
#     → look for a key containing "token"
```

---

## Auth

Bearer token in the `Authorization` header:

```bash
source .env
BASE="$BACKSTAGE_BASE_URL"
# Usage: -H "Authorization: Bearer $BACKSTAGE_TOKEN"
```

---

## ⚠ Endpoint gotcha

`/api/catalog/entities?filter=...` is the **deprecated endpoint** — it returns null-filled objects. Always use:
- `/api/catalog/entities/by-query?filter=...` — filtered list (modern)
- `/api/catalog/entities/by-name/{kind}/{namespace}/{name}` — single entity by exact name

---

## Verify connection

```bash
source .env

curl -s -k "$BACKSTAGE_BASE_URL/api/catalog/entity-facets?facet=kind" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '.facets.kind'
# → [{"value": "Component", "count": 1154}, {"value": "Group", "count": 4373}, {"value": "User", "count": 28244}, ...]
# If 401: token expired or wrong — refresh or ask your platform team.
```

---

## Verified snippets

```bash
source .env
BASE="$BACKSTAGE_BASE_URL"

# Entity kinds and counts — good sanity check
curl -s -k "$BASE/api/catalog/entity-facets?facet=kind" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '.facets.kind'
# → [{"value": "Component", "count": 1154}, {"value": "Domain", "count": 15}, {"value": "Group", "count": 4373}, {"value": "System", "count": 65}, ...]

# List services (first 3, sparse fieldset — faster for large catalogs)
curl -s -k "$BASE/api/catalog/entities/by-query?filter=kind=component,spec.type=service&limit=3&fields=metadata.name,spec.owner,spec.lifecycle" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '{totalItems, items: [.items[] | {name: .metadata.name, owner: .spec.owner, lifecycle: .spec.lifecycle}]}'
# → {"totalItems": 850, "items": [{"name": "my-service", "owner": "group:platform-team", "lifecycle": "production"}, ...]}

# Get a single component by exact name
curl -s -k "$BASE/api/catalog/entities/by-name/component/default/{service-name}" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '{name: .metadata.name, type: .spec.type, owner: .spec.owner, lifecycle: .spec.lifecycle, annotations: .metadata.annotations}'
# → {"name": "my-service", "type": "service", "owner": "group:platform-team", "lifecycle": "production", "annotations": {...}}

# User lookup by username
curl -s -k "$BASE/api/catalog/entities/by-name/user/default/{username}" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '{name: .metadata.name, email: .spec.profile.email, displayName: .spec.profile.displayName, memberOf: .spec.memberOf}'
# → {"name": "alice", "email": "alice@example.com", "displayName": "Alice Smith", "memberOf": ["group:platform-team"]}

# Group lookup by name
curl -s -k "$BASE/api/catalog/entities/by-name/group/default/{group-name}" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '{name: .metadata.name, members: .spec.members[:5]}'
# → {"name": "platform-team", "members": ["alice", "bob", "carol"]}

# Component type breakdown (facet)
curl -s -k "$BASE/api/catalog/entity-facets?facet=spec.type&filter=kind=component" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '{"spec.type": .facets["spec.type"]}'
# → {"spec.type": [{"value": "service", "count": 850}, {"value": "resource", "count": 200}, {"value": "library", "count": 104}, ...]}
```

---

## Common annotations to look for

Components carry annotations linking to other tools. Common standard ones:

| Annotation | Example value | Links to |
|---|---|---|
| `pagerduty.com/service-id` | `P1234AB` | PagerDuty service |
| `github.com/project-slug` | `org/repo` | GitHub repo |
| `backstage.io/source-location` | `url:https://...` | Catalog YAML source in git |
| `backstage.io/managed-by-location` | `url:https://...` | Where Backstage manages this entity from |

Check what annotations your instance uses:
```bash
curl -s -k "$BACKSTAGE_BASE_URL/api/catalog/entities/by-query?filter=kind=component&limit=3" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  | jq '.items[].metadata.annotations | keys'
```

---

## Notes

- **namespace:** Most entities use `default`. Multi-tenant setups may use other namespaces — check entity listings.
- **Filter syntax:** Comma (`,`) = AND within one `filter=` param. Multiple `&filter=` params = OR.
- **fields= sparse fieldset:** Always use `fields=metadata.name,spec.owner,...` for list queries — it significantly reduces response size. On large catalogs (10k+ entities or 28k+ users), omitting it can return several MB per page.
- **Pagination:** Use `&offset={N}` to page through results. `totalItems` tells you the total count.
- **Token lifetime:** Static tokens are long-lived. SSO-issued JWTs expire in ~8h — re-capture from browser local storage or ask your platform team for a static token.
- **-k flag:** Deployments using internal CAs — add `-k` to curl or configure the cert.
