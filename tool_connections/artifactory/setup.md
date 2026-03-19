---
name: artifactory-setup
description: Set up Artifactory connection. API key or access token + Basic auth. Ask for Artifactory URL and credentials.
---

# Artifactory — Setup

## Step 1: Ask for a URL

Ask the user: "Share your Artifactory URL" (e.g. `https://artifactory.yourcompany.com`).

Infer `ARTIFACTORY_BASE_URL` from the URL.

---

## Auth method: API key or Access Token (Basic auth)

**What to ask the user:**
- "Your Artifactory username"
- "Your Artifactory API key or access token":
  - API key: Artifactory UI → top-right user icon → Edit Profile → Authentication Settings → Generate API Key
  - Access token (7.21+): Administration → Identity and Access → Access Tokens → Generate Token

---

## Set `.env`

```bash
ARTIFACTORY_USER=your-username
ARTIFACTORY_TOKEN=your-api-key-or-token
ARTIFACTORY_BASE_URL=https://artifactory.yourcompany.com
```

---

## Verify

```bash
source .env
AUTH=$(echo -n "$ARTIFACTORY_USER:$ARTIFACTORY_TOKEN" | base64)
curl -s -H "Authorization: Basic $AUTH" \
  "$ARTIFACTORY_BASE_URL/artifactory/api/system/ping"
# → OK
# If 401: wrong user or token. If connection refused: check ARTIFACTORY_BASE_URL.
```

**Connection details:** `tool_connections/artifactory/connection-api-token.md`

---

## `.env` entries

```bash
# --- Artifactory ---
ARTIFACTORY_USER=your-username
ARTIFACTORY_TOKEN=your-api-key-or-access-token
ARTIFACTORY_BASE_URL=https://artifactory.yourcompany.com
# Generate API key: Artifactory UI → top-right user icon → Edit Profile → Authentication Settings → Generate API Key
# Or (7.21+): Administration → Identity and Access → Access Tokens → Generate Token
```
