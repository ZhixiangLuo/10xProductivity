---
name: artifactory
auth: api-token
description: JFrog Artifactory — universal artifact repository manager for PyPI, Maven, npm, Docker, and more. Use when finding artifact versions, browsing repos, searching for packages, or downloading build artifacts.
env_vars:
  - ARTIFACTORY_USER
  - ARTIFACTORY_TOKEN
  - ARTIFACTORY_BASE_URL
---

# Artifactory — API token (Basic auth)

JFrog Artifactory is a universal artifact repository manager used to store, manage, and distribute build artifacts — PyPI packages, Maven JARs, npm modules, Docker images, and generic binaries. Common use cases: find the latest version of an internal package, check what artifacts a build produced, download a specific release.

API docs: https://jfrog.com/help/r/jfrog-rest-apis/artifactory-rest-apis

**Verified:** Production (Artifactory Enterprise 7.x) — `/api/system/ping` + `/api/repositories` + `/api/storage/{repo}/{path}` + `/api/search/artifact` — 2026-03. No VPN required (depends on your instance network policy).

---

## Credentials

```bash
# Add to .env:
# ARTIFACTORY_USER=your-username
# ARTIFACTORY_TOKEN=your-api-key-or-token
# ARTIFACTORY_BASE_URL=https://artifactory.yourcompany.com
#
# Generate API key: Artifactory UI → top-right user icon → Edit Profile → Authentication Settings → Generate API Key
# Or (Artifactory 7.21+): Administration → Identity and Access → Access Tokens → Generate Token
```

---

## Auth

Basic auth with base64-encoded `user:token`. Set `AUTH` once per session:

```bash
source .env
AUTH=$(echo -n "$ARTIFACTORY_USER:$ARTIFACTORY_TOKEN" | base64)
BASE="$ARTIFACTORY_BASE_URL"
```

---

## Verify connection

```bash
source .env
AUTH=$(echo -n "$ARTIFACTORY_USER:$ARTIFACTORY_TOKEN" | base64)

curl -s -H "Authorization: Basic $AUTH" \
  "$ARTIFACTORY_BASE_URL/artifactory/api/system/ping"
# → OK
# If 401: wrong user or token. If connection refused: check ARTIFACTORY_BASE_URL.
```

---

## Verified snippets

```bash
source .env
AUTH=$(echo -n "$ARTIFACTORY_USER:$ARTIFACTORY_TOKEN" | base64)
BASE="$ARTIFACTORY_BASE_URL"

# List local repositories (first 5)
curl -s -H "Authorization: Basic $AUTH" \
  "$BASE/artifactory/api/repositories?type=local" \
  | jq '.[:5] | .[] | {key, packageType}'
# → [{"key": "libs-release-local", "packageType": "Generic"}, {"key": "npm-local", "packageType": "Npm"}, ...]

# Browse a package folder (list all versions)
curl -s -H "Authorization: Basic $AUTH" \
  "$BASE/artifactory/api/storage/{repo-key}/{package-name}/" \
  | jq '{repo, path, children: [.children[].uri]}'
# → {"repo": "python-dev", "path": "/my-package", "children": ["/1.0.0", "/1.0.1", "/1.1.0"]}

# Get the latest version (sort children and take the last)
curl -s -H "Authorization: Basic $AUTH" \
  "$BASE/artifactory/api/storage/{repo-key}/{package-name}/" \
  | jq '.children[].uri' | sort -V | tail -1
# → "/1.1.0"

# Get file info for a specific version folder
curl -s -H "Authorization: Basic $AUTH" \
  "$BASE/artifactory/api/storage/{repo-key}/{package-name}/1.1.0/" \
  | jq '{repo, path, children: [.children[].uri]}'
# → {"repo": "python-dev", "path": "/my-package/1.1.0", "children": ["/my_package-1.1.0-py3-none-any.whl", "/my_package-1.1.0.tar.gz"]}

# Search for artifacts by name
curl -s -H "Authorization: Basic $AUTH" \
  "$BASE/artifactory/api/search/artifact?name={artifact-name}&repos={repo-key}" \
  | jq '{results_count: (.results | length), sample: [.results[:3][].uri]}'
# → {"results_count": 2, "sample": ["https://.../{artifact-name}-1.1.0.whl", ...]}

# Download an artifact
curl -s -H "Authorization: Basic $AUTH" \
  "$BASE/artifactory/{repo-key}/{package-name}/1.1.0/my_package-1.1.0.tar.gz" \
  -o my_package.tar.gz
# → downloads to my_package.tar.gz
```

---

## Notes

- **API key vs access token:** Older instances expose a per-user API key under Edit Profile. Artifactory 7.21+ also has scoped Access Tokens (Administration → Identity and Access → Access Tokens). Either works with Basic auth as `user:key`. API keys generated under Edit Profile are non-expiring. Access tokens can have a TTL — check the expiry field when generating.
- **`sort -V`:** Version sort (`sort -V`) handles semver correctly — `1.9.0` before `1.10.0`. Plain `sort` will mis-order.
- **packageType values:** `Generic`, `Maven`, `Gradle`, `Npm`, `PyPI`, `Docker`, `Helm`, `YUM`, `Debian`, etc.
- **SSL:** Enterprise instances often use internal CAs — add `-k` to curl if you see SSL errors.
- **Network:** Most enterprise Artifactory instances are internal-only — VPN may be required.
- **Anonymous read:** Some repos allow anonymous access. If you only need to download public artifacts, skip auth entirely.
