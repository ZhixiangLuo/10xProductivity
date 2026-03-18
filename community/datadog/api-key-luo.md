---
tool: datadog
auth: api-key
author: ZhixiangLuo
verified:
env_vars:
  - DD_API_KEY
  - DD_APP_KEY
  - DD_BASE_URL
---

# Datadog — API Key + Application Key

Datadog is the leading cloud monitoring platform covering metrics, logs, APM traces, dashboards, and incident management. Read endpoints require both an API key and an Application key. The validate endpoint only needs the API key.

API docs: https://docs.datadoghq.com/api/latest/

**Verified:** NOT YET VERIFIED against a live instance. Snippets are based on official Datadog API documentation and confirmed response shapes — but have not been executed against a real org. Set `verified: YYYY-MM` and replace `# → ...` comments with real output before promoting to core.

---

## Credentials

```bash
# Add to .env:
# DD_API_KEY=your-api-key-here
# DD_APP_KEY=your-application-key-here
# DD_BASE_URL=https://api.datadoghq.com   (default US; see Notes for EU/US3/US5)
#
# API key:  https://app.datadoghq.com/organization-settings/api-keys
# App key:  https://app.datadoghq.com/organization-settings/application-keys
```

---

## Auth

All requests send two headers: `DD-API-KEY` and `DD-APPLICATION-KEY`. The validate endpoint only requires the API key.

```bash
source .env

# Validate API key only
curl -s "$DD_BASE_URL/api/v1/validate" \
  -H "DD-API-KEY: $DD_API_KEY" \
  | jq .
# → {"valid": true}
```

---

## Snippets (unverified — based on official docs)

```bash
source .env
BASE="$DD_BASE_URL"

# List active monitors (first page)
curl -s "$BASE/api/v1/monitor?page=0&page_size=5" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | {id, name, type, overall_state}]'
# → [{"id": 12345, "name": "CPU high on web-prod", "type": "metric alert", "overall_state": "OK"}, ...]

# Filter to alerting monitors only
curl -s "$BASE/api/v1/monitor?page=0&page_size=20" \
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

# List dashboards
curl -s "$BASE/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.dashboards[:5][] | {id, title, url}]'
# → [{"id": "abc-123", "title": "Service Overview", "url": "/dashboard/abc-123/..."}, ...]

# Query a metric (last 1 hour)
NOW=$(date +%s); FROM=$((NOW - 3600))
curl -s "$BASE/api/v1/query?from=$FROM&to=$NOW&query=avg:system.cpu.user{*}" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{status, series: [.series[] | {metric, pointlist: .pointlist[-3:]}]}'
# → {"status": "ok", "series": [{"metric": "system.cpu.user", "pointlist": [[1700000000000, 12.5], ...]}]}

# List active incidents (requires Incident Management feature — Enterprise plan)
curl -s "$BASE/api/v2/incidents?page[size]=5" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '.data[:3] | [.[] | {id, attributes: {title: .attributes.title, status: .attributes.status}}]'
# → [{"id": "abc-def", "attributes": {"title": "DB latency spike", "status": "active"}}]
# Note: returns 404 if Incident Management is not enabled for your org
```

---

## Notes

- **Site-specific base URLs** — set `DD_BASE_URL` to match your org:
  - US (default): `https://api.datadoghq.com`
  - EU: `https://api.datadoghq.eu`
  - US3: `https://api.us3.datadoghq.com`
  - US5: `https://api.us5.datadoghq.com`
  - AP1: `https://api.ap1.datadoghq.com`
- **Application key is user-scoped** — inherits the creating user's permissions.
- **Incident Management** — `/api/v2/incidents` returns 404 if your org doesn't have the feature (Enterprise plan).
- **Metrics query syntax** — same as Datadog dashboards; scope with `{host:my-host}` or `{service:my-service}`.
- **No VPN required** — all endpoints are public SaaS.
