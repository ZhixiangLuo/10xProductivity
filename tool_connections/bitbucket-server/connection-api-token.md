---
name: bitbucket-server
auth: api-token
description: Bitbucket Server / Data Center — self-hosted Git repository manager. Use when browsing projects and repos, reading file content, listing branches or commits, or searching repos by name.
env_vars:
  - BITBUCKET_TOKEN
  - BITBUCKET_BASE_URL
---

# Bitbucket Server / Data Center — API token (Bearer auth)

Bitbucket Server (now Bitbucket Data Center) is Atlassian's self-hosted Git repository manager. Organizes repos into projects, each identified by a short key. The REST API exposes browsing, search, branches, commits, and file content. This file covers **Server/Data Center** — distinct from Bitbucket Cloud (`bitbucket.org`), which uses a different API and OAuth2.

API docs: https://developer.atlassian.com/server/bitbucket/rest/

**Verified:** Production (Bitbucket Data Center 8.x) — `/profile/recent/repos` + `/projects` + `/projects/{key}/repos` + `/repos/{slug}/branches` + `/repos/{slug}/commits` — 2026-03. No VPN required (depends on your instance network policy).

---

## Credentials

```bash
# Add to .env:
# BITBUCKET_TOKEN=your-personal-access-token
# BITBUCKET_BASE_URL=https://bitbucket.yourcompany.com
#
# Generate token: Bitbucket → top-right user icon → Manage account → Personal access tokens → Create token
# Scopes: Project read + Repository read (add write/admin if needed)
# Token management: {BITBUCKET_BASE_URL}/plugins/servlet/access-tokens/manage
```

---

## Auth

Bearer token in the `Authorization` header:

```bash
source .env
BASE="$BITBUCKET_BASE_URL/rest/api/1.0"
# Usage: -H "Authorization: Bearer $BITBUCKET_TOKEN"
```

---

## Verify connection

```bash
source .env
BASE="$BITBUCKET_BASE_URL/rest/api/1.0"

curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/profile/recent/repos?limit=3" \
  | jq '.values[] | {slug, name, project: .project.key}'
# → [{"slug": "my-repo", "name": "My Repo", "project": "MYPROJ"}, ...]
# If 401: token wrong or expired. If 403: token lacks read scope.
```

---

## Verified snippets

```bash
source .env
BASE="$BITBUCKET_BASE_URL/rest/api/1.0"

# Recently accessed repos (personal history — good starting point)
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/profile/recent/repos?limit=5" \
  | jq '.values[] | {slug, name, project: .project.key}'
# → [{"slug": "my-repo", "name": "My Repo", "project": "MYPROJ"}, ...]

# List projects (each has a short key used in all other API calls)
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects?limit=10" \
  | jq '.values[] | {key, name}'
# → [{"key": "MYPROJ", "name": "My Project"}, {"key": "PLATFORM", "name": "Platform Team"}, ...]

# List repos in a project
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects/{PROJECT_KEY}/repos?limit=20" \
  | jq '.values[] | {slug, name}'
# → [{"slug": "my-repo", "name": "My Repo"}, {"slug": "another-repo", "name": "Another Repo"}, ...]

# Search repos by name keyword
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/repos?name={keyword}&limit=10" \
  | jq '.values[] | {slug, name, project: .project.key}'
# → [{"slug": "my-keyword-repo", "name": "My Keyword Repo", "project": "MYPROJ"}, ...]

# List directory contents in a repo
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects/{PROJECT_KEY}/repos/{repo-slug}/browse" \
  | jq '.children.values[] | {path: .path.toString, type}'
# → [{"path": "README.md", "type": "FILE"}, {"path": "src", "type": "DIRECTORY"}, ...]

# Read a file (returns lines array)
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects/{PROJECT_KEY}/repos/{repo-slug}/browse/{path/to/file.txt}" \
  | jq -r '.lines[].text'
# → (file content, one line per entry)

# Get raw file content (plain text directly)
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects/{PROJECT_KEY}/repos/{repo-slug}/raw/{path/to/file.txt}"
# → (raw file text)

# List branches
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects/{PROJECT_KEY}/repos/{repo-slug}/branches?limit=10" \
  | jq '.values[] | {displayId, latestCommit: .latestCommit[:8]}'
# → [{"displayId": "main", "latestCommit": "a1b2c3d4"}, {"displayId": "develop", "latestCommit": "e5f6a7b8"}, ...]

# Get recent commits
curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "$BASE/projects/{PROJECT_KEY}/repos/{repo-slug}/commits?limit=5" \
  | jq '.values[] | {id: .id[:8], message: .message[:60], author: .author.name}'
# → [{"id": "a1b2c3d4", "message": "Fix bug in auth flow", "author": "Alice"}, ...]
```

---

## Python helper

```python
import json, urllib.request, ssl
from pathlib import Path

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
BASE = env["BITBUCKET_BASE_URL"] + "/rest/api/1.0"
HEADERS = {"Authorization": f"Bearer {env['BITBUCKET_TOKEN']}"}

def bb_get(path):
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())

# Recent repos
repos = bb_get("/profile/recent/repos?limit=5")
for r in repos["values"]:
    print(r["name"], r["project"]["key"])
```

---

## Notes

- **Server vs Cloud:** This file is for **Bitbucket Server / Data Center** (`yourcompany.com`). Bitbucket Cloud (`bitbucket.org`) uses OAuth2 and a different API base. Do not mix them.
- **Project key:** Short uppercase identifier (e.g. `MYPROJ`) — not the project name. Find it via `GET /projects`.
- **Pagination:** List endpoints return `isLastPage` and `nextPageStart`. Example loop:
  ```bash
  start=0
  while true; do
    page=$(curl -s -k -H "Authorization: Bearer $BITBUCKET_TOKEN" \
      "$BASE/projects/{KEY}/repos?limit=25&start=$start")
    echo "$page" | jq '.values[].slug'
    isLast=$(echo "$page" | jq '.isLastPage')
    [ "$isLast" = "true" ] && break
    start=$(echo "$page" | jq '.nextPageStart')
  done
  ```
- **-k flag:** Enterprise instances use internal CAs — add `-k` to curl (or configure the cert) if you get SSL errors.
- **Network:** Bitbucket Server is typically internal — VPN may be required.
