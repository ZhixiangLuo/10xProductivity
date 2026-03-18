---
tool: artifactory
auth: api-token
author: ZhixiangLuo
verified:
env_vars:
  - ARTIFACTORY_TOKEN
  - ARTIFACTORY_BASE_URL
---

# JFrog Artifactory — API Token

JFrog Artifactory is the universal artifact repository manager used to store, version, and distribute build artifacts (Docker images, npm packages, Maven JARs, Python wheels, etc.). This connection uses a personal access token (Bearer auth) — the modern JFrog auth method replacing Basic username/password.

API docs: https://jfrog.com/help/r/jfrog-platform-rest-apis/artifactory-rest-apis

**Verified:** NOT YET VERIFIED against a live instance. Snippets are based on official JFrog REST API documentation and confirmed endpoint shapes — but have not been executed against a real Artifactory server. Set `verified: YYYY-MM` and replace `# → ...` comments with real output before promoting to core.

---

## Credentials

```bash
# Add to .env:
# ARTIFACTORY_TOKEN=your-access-token-here
# ARTIFACTORY_BASE_URL=https://yourcompany.jfrog.io   (no trailing slash)
#
# Generate token: JFrog Platform → top-right user menu → Edit Profile → Identity Tokens → Generate Token
```

---

## Auth

Artifactory supports Bearer token auth (modern) and Basic auth (legacy). Prefer Bearer — Basic auth with password is deprecated in JFrog Cloud.

```bash
source .env
BASE="$ARTIFACTORY_BASE_URL/artifactory"

# Ping (no auth needed)
curl -s "$BASE/api/v1/system/ping"
# → OK

# Verify auth — returns current user info
curl -s "$BASE/api/security/user/me" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '{name, email, groups}'
# → {"name": "alice", "email": "alice@example.com", "groups": ["readers", "devs"]}
```

---

## Snippets (unverified — based on official docs)

```bash
source .env
BASE="$ARTIFACTORY_BASE_URL/artifactory"

# List all repositories
curl -s "$BASE/api/repositories" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '[.[:10][] | {key, type, packageType}]'
# → [{"key": "libs-release", "type": "LOCAL", "packageType": "Maven"}, ...]

# List local Docker repositories only
curl -s "$BASE/api/repositories?type=local&packageType=docker" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '[.[] | {key, packageType}]'
# → [{"key": "docker-local", "packageType": "Docker"}]

# Search for an artifact by name
REPO="libs-release"
ARTIFACT="my-service"
curl -s "$BASE/api/search/quick?name=$ARTIFACT&repos=$REPO" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '.results[:5]'
# → [{"uri": "https://yourcompany.jfrog.io/artifactory/api/storage/libs-release/com/example/my-service/1.2.3/my-service-1.2.3.jar"}, ...]

# Browse versions at a path
REPO="libs-release"
PATH_IN_REPO="com/example/my-service"
curl -s "$BASE/api/storage/$REPO/$PATH_IN_REPO" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '{repo, path, children: [.children[].uri]}'
# → {"repo": "libs-release", "path": "/com/example/my-service", "children": ["/1.2.0", "/1.2.1", "/1.2.3"]}

# Get artifact properties for a specific version
curl -s "$BASE/api/storage/$REPO/$PATH_IN_REPO/1.2.3/my-service-1.2.3.jar?properties" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq .properties
# → {"build.name": ["my-service"], "build.number": ["42"]}

# Storage summary per repository
curl -s "$BASE/api/storageinfo" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '.repositoriesSummaryList[:5] | [.[] | {repoKey, usedSpaceInBytes, filesCount}]'
# → [{"repoKey": "libs-release", "usedSpaceInBytes": "1073741824", "filesCount": 1234}, ...]

# AQL: find latest 3 artifacts modified in the last 7 days
curl -s "$BASE/api/search/aql" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  -H "Content-Type: text/plain" \
  -d 'items.find({"repo": "libs-release", "modified": {"$last": "7d"}}).sort({"$desc": ["modified"]}).limit(3)' \
  | jq '.results | [.[] | {name, path, modified, size}]'
# → [{"name": "my-service-1.2.3.jar", "path": "com/example/my-service/1.2.3", "modified": "2026-03-17T10:00:00.000Z", "size": 8388608}]

# List Docker image tags
DOCKER_REPO="docker-local"
IMAGE="my-service"
curl -s "$BASE/api/docker/$DOCKER_REPO/v2/$IMAGE/tags/list" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq .
# → {"name": "my-service", "tags": ["latest", "1.2.3", "1.2.2"]}
```

---

## Notes

- **JFrog Cloud URL format:** `https://{company}.jfrog.io` — the API path is always under `/artifactory/`.
- **Self-hosted format:** `https://artifactory.yourcompany.com` — same `/artifactory/` prefix.
- **AQL** (Artifactory Query Language) is the most powerful search interface for complex queries (by date, property, checksum, etc.).
- **No VPN required** for JFrog Cloud. Self-hosted instances commonly require corp VPN.
- **Read-only** — these snippets do not deploy or delete artifacts. Deploy requires `deploy` permission on the target repo.
