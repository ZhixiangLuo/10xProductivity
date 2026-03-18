---
name: datadog
auth: api-key
description: Datadog — cloud monitoring platform for metrics, APM, logs, dashboards, and incidents. Use when querying monitors and alerts, checking host inventory, searching metrics time-series, listing dashboards, or looking up active incidents.
env_vars:
  - DD_API_KEY
  - DD_APP_KEY
  - DD_BASE_URL
---

# Datadog

Cloud monitoring platform covering metrics, APM traces, logs, dashboards, and incident management. Used by SRE and engineering teams to observe service health and respond to incidents.

Env: `DD_API_KEY` + `DD_APP_KEY` (long-lived — no expiry by default)
API docs: https://docs.datadoghq.com/api/latest/

**Verified:** Production (api.us5.datadoghq.com) — `/api/v1/validate`, `/api/v1/monitor`, `/api/v1/hosts`, `/api/v1/dashboard`, `/api/v1/metrics`, `/api/v1/query`, `/api/v2/incidents` — 2026-03. No VPN required.

---

## Auth setup (one-time)

1. Find your site subdomain from the Datadog UI URL (e.g. `us5.datadoghq.com` → `DD_BASE_URL=https://api.us5.datadoghq.com`)
2. Go to `https://{your-site}/organization-settings/api-keys` → **New Key**
3. Go to `https://{your-site}/organization-settings/application-keys` → **New Key**
4. Add to `.env`:

```bash
# --- Datadog ---
DD_API_KEY=your-api-key-here
DD_APP_KEY=your-application-key-here
DD_BASE_URL=https://api.us5.datadoghq.com   # change to match your site
```

Auth: `DD-API-KEY` header for all requests; `DD-APPLICATION-KEY` header for read endpoints.

## Verify connection

```bash
source .env
curl -s "$DD_BASE_URL/api/v1/validate" \
  -H "DD-API-KEY: $DD_API_KEY" \
  | jq .
# → {"valid": true}
```

---

## Quick-reference snippets

```bash
source .env
BASE="$DD_BASE_URL"

# List monitors
curl -s "$BASE/api/v1/monitor?page=0&page_size=10" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | {id, name, type, overall_state}]'
# → [] on fresh org; [{...}] when monitors exist

# Filter to alerting monitors only
curl -s "$BASE/api/v1/monitor?page=0&page_size=50" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '[.[] | select(.overall_state == "Alert") | {id, name, overall_state}]'
# → [] or [{id: 12345, name: "CPU spike", overall_state: "Alert"}]

# List hosts
curl -s "$BASE/api/v1/hosts?count=10&start=0" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{total_returned, host_list: [.host_list[]? | {name, up, apps}]}'
# → {"total_returned": 0, "host_list": []}

# List dashboards
curl -s "$BASE/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{total: (.dashboards | length), sample: [.dashboards[:5][]? | {id, title}]}'
# → {"total": 0, "sample": []}

# List active metrics (last hour)
curl -s "$BASE/api/v1/metrics?from=$(($(date +%s) - 3600))" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{metrics_count: (.metrics | length), sample: .metrics[:5]}'
# → {"metrics_count": 9, "sample": ["datadog.apis.usage.per_org", ...]}

# Query a metric time-series (last 1 hour)
# IMPORTANT: {*} must be URL-encoded as %7B*%7D — bare braces cause a parse error
NOW=$(date +%s); FROM=$((NOW - 3600))
METRIC="avg:datadog.apis.usage.per_org%7B*%7D"   # replace with any metric from list above
curl -s "$BASE/api/v1/query?from=$FROM&to=$NOW&query=$METRIC" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{status, series_count: (.series | length), sample_points: (.series[0].pointlist[-3:] // [])}'
# → {"status": "ok", "series_count": 1, "sample_points": [[1773860420000.0, 1.75], ...]}

# List incidents (page brackets must also be URL-encoded)
curl -s "$BASE/api/v2/incidents?page%5Bsize%5D=10" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '{data_count: (.data | length), pagination: .meta.pagination}'
# → {"data_count": 0, "pagination": {"offset": 0, "next_offset": 0, "size": 0}}
```

---

## Full API surface

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/validate` | Validate API key (no app key needed) |
| GET | `/api/v1/monitor` | List monitors (`?page`, `?page_size`, `?monitor_tags`) |
| GET | `/api/v1/monitor/{id}` | Single monitor detail |
| GET | `/api/v1/hosts` | Host inventory (`?count`, `?start`, `?filter`, `?sort_field`) |
| GET | `/api/v1/dashboard` | List all dashboards |
| GET | `/api/v1/dashboard/{id}` | Single dashboard with widgets |
| GET | `/api/v1/metrics` | List active metric names (`?from=<unix_ts>`) |
| GET | `/api/v1/query` | Query metric time-series (`?from`, `?to`, `?query`) |
| GET | `/api/v2/incidents` | List incidents (`?page%5Bsize%5D=`, `?filter%5Bstatus%5D=`) |
| GET | `/api/v2/incidents/{id}` | Single incident detail |

---

## Notes

- **Site-specific base URLs** — match `DD_BASE_URL` to your org's subdomain:
  - US1 (default): `https://api.datadoghq.com`
  - US3: `https://api.us3.datadoghq.com`
  - US5: `https://api.us5.datadoghq.com`
  - EU: `https://api.datadoghq.eu`
  - AP1: `https://api.ap1.datadoghq.com`
  - Gov: `https://api.ddog-gov.com`
- **URL-encoding required in curl:** `{*}` → `%7B*%7D`; `[size]` → `%5Bsize%5D`. Bare braces cause `Rule 'scope_expr' didn't match` parse errors.
- **Empty results are valid:** fresh orgs return `[]` / `{}` for monitors, hosts, dashboards — not an error.
- **Application key is user-scoped** — inherits the creating user's permissions.
- **No VPN required** — all endpoints are public SaaS.
- **Rate limits** in response headers: `x-ratelimit-remaining`, `x-ratelimit-reset` (default ~100 req/60s).
