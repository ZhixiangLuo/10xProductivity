---
name: jenkins-setup
description: Set up Jenkins connection. API token + Basic auth. Ask for Jenkins URL and credentials.
---

# Jenkins — Setup

## Step 1: Ask for a URL

Ask the user: "Share your Jenkins URL" (e.g. `https://jenkins.yourcompany.com`).

Infer `JENKINS_BASE_URL` from the URL. Note: if jobs live under a subfolder, the base URL can include the folder prefix (e.g. `https://jenkins.yourcompany.com/my-team`).

---

## Auth method: API token (Basic auth)

**What to ask the user:**
- "Your Jenkins username"
- "Your Jenkins API token" → Jenkins → top-right user icon → Configure → API Token → Add new Token

---

## Set `.env`

```bash
JENKINS_USER=your-username
JENKINS_TOKEN=your-api-token
JENKINS_BASE_URL=https://jenkins.yourcompany.com
```

---

## Verify

```bash
source .env
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$JENKINS_BASE_URL/api/json?tree=jobs[name,color]" \
  | jq '.jobs[:3] | .[] | {name, color}'
# → [{"name": "my-pipeline", "color": "blue"}, ...]
# color: blue = passing, red = failing, grey = not built yet
# If 401: wrong user or token. If 403: user lacks read permission.
```

**Connection details:** `tool_connections/jenkins/connection-api-token.md`

---

## `.env` entries

```bash
# --- Jenkins ---
JENKINS_USER=your-username
JENKINS_TOKEN=your-api-token
JENKINS_BASE_URL=https://jenkins.yourcompany.com
# Can include a folder prefix: https://jenkins.yourcompany.com/my-team
# Generate API token: Jenkins → top-right user icon → Configure → API Token → Add new Token
```
