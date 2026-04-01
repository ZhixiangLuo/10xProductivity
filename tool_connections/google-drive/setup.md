---
name: google-drive-setup
description: Set up Google Drive connection. Hybrid approach — Google Drive for Desktop (local filesystem, no auth) + Playwright daemon (for reading Google Docs/Sheets/Slides content). No OAuth2, no GCP project, no admin approval needed.
---

# Google Drive — Setup

## Auth approach: local filesystem (primary) + Playwright session (for content)

**No OAuth2 app, no GCP project, no admin approval needed.**

Two components:

| Component | What it does | Auth required |
|-----------|-------------|---------------|
| Google Drive for Desktop | Mounts Drive as local filesystem — list, search, read non-Google files | None (uses your existing Workspace login) |
| Playwright daemon (`gdrive_server.py`) | Reads Google Docs/Sheets/Slides content, searches cloud-only/shared files | Browser SSO session (~7 day lifetime) |

---

## Step 1: Install Google Drive for Desktop

Download and install: https://www.google.com/drive/download/

Sign in with your Google account. Drive will mount at:
```
~/Library/CloudStorage/GoogleDrive-<your-email>/
```

Verify:
```bash
ls ~/Library/CloudStorage/
# → GoogleDrive-you@example.com/
```

---

## Step 2: Capture browser session (once)

```bash
source .venv/bin/activate
python3 tool_connections/google-drive/sso.py --force
# Browser opens — log in to Google Drive (~30s)
# Session saved to ~/.browser_automation/gdrive_auth.json
```

---

## Step 3: Start the daemon

```bash
nohup .venv/bin/python3 tool_connections/google-drive/gdrive_server.py start > /dev/null 2>&1 &
# → Browser window opens and stays open — minimize it, don't close it
# → All agent calls reuse this browser session — no repeated auth
```

Check status:
```bash
python3 tool_connections/google-drive/gdrive_server.py status
# → Running (pid 12345)
```

---

## Verify

```python
import sys
sys.path.insert(0, "tool_connections/google-drive")
from google_drive import GDriveLocal

local = GDriveLocal()

# Local listing (no browser)
files = local.list_folder("My Drive")
print(f"{len(files)} files in My Drive")
for f in files[:3]:
    print(f"  [{f['type']}] {f['name']}")

# Smart search (local → online fallback)
results = local.smart_search("meeting notes")
print(f"Found {len(results)} results")

# Read a Google Doc (requires daemon)
if results:
    file_id, ftype = local.get_id_and_type(results[0]["path"])
    content = local.drive.read(file_id, ftype)
    print(content[:200])
```

**Connection details:** `tool_connections/google-drive/connection-local-filesystem.md`

---

## Refresh (when session expires, ~7 days)

```bash
# 1. Re-authenticate
python3 tool_connections/google-drive/sso.py --force

# 2. Restart the daemon
python3 tool_connections/google-drive/gdrive_server.py stop
nohup .venv/bin/python3 tool_connections/google-drive/gdrive_server.py start > /dev/null 2>&1 &
```

---

## Daemon notes

- The daemon keeps one browser window open — **minimize it, don't close it**
- It survives terminal/Cursor restarts (started with `nohup`)
- It does NOT survive a Mac reboot — restart it after reboot (or it auto-starts on first use, adding ~10s)
- Log: `~/.browser_automation/gdrive_server.log`
