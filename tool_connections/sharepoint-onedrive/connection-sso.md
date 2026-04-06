---
name: sharepoint-onedrive
auth: sso
description: SharePoint and OneDrive for Business via Microsoft Graph API — list, read, upload, delete files; search across OneDrive + SharePoint; read Word and Excel files locally. Reuses TEAMS_ENTERPRISE_GRAPH_TOKEN, no additional auth needed.
env_vars:
  - TEAMS_ENTERPRISE_GRAPH_TOKEN
---

# SharePoint / OneDrive — SSO (MSAL token via Teams Enterprise)

Microsoft SharePoint and OneDrive for Business via Microsoft Graph API. Reuses the `TEAMS_ENTERPRISE_GRAPH_TOKEN` captured by the Teams Enterprise SSO script — no additional auth needed if that connection is already set up.

API docs: https://learn.microsoft.com/en-us/graph/api/resources/onedrive

**Verified:** Production (graph.microsoft.com, M365 Business Basic) — OneDrive list/read/upload/delete, file search, SharePoint root site + document libraries — 2026-04. No VPN required.

---

## Credentials

```bash
# Reuses TEAMS_ENTERPRISE_GRAPH_TOKEN — no additional setup if microsoft-teams-enterprise is connected.
# If not yet set up: python3 tool_connections/microsoft-teams-enterprise/sso.py
# TTL: ~1h. Refresh: python3 tool_connections/microsoft-teams-enterprise/sso.py
```

---

## Auth

Same MSAL Graph token used for Teams Enterprise. The token covers `Files.ReadWrite.All` and `Sites.ReadWrite.All` scopes.

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json

TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me/drive",
    headers={"Authorization": f"Bearer {TOKEN}"})
r = json.loads(urllib.request.urlopen(req, timeout=10).read())
print(r["driveType"], r["name"], r["quota"]["used"], "bytes used")
# → business  OneDrive  109889 bytes used
```

---

## Verified snippets

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, urllib.error

TOKEN = env["TEAMS_ENTERPRISE_GRAPH_TOKEN"]
GRAPH = "https://graph.microsoft.com"

def gget(path, ver="v1.0"):
    req = urllib.request.Request(f"{GRAPH}/{ver}{path}",
        headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

def gpost(path, body, ver="v1.0"):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{GRAPH}/{ver}{path}", data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except: return e.code, {}

# --- List OneDrive root folder ---
code, r = gget("/me/drive/root/children?$top=10")
for item in r.get("value", []):
    kind = "folder" if "folder" in item else "file"
    print(f"[{kind}] {item['name']}  id={item['id']}")
# → [folder] Documents
# → [folder] Recordings
# → [file] report.docx  id=01YWZM5INDR7NCJ6PG5TBBCEQFW2PYOJZC

# --- Get file metadata + download URL ---
FILE_ID = "01YWZM5INDR7NCJ6PG5TBBCEQFW2PYOJZC"
code, r = gget(f"/me/drive/items/{FILE_ID}")
print(r["name"], r["size"], "bytes")
dl_url = r["@microsoft.graph.downloadUrl"]
# → report.docx 11398 bytes

# --- Download file content ---
content = urllib.request.urlopen(dl_url, timeout=15).read()
print(len(content), "bytes downloaded")
# → 11398 bytes downloaded

# --- Search files in OneDrive ---
code, r = gget("/me/drive/root/search(q='report')?$top=5")
for item in r.get("value", []):
    print(item["name"], item.get("size", "?"), "bytes")
# → report.docx 11398 bytes

# --- Search across OneDrive + SharePoint (Graph search) ---
code, r = gpost("/search/query",
    {"requests": [{"entityTypes": ["driveItem"], "query": {"queryString": "report"},
                   "from": 0, "size": 5}]}, ver="beta")
hits = r.get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])
for h in hits:
    print(h.get("resource", {}).get("name", "?"), h.get("summary", "")[:60])
# → report.docx  <c0>report</c0> <ddd/>

# --- Upload a file (≤4 MB — simple upload) ---
data = b"Hello from agent"
req = urllib.request.Request(
    f"{GRAPH}/v1.0/me/drive/root:/agent-upload.txt:/content",
    data=data,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "text/plain"},
    method="PUT")
r = json.loads(urllib.request.urlopen(req, timeout=15).read())
print(r["id"], r["name"], r["size"])
# → 01YWZM5INBIWNVHG6PMKNCJ5QD74ETXDNFZ  agent-upload.txt  16

# --- Delete a file ---
req = urllib.request.Request(
    f"{GRAPH}/v1.0/me/drive/items/{r['id']}",
    headers={"Authorization": f"Bearer {TOKEN}"},
    method="DELETE")
resp = urllib.request.urlopen(req, timeout=10)
print(resp.status)
# → 204

# --- List SharePoint root site document libraries ---
code, r = gget("/sites/root/drives")
for d in r.get("value", []):
    print(d["name"], d["driveType"], d["id"])
# → Documents  documentLibrary  b!sRz49QZgUk6f26QbQsXf4pJxgoDa_nlHqxauJXZOl3u6_kUSI3qvTZ

# --- What does NOT work ---
# GET /me/followedSites → 403 (Sites.Follow not in scope)
```

---

## Working with Office files

Download `.docx` and `.xlsx` files and parse locally — cleaner and more capable than the cell-level workbook API for read use cases.

```python
# Read a Word document
import io
from docx import Document  # pip install python-docx

code, meta = gget(f"/me/drive/items/{FILE_ID}")
docx_bytes = urllib.request.urlopen(meta["@microsoft.graph.downloadUrl"], timeout=15).read()
doc = Document(io.BytesIO(docx_bytes))
text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
print(text[:500])
# → Q2 Roadmap
# → Discussed timeline with Alice. Action items: update spec by Friday, share draft with team.

# Read an Excel spreadsheet
import openpyxl  # pip install openpyxl

XLSX_ID = "01YWZM5INFTO752AMUAIREITAQWMWJ7PG5F"
code, meta = gget(f"/me/drive/items/{XLSX_ID}")
xlsx_bytes = urllib.request.urlopen(meta["@microsoft.graph.downloadUrl"], timeout=15).read()
wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
ws = wb.active
for row in ws.iter_rows(values_only=True):
    print(row)
# → ('Name', 'Score')
# → ('Alice', 95)

# ⚠ Close the file in the browser before re-uploading — open files return 423 Locked.
```

---

## API surface

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/v1.0/me/drive` | ✅ | OneDrive info + quota |
| GET | `/v1.0/me/drive/root/children` | ✅ | List root folder |
| GET | `/v1.0/me/drive/items/{id}` | ✅ | File metadata + download URL |
| GET | `/v1.0/me/drive/root/search(q='{q}')` | ✅ | Search files in OneDrive |
| PUT | `/v1.0/me/drive/root:/{path}:/content` | ✅ | Upload file ≤4 MB |
| DELETE | `/v1.0/me/drive/items/{id}` | ✅ | Delete file (204) |
| POST | `/beta/search/query` entityType=driveItem | ✅ | Search across OneDrive + SharePoint |
| GET | `/v1.0/sites/root` | ✅ | SharePoint root site |
| GET | `/v1.0/sites/root/drives` | ✅ | SharePoint document libraries |
| GET | `/v1.0/me/followedSites` | ❌ 403 | Sites.Follow not in scope |

---

## Notes

- **No additional auth needed** — reuses `TEAMS_ENTERPRISE_GRAPH_TOKEN` from the Teams Enterprise connection.
- **Upload limit:** simple PUT works for files ≤4 MB. For larger files use the upload session API (`/createUploadSession`).
- **Download:** use the `@microsoft.graph.downloadUrl` field — pre-signed URL valid for ~1h, no auth header needed.
- **Search scope:** `/me/drive/root/search` searches OneDrive only. `/beta/search/query` with `entityType=driveItem` searches across OneDrive + SharePoint.
- **SharePoint site drives:** use `/sites/{site-id}/drives` to list document libraries, then `/drives/{drive-id}/root/children` to browse.
- **Token TTL:** ~1h. Refresh via Teams Enterprise `sso.py`.
- **No VPN required.**
