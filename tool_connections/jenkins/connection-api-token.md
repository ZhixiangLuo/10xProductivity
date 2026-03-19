---
name: jenkins
auth: api-token
description: Jenkins — open-source CI/CD automation server. Use when checking build status, reading console logs to diagnose failures, listing jobs, or triggering builds.
env_vars:
  - JENKINS_USER
  - JENKINS_TOKEN
  - JENKINS_BASE_URL
---

# Jenkins — API token (Basic auth)

Jenkins is an open-source automation server widely used for CI/CD pipelines — building, testing, and deploying software. Every object (job, build, node) exposes a JSON REST API via `/api/json`. Common agentic use cases: check if the last build passed, get build logs to diagnose failures, trigger a new build.

API docs: https://www.jenkins.io/doc/book/using/remote-access-api/

**Verified:** Production (Jenkins 2.x with Kubernetes controller) — `/api/json` + `/job/{name}/lastBuild/api/json` + `/job/{name}/lastBuild/consoleText` — 2026-03. No VPN required (depends on your instance network policy).

---

## Credentials

```bash
# Add to .env:
# JENKINS_USER=your-username
# JENKINS_TOKEN=your-api-token
# JENKINS_BASE_URL=https://jenkins.yourcompany.com
#
# JENKINS_BASE_URL can include a folder prefix if jobs live in a subfolder:
#   e.g. https://jenkins.yourcompany.com/my-team
#
# Generate API token: Jenkins → top-right user icon → Configure → API Token → Add new Token
# API tokens do not expire by default. If your admin has enabled token expiry, you'll get a 401
# after the TTL — regenerate from Configure → API Token.
```

---

## Auth

Basic auth with `JENKINS_USER:JENKINS_TOKEN`:

```bash
source .env
BASE="$JENKINS_BASE_URL"
# Usage: -u "$JENKINS_USER:$JENKINS_TOKEN"
```

---

## Verify connection

```bash
source .env

curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$JENKINS_BASE_URL/api/json?tree=jobs[name,color]" \
  | jq '.jobs[:3] | .[] | {name, color}'
# → [{"name": "my-pipeline", "color": "blue"}, {"name": "deploy-staging", "color": "red"}, ...]
# color: blue = passing, red = failing, grey = not built yet
# If 401: wrong user or token. If 403: user lacks read permission.
```

---

## Verified snippets

```bash
source .env
BASE="$JENKINS_BASE_URL"

# List all jobs in BASE (with status color)
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/api/json?tree=jobs[name,color]" \
  | jq '.jobs[] | {name, color}'
# → [{"name": "my-pipeline", "color": "blue"}, {"name": "deploy-staging", "color": "red"}, ...]

# Check last build status for a job
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/lastBuild/api/json" \
  | jq '{number, result, duration}'
# → {"number": 42, "result": "SUCCESS", "duration": 108355}
# result: "SUCCESS", "FAILURE", "ABORTED", null (still building)

# Get last build parameters
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/lastBuild/api/json" \
  | jq '{result, params: [.actions[] | select(.parameters) | .parameters[] | {name, value}]}'
# → {"result": "SUCCESS", "params": [{"name": "BRANCH", "value": "main"}, {"name": "ENV", "value": "staging"}]}

# Get build console log (last N lines)
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/lastBuild/consoleText" \
  | tail -20
# → (last 20 lines of build output)
# → Finished: SUCCESS

# Get console log for a specific build number
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/{build-number}/consoleText"
# → (full log for build #N)

# List recent builds (last 10)
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/api/json?tree=builds[number,result,duration]{0,10}" \
  | jq '.builds[] | {number, result, duration}'
# → [{"number": 42, "result": "SUCCESS", "duration": 108355}, {"number": 41, "result": "FAILURE", "duration": 45200}, ...]

# Trigger a build (no parameters)
curl -s -X POST -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/build"
# → (empty body, HTTP 201 = queued successfully)

# Trigger a build with parameters
curl -s -X POST -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/{job-name}/buildWithParameters?BRANCH=main&ENV=staging"
# → (empty body, HTTP 201 = queued)
# Parameter names must match the job's defined parameters exactly.
```

---

## Nested jobs (folder structure)

Jenkins often nests jobs under folders. Chain `/job/` for each level:

```bash
# job inside a folder: BASE/job/{folder}/job/{job-name}/
curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" \
  "$BASE/job/my-team/job/my-pipeline/lastBuild/api/json" \
  | jq '{number, result}'
# → {"number": 9, "result": "SUCCESS"}
```

---

## Python helper

```python
import json, urllib.request, ssl, base64
from pathlib import Path

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
BASE = env["JENKINS_BASE_URL"]
creds = base64.b64encode(f"{env['JENKINS_USER']}:{env['JENKINS_TOKEN']}".encode()).decode()
HEADERS = {"Authorization": f"Basic {creds}"}

def j_get(path):
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read())

# List jobs
jobs = j_get("/api/json?tree=jobs[name,color]")["jobs"]
for j in jobs[:5]:
    print(j["name"], j.get("color", "n/a"))

# Last build for a specific job
build = j_get("/job/my-pipeline/lastBuild/api/json")
print(build["number"], build["result"])
```

---

## Notes

- **CSRF crumbs:** Some Jenkins instances require a crumb header for POST requests. If `buildWithParameters` returns 403:
  ```bash
  CRUMB=$(curl -s -u "$JENKINS_USER:$JENKINS_TOKEN" "$JENKINS_BASE_URL/crumbIssuer/api/json" | jq -r '"\(.crumbRequestField): \(.crumb)"')
  curl -s -X POST -u "$JENKINS_USER:$JENKINS_TOKEN" -H "$CRUMB" "$JENKINS_BASE_URL/job/{job}/build"
  ```
- **color field:** `blue` = passing, `red` = failing, `yellow` = unstable, `grey`/`notbuilt` = no builds, `disabled` = disabled. Append `_anime` for in-progress (e.g. `blue_anime`).
- **Build shortcuts:** `lastBuild`, `lastSuccessfulBuild`, `lastFailedBuild`, `lastStableBuild` — or use a build number directly (`/job/{name}/42/`).
- **Token expiry:** API tokens do not expire by default. If your admin has enabled token expiry, a 401 after previously working auth means the token expired — regenerate from Configure → API Token.
- **Network:** Jenkins controllers are typically internal — VPN may be required.
- **Permissions:** Triggering builds and reading logs requires appropriate Jenkins role. Read-only queries usually work with any authenticated user.
