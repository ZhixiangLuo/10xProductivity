---
tool: miro
type: api-patterns
description: Verified Miro internal API patterns — endpoints, board content extraction, widget schema. Uses internal miro.com/api/v1/ (no OAuth needed). Read before writing any Miro API code.
updated: 2026-03-31
---

# Miro API — Verified Patterns

## Critical: Use the internal `miro.com/api/v1/` API, NOT `api.miro.com/v2/`

The official REST API (`api.miro.com/v2/`) requires OAuth app registration. The internal API uses the same `token` session cookie the browser uses — no app needed.

```python
from pathlib import Path
import urllib.request, json, ssl, urllib.parse, re, html

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

HEADERS = {"Cookie": f"token={env['MIRO_TOKEN']}", "Accept": "application/json"}
BASE = "https://miro.com/api/v1"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

def miro_get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=20)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:500]}
```

---

## Verified endpoints

### `GET /users/me/` — current user
```python
r = miro_get("/users/me/")
# → {"name": "...", "email": "...", "lastKnownOrgId": "..."}
```

### `GET /recent-boards` — recently viewed boards
```python
boards = miro_get("/recent-boards")
# Returns a LIST directly (not {"data": [...]})
for b in boards:
    print(b["id"], b["title"])
```

### `GET /boards/{board_id}/` — board metadata
```python
board_id = urllib.parse.quote("BOARD_ID_HERE=", safe="")
board = miro_get(f"/boards/{board_id}/")
print(board["title"], board["description"])
```

### `GET /boards/{board_id}/frames` — list frames with titles and positions
```python
board_id = urllib.parse.quote(env["MIRO_BOARD_ID"], safe="")
frames = miro_get(f"/boards/{board_id}/frames")
# {"total": N, "data": [{"id": "...", "title": "Frame name", ...}, ...]}
for f in frames["data"]:
    print(f["id"], f["title"])
```

---

## ⚠ Critical: `GET /boards/{id}/widgets/` does NOT return content

The widgets list endpoint returns only `id`, `updatedAt`, `createdAt` — no text, no type, no position. Filtering by `?widgetType=X` is silently ignored.

**The correct endpoint for board content is `/content`:**

```python
board_id = urllib.parse.quote(env["MIRO_BOARD_ID"], safe="")
r = miro_get(f"/boards/{board_id}/content")
widgets = r["content"]["widgets"]  # list of all widget objects
```

---

## Widget schema from `/content`

Each widget:
```json
{
  "id": "...",
  "canvasedObjectData": {
    "type": "shape",
    "json": "(nested JSON string — must be parsed separately)"
  },
  "objectHistoryData": { "creationTime": "...", "lastChangeTime": "..." }
}
```

Widget types: `shape`, `sticker`, `frame`, `line`, `image`

Parsing the inner JSON:
```python
def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

for w in widgets:
    cod = w["canvasedObjectData"]
    raw = cod.get("json", "")
    if not raw:
        continue
    data = json.loads(raw)

    text = strip_html(data.get("text", ""))  # HTML — use strip_html()
    pos = data.get("_position", {}).get("offsetPx", {})
    x, y = pos.get("x", 0), pos.get("y", 0)
    parent = data.get("_parent")  # None or {"id": "frame_id"}
    size = data.get("size")       # {"width": ..., "height": ...}
```

---

## Mapping widgets to frames

Frame membership comes from `_parent` in the inner JSON — **not** from position overlap.

```python
# Step 1: build titled frame lookup (titles are in /frames, not in /content)
titled = {f["id"]: f["title"]
          for f in miro_get(f"/boards/{board_id}/frames")["data"]}

# Step 2: group widgets by frame
frame_contents = {}
for w in widgets:
    cod = w["canvasedObjectData"]
    if cod["type"] not in ("shape", "sticker"):
        continue
    raw = cod.get("json", "")
    if not raw:
        continue
    data = json.loads(raw)
    text = strip_html(data.get("text", ""))
    if not text:
        continue
    parent = data.get("_parent")
    parent_id = parent["id"] if isinstance(parent, dict) else parent
    frame_name = titled.get(str(parent_id), "Main canvas") if parent_id else "Main canvas"
    pos = data.get("_position", {}).get("offsetPx", {})
    frame_contents.setdefault(frame_name, []).append({
        "type": cod["type"], "text": text,
        "x": pos.get("x", 0), "y": pos.get("y", 0),
    })

# Step 3: print sorted by position (y then x = top-to-bottom, left-to-right)
for frame_name, items in frame_contents.items():
    print(f"\n=== {frame_name} ===")
    for item in sorted(items, key=lambda i: (i["y"], i["x"])):
        print(f"  [{item['type']}] {item['text']}")
```

---

## Board IDs

Miro board IDs in URLs are base64 strings (e.g. `uXjVG2SvynI=`). URL-encode the `=` when using in API paths:

```python
board_id = urllib.parse.quote(env["MIRO_BOARD_ID"], safe="")
# "uXjVG2SvynI=" → "uXjVG2SvynI%3D"
```

---

## Confirmed 404 / non-functional endpoints

```
GET /boards/{id}/widgets/{widget_id}   ← individual widget by ID returns 404
GET /boards/{id}/items                 ← 404
GET /boards/{id}/cards, /texts, /shapes, /stickynotes  ← all 404
GET /boards/{id}/export, /data         ← 404
GET /boards/{id}/widgets/?widgetType=X ← filter silently ignored; stubs only
api.miro.com/v2/ with session token    ← 401 (requires OAuth Bearer)
miro.com/api/v2/                       ← 404
```

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `401` | Session token expired | Re-run SSO script to refresh `MIRO_TOKEN` |
| `403` on board | No view access to that board | User must grant access in Miro |
| Widget content empty | Using `/widgets/` instead of `/content` | Switch to `/boards/{id}/content` |
| Frame title `None` in content | Titles not in content endpoint JSON | Cross-reference with `/boards/{id}/frames` |
| Widget text is raw HTML | `text` field contains `<p>`, `<mark>` etc. | Apply `strip_html()` helper |
