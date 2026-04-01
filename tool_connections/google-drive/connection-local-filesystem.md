---
name: google-drive
auth: local-filesystem + playwright-daemon
description: Google Drive via local filesystem mount (Google Drive for Desktop) + persistent Playwright daemon. No OAuth2, no GCP project, no admin approval. Use for listing, searching, and reading Drive files. Write is not supported.
env_vars: []
auth_file: ~/.browser_automation/gdrive_auth.json
---

# Google Drive

No OAuth2 app or admin approval needed. Two layers:

1. **Google Drive for Desktop** — mounts your Drive at `~/Library/CloudStorage/GoogleDrive-<email>/`. No auth, no tokens, instant file access.
2. **Playwright daemon** (`gdrive_server.py`) — keeps one browser open persistently. All online operations (read content, search cloud-only files) route through it. SSO happens once; no repeated auth prompts.

**Write support:** Not available. Google Docs and Slides have no write path without OAuth2. Sheets keyboard-navigation write exists but is too fragile for production use.

---

## Quick start

```python
import sys
sys.path.insert(0, "tool_connections/google-drive")
from google_drive import GDriveLocal

local = GDriveLocal()

# ── Local operations (no browser, instant) ───────────────────────────────────

# List a folder
files = local.list_folder("My Drive")
# → [{"name": "AI initiative", "path": "My Drive/AI initiative", "type": "folder", "is_stub": False},
#    {"name": "plan.gdoc", "path": "My Drive/plan.gdoc", "type": "document", "is_stub": True}, ...]

# Search synced files (Spotlight/mdfind — filename + content)
results = local.search("sprint capacity")
# → [{"name": "Sprint Capacity Planning.gsheet", "path": "My Drive/Sprint Capacity Planning.gsheet",
#     "type": "spreadsheet", "is_stub": True}]
# → instant, covers synced files only

# Smart search: local Spotlight → cache → online (covers "Shared with me" too)
results = local.smart_search("AI projects")
# → first call: [smart_search] Not found locally — searching online for 'AI projects'...
# →   20 results returned, stubs written to personal/tool_connections/google-drive/bridge_cache/
# → subsequent calls: instant from cache (source: "cache")

# Get file ID from a .gdoc/.gsheet stub
file_id, ftype = local.get_id_and_type("My Drive/plan.gdoc")
# → ("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms", "document")

# Read a non-Google file (txt, csv, md, json, etc.)
content = local.read_file("My Drive/notes.txt")

# ── Online operations (via daemon) ───────────────────────────────────────────

# Read Google Docs/Sheets/Slides content
content = local.drive.read(file_id, "document")
# → "The Enterprise AI Transformation\nWorkday's product vision and strategy..."
csv     = local.drive.read(file_id, "spreadsheet")
# → "Name,Status,Owner\nAIOps,In Progress,alice@example.com\n..."
notes   = local.drive.read(file_id, "presentation")
# → "Slide 1: AI Strategy Overview\nSpeaker notes: ..."

# Search online (covers all of Drive including Shared with me)
results = local.drive.search("project proposal")
results = local.drive.search("owner:me budget")     # files you own
```

---

## What each layer covers

| Operation | Local (GDriveLocal) | Online (GDrive daemon) |
|-----------|--------------------|-----------------------|
| List folder | ✅ instant | ✅ slower |
| Search synced files | ✅ Spotlight, instant | ✅ slower |
| Search "Shared with me" / cloud-only | ✅ via `smart_search()` fallback | ✅ direct |
| Auto-cache online results | ✅ `smart_search()` writes to bridge_cache/ | ✗ |
| Read non-Google files (txt, csv, docx) | ✅ direct | ✗ |
| Get file ID from stub | ✅ no browser | — |
| Read Google Docs content | ✗ stub only | ✅ export |
| Read Google Sheets as CSV | ✗ stub only | ✅ export |
| Read Google Slides as text | ✗ stub only | ✅ export |
| Write | ✗ not supported | ✗ not supported |

---

## Stub file format

`.gdoc`, `.gsheet`, `.gslides` files on the local mount are stubs — metadata only:
```json
{"doc_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms", "email": "you@example.com"}
```

`doc_id` is the Google file ID used in all Drive URLs (`/document/d/<doc_id>/`).
Pass it to `local.drive.read(doc_id, "document")` to export content as plain text.

---

## Bridge cache

`smart_search()` caches online results to `personal/tool_connections/google-drive/bridge_cache/` (gitignored — lives in `personal/` with all other user-specific data) as `.gdrive.json` files. Subsequent searches for the same query return instantly without hitting the network.

```json
{
  "doc_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
  "type": "document",
  "name": "AI Projects Overview",
  "queries": ["AI projects", "ai projects overview"]
}
```

---

## Daemon management

```bash
# Status
python3 tool_connections/google-drive/gdrive_server.py status

# Start (detached — survives terminal close)
nohup .venv/bin/python3 tool_connections/google-drive/gdrive_server.py start > /dev/null 2>&1 &

# Stop
python3 tool_connections/google-drive/gdrive_server.py stop
```

The daemon keeps one browser window open — minimize it, don't close it.
Log: `~/.browser_automation/gdrive_server.log`

---

## Session refresh (~7 days)

```bash
python3 tool_connections/google-drive/sso.py --force
python3 tool_connections/google-drive/gdrive_server.py stop
nohup .venv/bin/python3 tool_connections/google-drive/gdrive_server.py start > /dev/null 2>&1 &
```

---

## Caveats

- **macOS only** — `mdfind` (Spotlight) and the FUSE mount are macOS-specific.
- **`list_folder` / `search` use subprocess**, not Python's `iterdir()`/`glob()` — these block on the FUSE-mounted network filesystem. `ls` and `mdfind` avoid this.
- **Exports do NOT go to `~/Downloads`** — `accept_downloads=True` intercepts to a Playwright temp dir. Content is returned as a string directly.
- **`data-id` is truncated** — Drive's DOM `data-id` attributes are ~30 chars; the real file ID is 44 chars. The asset uses `href` attributes to get the full ID.
- **~51-item render cap** — Drive's virtual DOM renders ~51 items per folder. Folders with more items will be undercounted without programmatic scrolling.
- **Shared files** — files shared with you that aren't synced locally will only appear via `smart_search()` online fallback or `local.drive.search()`.

---

**Verified:** 2026-04-01, macOS 15, Google Workspace account, Google Drive for Desktop 1.91. Tested: `list_folder("My Drive")` (20+ files), `search("AI strategy")` (instant via Spotlight), `smart_search("workday AI strategy")` (20 results via daemon), `read(file_id, "document")` (full doc text returned), `read(file_id, "spreadsheet")` (CSV returned). Daemon start-to-ready ~10s. Auth lifetime ~7 days observed. Session expired error confirmed when `gdrive_auth.json` stale — resolved by re-running `sso.py --force`.
