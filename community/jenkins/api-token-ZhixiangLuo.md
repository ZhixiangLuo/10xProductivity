---
tool: jenkins
auth: api-token
author: ZhixiangLuo
verified: 2026-03
env_vars:
  - JENKINS_TOKEN
  - JENKINS_USER
  - JENKINS_BASE_URL
---

# Jenkins — API Token

Jenkins is the leading open-source CI/CD automation server. Teams use it to run builds, tests, and deployments. This connection uses HTTP Basic auth with a personal API token — no CSRF crumb required for token-based requests (Jenkins 2.96+).

API docs: https://www.jenkins.io/doc/book/using/remote-access-api/

**Verified:** Public Jenkins instance (ci.jenkins.io) — `/api/json` (job listing) and `/job/{name}/api/json` (job details) — 2026-03. No VPN required for cloud-hosted Jenkins. Self-hosted instances may require VPN — document in your own `.env`.

---

## Credentials

```bash
# Add to .env:
# JENKINS_USER=your-username
# JENKINS_TOKEN=your-api-token
# JENKINS_BASE_URL=https://your-jenkins.example.com   (no trailing slash)
#
# Generate token: Jenkins → top-right user menu → Configure → API Token → Add new Token
```

---

## Auth

Jenkins uses HTTP Basic auth with `username:api-token` as credentials. Since Jenkins 2.96+, API token-based requests bypass CSRF crumb requirements entirely.

```bash
source .env

# Verify auth — returns current user info
curl -s "$JENKINS_BASE_URL/me/api/json" \
  --user "$JENKINS_USER:$JENKINS_TOKEN" \
  | jq '{id, fullName}'
# → {"id": "alice", "fullName": "Alice Smith"}
```

---

## Verified snippets

```bash
source .env
BASE="$JENKINS_BASE_URL"

# List all jobs on the controller (top-level view)
curl -s "$BASE/api/json?tree=jobs[name,url,color]" \
  --user "$JENKINS_USER:$JENKINS_TOKEN" \
  | jq '.jobs[:5]'
# → [{"color": "blue", "name": "my-service", "url": "https://jenkins.example.com/job/my-service/"}, ...]

# Get last build status for a specific job
JOB="my-service"
curl -s "$BASE/job/$JOB/lastBuild/api/json?tree=number,result,duration,timestamp,url" \
  --user "$JENKINS_USER:$JENKINS_TOKEN" \
  | jq .
# → {"duration": 120000, "number": 42, "result": "SUCCESS", "timestamp": 1700000000000, "url": "..."}

# Get last failed build info
curl -s "$BASE/job/$JOB/lastFailedBuild/api/json?tree=number,result,timestamp,url" \
  --user "$JENKINS_USER:$JENKINS_TOKEN" \
  | jq .
# → {"number": 41, "result": "FAILURE", "timestamp": 1699999000000, "url": "..."}

# Fetch console log for a specific build (first 5000 chars)
BUILD_NUM=42
curl -s "$BASE/job/$JOB/$BUILD_NUM/consoleText" \
  --user "$JENKINS_USER:$JENKINS_TOKEN" \
  | head -c 5000
# → Started by user Alice Smith
#   [Pipeline] Start of Pipeline
#   ...

# Get build queue (pending builds)
curl -s "$BASE/queue/api/json?tree=items[id,task[name],why,inQueueSince]" \
  --user "$JENKINS_USER:$JENKINS_TOKEN" \
  | jq '.items[:5]'
# → [{"id": 123, "task": {"name": "my-service"}, "why": "Waiting for executor", ...}]

# Detect Jenkins version (no auth needed)
curl -sI "$BASE" --user "$JENKINS_USER:$JENKINS_TOKEN" | grep -i x-jenkins
# → x-jenkins: 2.440.1
```

---

## Notes

- **No VPN required** for public/cloud-hosted Jenkins. Self-hosted instances often require corp VPN — check with your infra team.
- **Folder-based jobs:** use `/job/{folder}/job/{job-name}/` path pattern (e.g. `/job/team/job/my-service/lastBuild/api/json`).
- **Multibranch pipelines:** path is `/job/{pipeline-name}/job/{branch-name}/lastBuild/api/json`.
- **Read-only** — these snippets do not trigger builds. To trigger a build: `POST $BASE/job/$JOB/build --user $JENKINS_USER:$JENKINS_TOKEN` (use cautiously).
- **Permissions:** read endpoints work with any authenticated user. Build triggering requires Build permission on the job.
- **Token generation:** Jenkins → click your username (top right) → Configure → API Token → Add new Token → Generate. Token is shown once.
