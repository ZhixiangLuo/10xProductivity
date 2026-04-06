---
name: onenote
auth: sso
description: Microsoft OneNote via Graph OneNote API — list notebooks/sections/pages, read page content as HTML (strip for plain text context injection), filter pages by title, create pages. Reuses TEAMS_ENTERPRISE_GRAPH_TOKEN, no additional auth needed.
env_vars:
  - TEAMS_ENTERPRISE_GRAPH_TOKEN
---

# OneNote — SSO (MSAL token via Teams Enterprise)

Microsoft OneNote via the Graph OneNote API. Read notebooks, sections, and page HTML content — useful for pulling notes as context. Reuses `TEAMS_ENTERPRISE_GRAPH_TOKEN` — no additional auth needed if Teams Enterprise is set up.

API docs: https://learn.microsoft.com/en-us/graph/api/resources/onenote-api-overview

**Verified:** Production (graph.microsoft.com, M365 Business Basic) — list notebooks/sections/pages, read page HTML content, filter pages by title, create pages — 2026-04. No VPN required.

---

## Credentials

```bash
# Reuses TEAMS_ENTERPRISE_GRAPH_TOKEN — no additional setup if microsoft-teams-enterprise is connected.
# TTL: ~1h. Refresh: python3 tool_connections/microsoft-teams-enterprise/sso.py
```

---

## Auth

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json

TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me/onenote/notebooks",
    headers={"Authorization": f"Bearer {TOKEN}"})
r = json.loads(urllib.request.urlopen(req, timeout=10).read())
for nb in r["value"]:
    print(nb["displayName"], nb["id"])
# → My Notebook  1-c3d4e5f6-1a2b-3c4d-5e6f-7a8b9c0d1e2f
```

---

## Verified snippets

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, urllib.error, urllib.parse, re

TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]
GRAPH = "https://graph.microsoft.com"

def gget(path, raw=False):
    req = urllib.request.Request(f"{GRAPH}/v1.0{path}",
        headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, (r.read() if raw else json.loads(r.read()))
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

def gpost_html(path, html):
    req = urllib.request.Request(f"{GRAPH}/v1.0{path}",
        data=html.encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "text/html"},
        method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

# --- List notebooks ---
code, r = gget("/me/onenote/notebooks")
for nb in r.get("value", []):
    print(nb["displayName"], nb["id"])
# → My Notebook  1-c3d4e5f6-1a2b-3c4d-5e6f-7a8b9c0d1e2f

# --- List sections ---
code, r = gget("/me/onenote/sections")
for s in r.get("value", []):
    print(s["displayName"], s["id"], s["parentNotebook"]["displayName"])
# → General  1-f7e6d5c4-b3a2-9180-7654-3210fedcba98  My Notebook

# --- List pages (all, across all sections) ---
code, r = gget("/me/onenote/pages?$top=20")
for p in r.get("value", []):
    print(p.get("title", "(untitled)"), p["lastModifiedDateTime"], p["id"])
# → Meeting notes  2026-04-06T01:14:31Z  1-95946a0af3c84f77a9c214168ebf2904!14-f7e6d5c4-b3a2-9180
# → Project ideas  2026-04-06T01:19:51Z  1-467f9035a5264aee96cfd59c219e6916!49-f7e6d5c4-b3a2-9180

# --- List pages in a specific section ---
SECTION_ID = "1-f7e6d5c4-b3a2-9180-7654-3210fedcba98"
code, r = gget(f"/me/onenote/sections/{SECTION_ID}/pages?$top=20")
for p in r.get("value", []):
    print(p.get("title", "(untitled)"), p["lastModifiedDateTime"])
# → Meeting notes  2026-04-06T01:14:31Z
# → Project ideas  2026-04-06T01:19:51Z

# --- Read page content as HTML (primary use: extract text for context) ---
PAGE_ID = "1-95946a0af3c84f77a9c214168ebf2904!14-f7e6d5c4-b3a2-9180-7654-3210fedcba98"
code, html_bytes = gget(f"/me/onenote/pages/{PAGE_ID}/content", raw=True)
html = html_bytes.decode("utf-8")
print(html[:300])
# → <html lang="en-US"><head><title>Meeting notes</title>...</head><body>...</body></html>

# Strip HTML tags for plain text context injection:
text = re.sub(r"<[^>]+>", " ", html).strip()
print(text[:200])
# → Meeting notes  Alice: discussed Q2 roadmap. Action items: ...

# --- Filter pages by title ---
filt = urllib.parse.quote("title eq 'Meeting notes'")
code, r = gget(f"/me/onenote/pages?$filter={filt}&$top=5")
for p in r.get("value", []):
    print(p.get("title"), p["id"])
# → Meeting notes  1-95946a0af3c84f77a9c214168ebf2904!14-f7e6d5c4-b3a2-9180-7654-3210fedcba98

# --- Create a new page in a section ---
html_page = """<!DOCTYPE html>
<html>
<head><title>My note title</title></head>
<body>
<h1>Heading</h1>
<p>Body text here.</p>
</body>
</html>"""
code, r = gpost_html(f"/me/onenote/sections/{SECTION_ID}/pages", html_page)
print(code, r.get("title"), r.get("id"))
# → 201  My note title  1-467f9035a5264aee96cfd59c219e6916!39-f7e6d5c4-b3a2-9180-7654-3210fedcba98

# --- What does NOT work ---
# GET /me/onenote/pages?$search='...' → 400 (not supported — use $filter by title instead)
# POST /beta/search/query entityType=onenotePage → 400 (not supported by Graph)
```

---

## API surface

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/v1.0/me/onenote/notebooks` | ✅ | List notebooks |
| GET | `/v1.0/me/onenote/sections` | ✅ | List all sections across notebooks |
| GET | `/v1.0/me/onenote/pages` | ✅ | List all pages (up to $top) |
| GET | `/v1.0/me/onenote/sections/{id}/pages` | ✅ | List pages in a specific section |
| GET | `/v1.0/me/onenote/pages?$filter=title eq '{title}'` | ✅ | Find pages by exact title |
| GET | `/v1.0/me/onenote/pages/{id}/content` | ✅ | Read page HTML content |
| POST | `/v1.0/me/onenote/sections/{id}/pages` | ✅ | Create a new page (201) |
| GET | `/v1.0/me/onenote/pages?$search='...'` | ❌ 400 | Not supported — use $filter |
| POST | `/beta/search/query` entityType=onenotePage | ❌ 400 | Not supported by Graph |

---

## Notes

- **No additional auth needed** — reuses `TEAMS_ENTERPRISE_GRAPH_TOKEN` from Teams Enterprise.
- **Page content is HTML** — strip tags with `re.sub(r"<[^>]+>", " ", html)` for plain text context injection.
- **No full-text search** — OneNote doesn't support `$search` or Graph search for pages. To find pages: list all via `/pages`, filter by exact title with `$filter=title eq '...'`, or read content of known pages.
- **Create pages** by POSTing HTML to `/sections/{id}/pages`. Title is set via `<title>` in the HTML `<head>`.
- **Token TTL:** ~1h. Refresh via Teams Enterprise `sso.py`.
- **No VPN required.**
