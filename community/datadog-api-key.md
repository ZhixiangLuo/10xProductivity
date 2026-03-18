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

Datadog is the leading cloud monitoring platform covering metrics, logs, APM traces, dashboards, and incident management. Read endpoints require both an API key and an Application key. The validate endpoint only needs the API key.

API docs: https://docs.datadoghq.com/api/latest/

**Verified:** Production (api.us5.datadoghq.com) — `/api/v1/validate`, `/api/v1/monitor`, `/api/v1/hosts`, `/api/v1/dashboard`, `/api/v1/metrics`, `/api/v1/query`, `/api/v2/incidents` — 2026-03. No VPN required.

---

## Credentials

```bash
# Add to .env:
# DD_API_KEY=your-api-key-here
# DD_APP_KEY=your-application-key-here
# DD_BASE_URL=https://api.us5.datadoghq.com   (change to match your site — see Notes)
#
# API key:  https://{your-site}/organization-settings/api-keys → New Key
# App key:  https://{your-site}/organization-settings/application-keys → New Key
# Token lifetime: long-lived (no expiry by default)
```

---

## Auth

All requests send two headers: `DD-API-KEY` and `DD-APPLICATION-KEY`. The validate endpoint only requires the API key — use it to confirm connectivity before adding the app key.

```bash
source .env

# Validate API key only
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

# List monitors (returns [] on a fresh org with no monitors configured)
curl -s "$BASE/api/v1/monitor?page=0&page_size=5" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | {id, name, type, overall_state}]'
# → []

# Filter to alerting monitors only
curl -s "$BASE/api/v1/monitor?page=0&page_size=20" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | select(.overall_state == "Alert") | {id, name, overall_state}]'
# → []

# List hosts (returns empty on a fresh org with no agents installed)
curl -s "$BASE/api/v1/hosts?count=5&start=0" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{total_returned, host_list: [.host_list[]? | {name, up, apps}]}'
# → {"total_returned": 0, "host_list": []}

# List dashboards
curl -s "$BASE/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{total: (.dashboards | length), sample: [.dashboards[:3][]? | {id, title}]}'
# → {"total": 0, "sample": []}

# List available metrics (active in the last hour)
curl -s "$BASE/api/v1/metrics?from=$(($(date +%s) - 3600))" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{metrics_count: (.metrics | length), sample: .metrics[:5]}'
# → {"metrics_count": 9, "sample": ["datadog.apis.usage.per_org", "datadog.apis.usage.per_org_ratio", "datadog.apis.usage.per_user", "datadog.apis.usage.per_user_ratio", "datadog.event.tracking.indexation.audit.events"]}

# Query a metric time-series (last 1 hour)
# IMPORTANT: braces {*} must be URL-encoded as %7B*%7D in curl
NOW=$(date +%s); FROM=$((NOW - 3600))
curl -s "$BASE/api/v1/query?from=$FROM&to=$NOW&query=avg:datadog.apis.usage.per_org%7B*%7D" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{status, series_count: (.series | length), sample_points: (.series[0].pointlist[-3:] // [])}'
# → {"status": "ok", "series_count": 1, "sample_points": [[1773860420000.0, 1.75], [1773860460000.0, 1.64], [1773860480000.0, 1.62]]}

# List incidents (HTTP 200 even on fresh org; returns empty data array)
# Note: page size brackets must be URL-encoded
curl -s "$BASE/api/v2/incidents?page%5Bsize%5D=5" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{data_count: (.data | length), pagination: .meta.pagination}'
# → {"data_count": 0, "pagination": {"offset": 0, "next_offset": 0, "size": 0}}
```

---

## Notes

- **Site-specific base URLs** — set `DD_BASE_URL` to match your Datadog org. Find your site from the subdomain in your Datadog UI URL:
  - US1 (default): `https://api.datadoghq.com`
  - US3: `https://api.us3.datadoghq.com`
  - US5: `https://api.us5.datadoghq.com`
  - EU: `https://api.datadoghq.eu`
  - AP1: `https://api.ap1.datadoghq.com`
  - Gov: `https://api.ddog-gov.com`
- **URL-encoding required in curl:** `{*}` → `%7B*%7D`, `[size]` → `%5Bsize%5D`. Omitting encoding causes parse errors (`Rule 'scope_expr' didn't match`).
- **Empty results are valid:** a fresh org returns `[]` / `{}` for monitors, hosts, dashboards — not an error.
- **Application key is user-scoped** — inherits the creating user's permissions.
- **No VPN required** — all endpoints are public SaaS.
- **Rate limits** are in response headers: `x-ratelimit-remaining`, `x-ratelimit-reset`. Default ~100 req/60s.
