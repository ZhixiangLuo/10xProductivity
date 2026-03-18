---
tool: artifactory
auth: api-token
author: ZhixiangLuo
verified: 2026-03
env_vars:
  - ARTIFACTORY_TOKEN
  - ARTIFACTORY_BASE_URL
---

# JFrog Artifactory — API Token

JFrog Artifactory is the universal artifact repository manager used to store, version, and distribute build artifacts (Docker images, npm packages, Maven JARs, Python wheels, etc.). This connection uses a personal access token (Bearer auth) — the modern JFrog auth method replacing Basic username/password.

API docs: https://jfrog.com/help/r/jfrog-platform-rest-apis/artifactory-rest-apis

**Verified:** JFrog Cloud instance (yourcompany.jfrog.io) — `/artifactory/api/repositories`, `/artifactory/api/storage/{repo}`, `/artifactory/api/search/quick` — 2026-03. No VPN required for JFrog Cloud. Self-hosted instances may require corp VPN.

---

## Credentials

```bash
# Add to .env:
# ARTIFACTORY_TOKEN=your-access-token-here
# ARTIFACTORY_BASE_URL=https://yourcompany.jfrog.io   (no trailing slash; JFrog Cloud format)
#
# Generate token: JFrog Platform → top-right user menu → Edit Profile → Identity Tokens → Generate Token
# Or via API: POST $ARTIFACTORY_BASE_URL/access/api/v1/tokens
```

---

## Auth

Artifactory supports Bearer token auth (modern) and Basic auth (legacy). Always prefer Bearer with a personal access token — Basic auth with password is deprecated in JFrog Cloud.

```bash
source .env
BASE="$ARTIFACTORY_BASE_URL/artifactory"

# Verify auth — returns current user info
curl -s "$BASE/api/v1/system/ping" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN"
# → OK

curl -s "$BASE/api/security/user/me" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '{name, email, groups}'
# → {"name": "alice", "email": "alice@example.com", "groups": ["readers", "devs"]}
```

---

## Verified snippets

```bash
source .env
BASE="$ARTIFACTORY_BASE_URL/artifactory"

# List all repositories
curl -s "$BASE/api/repositories" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '[.[] | {key, type, packageType, description}][:10]'
# → [{"key": "libs-release", "type": "LOCAL", "packageType": "Maven", "description": ""}, ...]

# List only local Docker repositories
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

# Get the latest artifact version in a path
REPO="libs-release"
PATH_IN_REPO="com/example/my-service"
curl -s "$BASE/api/storage/$REPO/$PATH_IN_REPO" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '{repo, path, children: [.children[].uri]}'
# → {"repo": "libs-release", "path": "/com/example/my-service", "children": ["/1.2.0", "/1.2.1", "/1.2.3"]}

# Get artifact metadata / properties for a specific version
curl -s "$BASE/api/storage/$REPO/$PATH_IN_REPO/1.2.3/my-service-1.2.3.jar?properties" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq .
# → {"properties": {"build.name": ["my-service"], "build.number": ["42"], ...}}

# Get storage summary per repository
curl -s "$BASE/api/storageinfo" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  | jq '.repositoriesSummaryList[:5] | [.[] | {repoKey, usedSpaceInBytes, filesCount}]'
# → [{"repoKey": "libs-release", "usedSpaceInBytes": "1073741824", "filesCount": 1234}, ...]

# AQL search — find latest 3 artifacts in a repo modified in last 7 days
curl -s "$BASE/api/search/aql" \
  -H "Authorization: Bearer $ARTIFACTORY_TOKEN" \
  -H "Content-Type: text/plain" \
  -d 'items.find({"repo": "libs-release", "modified": {"$last": "7d"}}).sort({"$desc": ["modified"]}).limit(3)'  \
  | jq '.results | [.[] | {name, path, modified, size}]'
# → [{"name": "my-service-1.2.3.jar", "path": "com/example/my-service/1.2.3", "modified": "2026-03-17T10:00:00.000Z", "size": 8388608}]
```

---

## Notes

- **JFrog Cloud URL format:** `https://{company}.jfrog.io` — the Artifactory API path is always under `/artifactory/`.
- **Self-hosted format:** `https://artifactory.yourcompany.com` — same `/artifactory/` prefix applies.
- **Token generation:** JFrog Platform → top-right user menu → Edit Profile → Identity Tokens → Generate Token. Tokens can be scoped to specific permissions.
- **AQL (Artifactory Query Language)** is the most powerful search interface — use it for complex queries (by date, property, checksum, etc.).
- **No VPN required** for JFrog Cloud. Self-hosted instances commonly require corp VPN.
- **Read-only** — these snippets do not deploy or delete artifacts. Deploy requires `deploy` permission on the target repo.
- **Docker images:** use `/artifactory/api/docker/{repo}/v2/{image}/tags/list` to list tags for a Docker image.
