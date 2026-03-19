---
name: google-drive-setup
description: Set up Google Drive connection. Playwright browser session (storage_state). No input needed from the user — just run the script and log in once.
---

# Google Drive — Setup

## Auth method: Playwright browser session

Google Drive requires a full browser session (Playwright `storage_state`) rather than a cookie injection, because Google detects raw cookie injection and shows a security warning. The session is saved to `~/.browser_automation/gdrive_auth.json` and is valid for days to weeks.

**What to ask the user:** Nothing. Just run the script — the browser opens and the user logs in to Google once if not already logged in.

---

## Steps

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --gdrive-only
# Opens a browser — log in to Google if prompted (~30s)
# Session saved to ~/.browser_automation/gdrive_auth.json
```

---

## Verify

```python
import sys; sys.path.insert(0, "tool_connections/google-drive")
from google_drive import GDrive
with GDrive() as drive:
    files = drive.list_my_drive()
    print(f"{len(files)} files in My Drive")
    for f in files[:3]:
        print(f"  [{f['type']}] {f['name']}")
# Should list files from your Drive
# If auth error: re-run playwright_sso.py --gdrive-only to refresh the session
```

**Connection details:** `tool_connections/google-drive/connection-browser-session.md`

---

## Refresh

Sessions last days to weeks. When expired (Drive redirects to sign-in):

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --gdrive-only
```
