---
name: google-drive
auth: browser-session
description: Google Drive via Playwright storage_state session — no OAuth app needed. Use when you need to list, search, read, or export files from Google Drive. Supports listing My Drive, searching by keyword/owner, and exporting Google Docs/Sheets/Slides as text/CSV.
env_vars: []
auth_file: ~/.browser_automation/gdrive_auth.json
---

# Google Drive

No OAuth app or admin approval needed — access is via a saved Playwright browser session, using `storage_state` to persist the Google Workspace SSO cookie bundle.

**Auth notes:**
- Google cookies are tied to the browser fingerprint — raw cookie injection triggers `CookieMismatch`. Must use Playwright's `storage_state` to replay the full session.
- Cookie lifetime: days to weeks. Re-run `--gdrive-only` only when you get auth errors.
- Requires a headed browser (macOS enterprise SSO only fires with a UI context).

Auth file: `~/.browser_automation/gdrive_auth.json` (Playwright storage_state snapshot)
Refresh: `python3 tool_connections/shared_utils/playwright_sso.py --gdrive-only`
Asset: `assets/google_drive.py` — importable `GDrive` class; use instead of writing boilerplate

## Verify connection

```python
import sys; sys.path.insert(0, "tool_connections/google-drive")
from google_drive import GDrive
with GDrive() as drive:
    files = drive.list_my_drive()
    print(f"{len(files)} files in My Drive")
    for f in files[:3]:
        print(f"  [{f['type']}] {f['name']}")
# Should list 3 files from your Drive
# If you see an auth error: re-run playwright_sso.py --gdrive-only to refresh the session.
```

---

## Quick start (use the asset — no boilerplate)

```python
import sys
sys.path.insert(0, "tool_connections/google-drive")
from google_drive import GDrive

with GDrive() as drive:
    results = drive.search("meeting notes")       # search by keyword
    files   = drive.list_my_drive()               # My Drive root
    folder  = drive.list_folder(folder_id)        # specific folder
    content = drive.read(file_id, "document")     # export Doc as plain text
    csv     = drive.read(file_id, "spreadsheet")  # export Sheet as CSV
    notes   = drive.read(file_id, "presentation") # export Slides as text

    # Write to a specific cell (row, col are 1-indexed)
    drive.write_sheet_cell(sheet_id, row=10, col=2, value="new value")

    # Find a row by value and write to it (safer than hardcoding row numbers)
    row = drive.find_row_and_write(
        sheet_id,
        search_col=1, search_value="target value",
        write_col=2,  write_value="new value",
    )
```

**Write rule:** Always use `find_row_and_write` when writing to a sheet whose row layout may change. Only use `write_sheet_cell` when you know the exact row from a prior read.

CLI (from the assets folder):
```bash
python3 google_drive.py search "keyword"
python3 google_drive.py ls
python3 google_drive.py read <file_id> document
```

---

## Setup (once, or when session expires)

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --gdrive-only
```

Browser opens → Google Workspace SSO completes → session saved to `~/.browser_automation/gdrive_auth.json`.

---

## Core helper functions

```python
import re, time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

AUTH_FILE = Path.home() / ".browser_automation" / "gdrive_auth.json"

_ID_PATTERNS = [
    r"/document/d/([a-zA-Z0-9_-]{20,})",
    r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})",
    r"/presentation/d/([a-zA-Z0-9_-]{20,})",
    r"/file/d/([a-zA-Z0-9_-]{20,})",
    r"/folders/([a-zA-Z0-9_-]{20,})",
]

def _extract_id(link: str) -> str | None:
    for pat in _ID_PATTERNS:
        m = re.search(pat, link)
        if m: return m.group(1)
    return None

def _infer_type(link: str) -> str:
    if "/document/d/"     in link: return "document"
    if "/spreadsheets/d/" in link: return "spreadsheet"
    if "/presentation/d/" in link: return "presentation"
    if "/folders/"        in link: return "folder"
    return "file"

def gdrive_extract_files(page) -> list[dict]:
    """
    Extract file list from current Drive page DOM.
    Returns list of {id, name, type} where id is the full 44-char file ID.

    IMPORTANT: data-id attributes in the DOM are truncated (~30 chars).
    This function uses href attributes to get the full ID.
    """
    raw = page.evaluate("""() => {
        const files = []; const seen = new Set();
        document.querySelectorAll('[data-id]').forEach(el => {
            const dataId = el.getAttribute('data-id') || '';
            const name = el.querySelector('[data-tooltip]')?.getAttribute('data-tooltip')
                       || el.getAttribute('data-tooltip') || '';
            const links = Array.from(el.querySelectorAll('a[href]'))
                .map(a => a.getAttribute('href')).filter(Boolean);
            files.push({ dataId, name: name.trim(), links });
        });
        return files;
    }""")
    suffixes = {
        "Google Docs": "document", "Google Sheets": "spreadsheet",
        "Google Slides": "presentation", "Google Forms": "form",
        "Shared folder": "folder", "Folder": "folder",
    }
    result = []; seen = set()
    for f in raw:
        best_id = f["dataId"]; best_link = ""
        for link in f["links"]:
            fid = _extract_id(link)
            if fid and len(fid) > len(best_id):
                best_id = fid; best_link = link
        if not best_id or len(best_id) < 15 or best_id in seen: continue
        seen.add(best_id)
        ftype = _infer_type(best_link) if best_link else "file"
        clean = f["name"]
        for suffix, t in suffixes.items():
            if f["name"].endswith(suffix):
                clean = f["name"][:-len(suffix)].strip()
                if ftype == "file": ftype = t
                break
        result.append({"id": best_id, "name": clean, "type": ftype})
    return result


def gdrive_search(page, query: str) -> list[dict]:
    """
    Search Drive by navigating to the search URL.
    query: plain text, or Drive search operators:
      owner:me          — files you own
      'meeting notes'   — exact phrase
    """
    import urllib.parse
    try:
        page.goto(f"https://drive.google.com/drive/search?q={urllib.parse.quote(query)}",
                  wait_until="networkidle", timeout=30_000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)
    return gdrive_extract_files(page)


def gdrive_export(page, file_id: str, file_type: str) -> str:
    """
    Export a Google file and return its text content.
    file_type: 'document' → plain text, 'spreadsheet' → CSV, 'presentation' → text
    """
    urls = {
        "document":     f"https://docs.google.com/document/d/{file_id}/export?format=txt",
        "spreadsheet":  f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv",
        "presentation": f"https://docs.google.com/presentation/d/{file_id}/export/txt",
    }
    url = urls.get(file_type, "")
    if not url:
        return f"(unsupported type: {file_type})"

    with page.expect_download(timeout=25_000) as dl_info:
        try:
            page.goto(url, wait_until="commit", timeout=10_000)
        except Exception:
            pass

    download = dl_info.value
    content = Path(download.path()).read_text(errors="replace")
    return content
```

---

## Usage pattern (open browser once, do all operations)

```python
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,   # must be headed — Google Workspace SSO requires it
        args=["--window-size=1400,900"],
    )
    ctx = browser.new_context(
        storage_state=str(AUTH_FILE),
        ignore_https_errors=True,
        accept_downloads=True,
    )
    page = ctx.new_page()

    try:
        page.goto("https://drive.google.com/drive/my-drive", wait_until="networkidle", timeout=45_000)
    except PlaywrightTimeout:
        pass
    time.sleep(2)

    # List My Drive
    files = gdrive_extract_files(page)
    for f in files[:10]:
        print(f"  [{f['type']:<14}] {f['name']}")

    # Search
    results = gdrive_search(page, "project proposal")

    # Export a Google Doc as text
    docs = [f for f in results if f["type"] == "document"]
    if docs:
        text = gdrive_export(page, docs[0]["id"], "document")
        print(text[:500])

    browser.close()
```

---

## Search query syntax

| Goal | query string |
|------|-------------|
| Keyword in name | `meeting notes` |
| Files you own | `owner:me` |
| Files by a specific person | `owner:alice@example.com` |
| Files shared with you | `sharedwith:me` |
| Combine keyword + owner | `owner:me project proposal` |

---

## File types

| Drive shows | type value | Export format |
|-------------|-----------|---------------|
| Google Docs | `document` | plain text |
| Google Sheets | `spreadsheet` | CSV |
| Google Slides | `presentation` | text (slide titles + notes) |
| Folders | `folder` | N/A |
| Other (PDF, etc.) | `file` | N/A |

---

## Caveats

- **headless=False required** — Google Workspace SSO only fires in a headed browser.
- **Exports do NOT go to ~/Downloads** — `accept_downloads=True` intercepts downloads to a Playwright temp dir. `download.path()` gives the temp path directly.
- **Session lifetime**: days to weeks. Re-run `playwright_sso.py --gdrive-only` if Drive redirects to sign-in.
- **`data-id` is truncated** — Drive's DOM `data-id` attributes are ~30 chars; the real file ID is 44 chars. Always use `gdrive_extract_files()` which gets the full ID from the href.
- **Export requires access** — `gdrive_export()` only works for files you can open. Use `owner:me` search for files guaranteed to export.
- **~51-item render cap per folder** — Drive's virtual DOM only renders ~51 items in the initial viewport. Folders with more items will be undercounted without programmatic scrolling.
