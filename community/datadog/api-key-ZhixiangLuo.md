---
tool: datadog
auth: api-key
author: ZhixiangLuo
verified: 2026-03
env_vars:
  - DD_API_KEY
  - DD_APP_KEY
  - DD_BASE_URL
---

# Datadog — API Key + Application Key

Datadog is the leading cloud monitoring platform covering metrics, logs, APM traces, dashboards, and incident management. Read endpoints require both an API key and an Application key. Write endpoints (create monitor, trigger incident) additionally require appropriate org permissions.

API docs: https://docs.datadoghq.com/api/latest/

**Verified:** Datadog US site (api.datadoghq.com) — `/api/v1/validate`, `/api/v1/monitor` (list), `/api/v1/hosts` — 2026-03. No VPN required. EU/US3/US5 orgs must set `DD_BASE_URL` to their site's API endpoint.

---

## Credentials

```bash
# Add to .env:
# DD_API_KEY=your-api-key-here
# DD_APP_KEY=your-application-key-here
# DD_BASE_URL=https://api.datadoghq.com   (default US; change for EU/US3/US5 — see Notes)
#
# Generate at: https://app.datadoghq.com/organization-settings/api-keys
# App key at:  https://app.datadoghq.com/organization-settings/application-keys
```

---

## Auth

All requests send two headers: `DD-API-KEY` and `DD-APPLICATION-KEY`. Read endpoints require both; the validate endpoint only needs the API key.

```bash
source .env

# Validate API key only (no app key needed)
curl -s "$DD_BASE_URL/api/v1/validate" \
  -H "DD-API-KEY: $DD_API_KEY" \
  | jq .
# → {"valid": true}
```

---

## Verified snippets

```bash
source .env
BASE="$DD_BASE_URL"

# List active monitors (first 5)
curl -s "$BASE/api/v1/monitor?page=0&page_size=5" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | {id, name, type, overall_state}]'
# → [{"id": 12345, "name": "CPU high on web-prod", "type": "metric alert", "overall_state": "OK"}, ...]

# List triggered (alerting) monitors
curl -s "$BASE/api/v1/monitor?monitor_tags=*&with_downtimes=false&page=0&page_size=20" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | select(.overall_state == "Alert") | {id, name, overall_state}]'
# → [{"id": 67890, "name": "Error rate spike", "overall_state": "Alert"}]

# List hosts (infrastructure inventory)
curl -s "$BASE/api/v1/hosts?count=5&start=0" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '.host_list[:5] | [.[] | {name, up, apps}]'
# → [{"name": "web-prod-1", "up": true, "apps": ["agent", "docker"]}, ...]

# Search dashboards by title keyword
curl -s "$BASE/api/v1/dashboard?filter_shared=false" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.dashboards[] | {id, title, url}] | .[:5]'
# → [{"id": "abc-123", "title": "Service Overview", "url": "/dashboard/abc-123/..."}, ...]

# Query a metric (last 1 hour) — e.g. system.cpu.user for a host
NOW=$(date +%s)
FROM=$((NOW - 3600))
curl -s "$BASE/api/v1/query?from=$FROM&to=$NOW&query=avg:system.cpu.user{*}" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{status, series: [.series[] | {metric, pointlist: .pointlist[-3:]}]}'
# → {"status": "ok", "series": [{"metric": "system.cpu.user", "pointlist": [[1700000000000, 12.5], ...]}]}

# List active incidents (v2 API — requires Incident Management feature)
curl -s "$BASE/api/v2/incidents?page[size]=5" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '.data[:3] | [.[] | {id, type, attributes: {title: .attributes.title, status: .attributes.status}}]'
# → [{"id": "abc-def", "type": "incidents", "attributes": {"title": "DB latency spike", "status": "active"}}]
# Note: 404 if Incident Management is not enabled for your org
```

---

## Notes

- **Site-specific base URLs** — set `DD_BASE_URL` to match your Datadog org:
  - US (default): `https://api.datadoghq.com`
  - EU: `https://api.datadoghq.eu`
  - US3: `https://api.us3.datadoghq.com`
  - US5: `https://api.us5.datadoghq.com`
  - AP1: `https://api.ap1.datadoghq.com`
- **Application key is user-scoped** — it inherits the creating user's permissions. A read-only user's app key can only read.
- **Incident Management** — the `/api/v2/incidents` endpoint returns 404 if your org doesn't have Incident Management enabled (Enterprise plan feature).
- **Metrics query** — the `query` parameter uses Datadog's metrics query syntax (same as dashboards). Scope with `{host:my-host}` or `{service:my-service}`.
- **No VPN required** — all endpoints are public SaaS. Requests originate from your local machine.
