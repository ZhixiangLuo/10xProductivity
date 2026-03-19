---
name: datadog-setup
description: Set up Datadog connection. API key + Application key. Ask for Datadog URL to infer the regional base URL.
---

# Datadog — Setup

## Auth method: API key + Application key

**What to ask the user:**
- "Share your Datadog URL" → infer `DD_BASE_URL` from the subdomain
- "Paste your Datadog API key" → `https://{your-site}/organization-settings/api-keys` → New Key
- "Paste your Datadog Application key" → `https://{your-site}/organization-settings/application-keys` → New Key

---

## Step 1: Infer base URL from their Datadog URL

| URL subdomain | DD_BASE_URL |
|--------------|-------------|
| `app.datadoghq.com` | `https://api.datadoghq.com` |
| `us3.datadoghq.com` | `https://api.us3.datadoghq.com` |
| `us5.datadoghq.com` | `https://api.us5.datadoghq.com` |
| `app.datadoghq.eu` | `https://api.datadoghq.eu` |
| `ap1.datadoghq.com` | `https://api.ap1.datadoghq.com` |
| `ddog-gov.com` | `https://api.ddog-gov.com` |

---

## Set `.env`

```bash
DD_API_KEY=your-api-key-here
DD_APP_KEY=your-application-key-here
DD_BASE_URL=https://api.us5.datadoghq.com   # change to match your site
```

---

## Verify

```bash
source .env
curl -s "$DD_BASE_URL/api/v1/validate" \
  -H "DD-API-KEY: $DD_API_KEY" \
  | jq .
# → {"valid": true}
# If {"valid": false}: wrong API key or wrong base URL
```

**Connection details:** `tool_connections/datadog/connection-api-key.md`

---

## `.env` entries

```bash
# --- Datadog ---
DD_API_KEY=your-datadog-api-key
DD_APP_KEY=your-datadog-application-key
DD_BASE_URL=https://api.datadoghq.com
# US5: https://api.us5.datadoghq.com / EU: https://api.datadoghq.eu (match your site subdomain)
# API key:  https://{your-site}/organization-settings/api-keys → New Key
# App key:  https://{your-site}/organization-settings/application-keys → New Key
```
