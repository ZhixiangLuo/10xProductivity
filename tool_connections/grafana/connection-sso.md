---
name: grafana
auth: sso-session
description: Grafana dashboards — extract PromQL queries from panels, look up dashboard UIDs, query data. Use when you need the PromQL from a Grafana dashboard (e.g. for incident analysis), or want to find which dashboards exist for a service.
env_vars:
  - GRAFANA_BASE_URL
  - GRAFANA_SESSION
---

# Grafana

Env: `GRAFANA_BASE_URL`, `GRAFANA_SESSION`

```bash
# Set in .env:
# GRAFANA_BASE_URL=https://grafana.yourcompany.com
# GRAFANA_SESSION=your-grafana-session-cookie-value   (~8h, refresh with playwright_sso.py)
```

Auth: session cookie captured via SSO — refresh with the shared script (see below).

**The primary use case is extracting PromQL:** Grafana dashboard JSON contains all panel queries with Grafana variable placeholders (e.g. `${env}`). Substitute variables to get runnable PromQL, then execute via your Prometheus-compatible endpoint.

## Verify connection

```bash
source .env
curl -s "$GRAFANA_BASE_URL/api/user" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '{login, email, name}'
# → {"login": "alice", "email": "alice@example.com", "name": "Alice Smith"}
# ⚠ Fresh clone: GRAFANA_SESSION doesn't exist until playwright_sso.py has run once — go to Refresh session below first.
# If you see 401/redirect: session expired — run playwright_sso.py to refresh.
# If you see connection refused: check GRAFANA_BASE_URL in .env.
```

---

## Refresh session

```bash
# Refreshes GRAFANA_SESSION — opens browser for SSO, ~20–30 s
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py
```

---

## Get PromQL from a dashboard

```bash
source .env

# Get full dashboard JSON — includes all panels and their PromQL targets
curl -s "$GRAFANA_BASE_URL/api/dashboards/uid/{uid}" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '[.dashboard.panels[] | select(.targets != null)
         | {title, exprs: [.targets[]? | select(.expr) | .expr]}
         | select(.exprs | length > 0)]'

# Shorter version — first 10 panels, truncated expressions
curl -s "$GRAFANA_BASE_URL/api/dashboards/uid/{uid}" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '[.dashboard.panels[] | select(.targets != null)
         | {title, exprs: [.targets[]? | select(.expr) | .expr[:120]]}
         | select(.exprs | length > 0)][:10]'
```

**Variable substitution:** Panel PromQL uses Grafana template variables like `${env}` or `$service`. Replace with actual values before running:

```python
import re

def substitute_vars(expr: str, vars: dict) -> str:
    """Replace Grafana ${var} and $var placeholders with actual values."""
    for k, v in vars.items():
        expr = re.sub(rf'\${{{re.escape(k)}}}', v, expr)
        expr = re.sub(rf'\${re.escape(k)}(?=[^a-zA-Z0-9_]|$)', v, expr)
    return expr

# Example
expr = 'rate(http_requests_total{env="${env}",service="${service}"}[5m])'
vars = {"env": "production", "service": "my-service"}
runnable = substitute_vars(expr, vars)
# → rate(http_requests_total{env="production",service="my-service"}[5m])
```

---

## Find dashboards

```bash
source .env

# Search by keyword
curl -s "$GRAFANA_BASE_URL/api/search?query=<keyword>&limit=10&type=dash-db" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '.[] | {title, uid, folderTitle}'

# Search by tag
curl -s "$GRAFANA_BASE_URL/api/search?tag=<tag-name>&limit=20" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '.[] | {title, uid}'
```

---

## Query live metric data

```bash
source .env

# Execute a PromQL query (instant vector)
curl -s "$GRAFANA_BASE_URL/api/datasources/proxy/uid/{datasource_uid}/api/v1/query" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  --data-urlencode "query=up" \
  --data-urlencode "time=$(date +%s)" \
  | jq '.data.result[] | {metric, value: .value[1]}'

# Find datasource UIDs
curl -s "$GRAFANA_BASE_URL/api/datasources" \
  -H "Cookie: grafana_session=$GRAFANA_SESSION" \
  | jq '.[] | {uid, name, type}'
```

---

## Notes on auth

Grafana session cookies are set after SSO login (~8h TTL). On managed machines, `playwright_sso.py` completes this automatically in a headed Chromium window without user interaction. On personal machines, it opens the Grafana login page — complete login manually once, then the session is saved.

If your Grafana uses API keys instead of SSO:
```bash
# Alternative: API key auth (if your Grafana instance supports it)
# GRAFANA_API_KEY=your-grafana-api-key
curl -s "$GRAFANA_BASE_URL/api/dashboards/uid/{uid}" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  | jq '.dashboard.title'
```
