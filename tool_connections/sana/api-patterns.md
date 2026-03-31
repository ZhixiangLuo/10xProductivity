---
tool: sana
type: api-patterns
description: Verified tRPC call patterns, endpoint schemas, and search techniques for the Sana Agents API. Read before writing any Sana API code.
updated: 2026-03-31
---

# Sana API — Verified Patterns

## Critical: Use tRPC batch format

**The non-batch `?input={"0": {...}}` format silently fails for most endpoints.**
Always use the batch format with `?batch=1`:

```python
import urllib.request, urllib.parse, json, ssl
from pathlib import Path

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

HEADERS = {
    "Cookie": f"sana-ai-session={env['SANA_SESSION_COOKIE']}",
    "sana-ai-workspace-id": env["SANA_WORKSPACE_ID"],
    "Accept": "application/json",
    "Content-Type": "application/json",
}
BASE = "https://sana.ai/x-api/trpc"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

def trpc_batch_get(procedure, input_data):
    encoded = urllib.parse.quote(json.dumps({"0": input_data}))
    url = f"{BASE}/{procedure}?batch=1&input={encoded}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=20)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode()[:500]}
```

Response is a **list** — data lives at `r[0]["result"]["data"]`, not `r["result"]["data"]`.

---

## Verified endpoints

### `user.me` — current user (GET, no batch needed)
```python
def trpc_get(procedure):
    req = urllib.request.Request(f"{BASE}/{procedure}", headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())

r = trpc_get("user.me")
email = r["result"]["data"]["user"]["email"]
```

### `assistantV2.list` — list AI assistants (GET, no batch needed)
```python
r = trpc_get("assistantV2.list")
for a in r["result"]["data"]:
    print(a["id"], a["name"])
```

### `workspace.list` — list workspaces the user belongs to (batch GET)
```python
r = trpc_batch_get("workspace.list", {})
workspaces = r[0]["result"]["data"]
```

### `searchV2.search` — full-text search across all content types (batch GET)

All three fields in `query` are **required** — omitting any returns a 400 with a zod validation error:

```python
input_data = {
    "query": {
        "text": "your search query",  # string, required
        "webSearch": False,            # boolean, required
        "sourceSearch": True           # boolean, required — True searches internal workspace content
    }
}
r = trpc_batch_get("searchV2.search", input_data)
results = r[0]["result"]["data"]["root"]["children"]
```

Each result has `fields` and `metadata` dicts. Key fields:

| Field | Description |
|---|---|
| `source` | e.g. `"sana-ai:meeting"`, `"sana-ai:file"`, `"sana-learn"` |
| `mimeType` | e.g. `"sana/meeting"`, `"application/pdf"`, `"sana-learn/course"` |
| `assetId` | parent asset ID (multiple fragments share one assetId) |
| `title` | document or meeting title |
| `snippet` | HTML with `<mark>` tags around matched terms (~200 chars) |
| `sequenceId` | fragment order within a parent asset (1-based, lower = earlier) |
| `createdAtEpochMs` | creation timestamp |

---

## Working with meeting transcripts

Meetings are stored as fragmented assets. Each search result is a ~200-char snippet from one fragment. There is no known endpoint to fetch a full transcript directly — reconstruct it from search results.

### Pattern: collect transcript fragments

```python
import re

def get_meeting_fragments(asset_id, queries):
    """Run multiple queries and collect unique fragments from a specific meeting."""
    fragments = {}
    for q in queries:
        r = trpc_batch_get("searchV2.search", {
            "query": {"text": q, "webSearch": False, "sourceSearch": True}
        })
        if not (isinstance(r, list) and "result" in r[0]):
            continue
        for item in r[0]["result"]["data"]["root"]["children"]:
            fields = item.get("fields", {})
            if fields.get("assetId") == asset_id:
                seq = fields.get("sequenceId")
                if seq is not None and seq not in fragments:
                    fragments[seq] = re.sub(r"</?mark>", "", fields.get("snippet", ""))
    return [(seq, snip) for seq, snip in sorted(fragments.items())]
```

### Pattern: snippet iteration to extend a passage

Each search returns a different window (~200 chars) around the matched text. To get the next sentence after a snippet ends, search for the trailing phrase:

```
Snippet ends: "...maybe we're thinking different things. Blake: Oh Josh..."
Next query:   "maybe we're thinking different things blake josh"
→ New window: "...Oh Josh Dixon: So I guess we're just going to have to wait and see..."
```

6–10 varied queries will typically surface most of a relevant passage.

---

## Confirmed 404 endpoints (don't waste time)

These were all tried and return 404 or are otherwise non-functional as of 2026-03:

```
meeting.get          meetingAsset.get      meetingV2.get
meetingTranscript.get  transcriptFragment.list  meetingFragment.list
asset.get            assetV2.get           assetContent.get
asset.list           asset.search
resource.list        resource.search
content.search       knowledge.search
teamspace.list
integrationAsset.list  integrationAsset.search
chatV2.list
globalSearch.search
search.query (POST)
searchV2.search via POST  ← it's a GET query procedure only
/x-api/search        /x-api/meetings       ← REST paths, not tRPC
```

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `401` with no message | Missing `sana-ai-workspace-id` header | Add the header on every request |
| `400 BAD_REQUEST` "expected object, received string" | Passing `query` as a string | Wrap in object: `{"query": {"text": "...", ...}}` |
| `400 BAD_REQUEST` "expected boolean, received undefined" | Missing `webSearch` or `sourceSearch` | Include both boolean fields |
| `405 METHOD_NOT_ALLOWED` | Using POST on a query procedure | Switch to GET with batch format |
| Response at `r["result"]` instead of `r[0]["result"]` | Forgot batch format | Use `?batch=1&input=...` |
