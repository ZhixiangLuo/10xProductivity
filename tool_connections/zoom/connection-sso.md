---
tool: zoom
auth: sso-session + nak-bearer + playwright-storage-state
description: Zoom — enterprise Zoom at workday.zoom.us. Three-layer auth: session cookies for /rest/ endpoints; NAK Bearer JWT for /nws/ endpoints; Playwright storage state for docs.zoom.us AI meeting summaries.
env_vars:
  - ZOOM_SSID
  - ZOOM_AID
  - ZOOM_PAGE_AUTH
  - ZOOM_CLUSTER
  - ZOOM_CMS_GUID
  - ZOOM_NAK
storage_state: ~/.browser_automation/zoom_docs_auth.json
---

# Zoom — SSO session

Enterprise Zoom at `workday.zoom.us`. Three-layer auth:

| Layer | What | TTL | Used for |
|---|---|---|---|
| Session cookies | `_zm_ssid`, `zm_aid`, `_zm_page_auth`, `zm_cluster`, `_zm_cms_guid` | days–weeks | `/rest/` endpoints (meeting list, recordings metadata) |
| NAK Bearer | JWT from `POST /nws/common/2.0/nak` | ~2h | `/nws/` endpoints (recording host-list with NAK) |
| Playwright storage state | `~/.browser_automation/zoom_docs_auth.json` | days–weeks | `docs.zoom.us/doc/{docId}` — AI meeting summary full text |

**NAK refreshable without SSO** via `--refresh-nak`. Storage state requires SSO to refresh.

**Verified:** `workday.zoom.us` — recording list (15 recs), AI summary metadata (3), AI summary full text — 2026-03.

---

## Credentials

```bash
# .env keys:
# ZOOM_SSID=aw1_c_...
# ZOOM_AID=...
# ZOOM_PAGE_AUTH=aw1_c_...
# ZOOM_CLUSTER=aw1
# ZOOM_NAK=eyJ0a192...
```

---

## Auth

```python
from pathlib import Path
import urllib.request, json, ssl

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

ZOOM = "https://workday.zoom.us"
NAK = env["ZOOM_NAK"]
SESSION_COOKIE = (
    f"_zm_ssid={env['ZOOM_SSID']}; "
    f"zm_aid={env['ZOOM_AID']}; "
    f"_zm_page_auth={env['ZOOM_PAGE_AUTH']}; "
    f"zm_cluster={env.get('ZOOM_CLUSTER','aw1')}"
)

def zoom_get(url, bearer=None):
    headers = {"Cookie": SESSION_COOKIE, "Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())

def zoom_post(url, body=None, bearer=None):
    headers = {"Cookie": SESSION_COOKIE, "Accept": "application/json",
                "Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url,
        data=json.dumps(body or {}).encode(),
        headers=headers, method="POST")
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())
```

---

## Verified snippets

```python
# List recordings (past meetings with recordings)
r = zoom_post(f"{ZOOM}/nws/recording/1.0/host-list", {}, bearer=NAK)
for rec in r.get("result", {}).get("recordings", []):
    print(rec.get("meetingTopic"), rec.get("meetingStartTimeStr"))

# List AI meeting summaries (metadata)
r = zoom_get(f"{ZOOM}/rest/meeting/host_summary_list")
for s in r.get("result", {}).get("data", []):
    print(s["topic"], s["createTime"], s["docId"])
# → blake / Alex  Mar 24, 2026 02:41 PM  U7JbOdPTTbqAdoqqJez62g
# → Caleb intros blake to dbt semantic models  Mar 24, 2026 02:03 PM  j4B6D1iWQMWWl_tvcGBt5g

# Get full AI meeting summary text (uses Playwright storage state — ~5s per doc)
from personal.zoom.sso import get_summary_text
text = get_summary_text("U7JbOdPTTbqAdoqqJez62g")
# Returns full doc text including Quick recap, Next steps, Summary sections

# User info via docs API
from pathlib import Path
import json, ssl, urllib.request
state = json.loads(Path.home().joinpath(".browser_automation/zoom_docs_auth.json").read_text())
cookie_map = {c["name"]: c["value"] for c in state.get("cookies", []) if "zoom.us" in c["domain"]}
docs_cookie = f"_zm_docs_nak={cookie_map['_zm_docs_nak']}; _zm_ssid={cookie_map['_zm_ssid']}"
# GET https://us01docs.zoom.us/api/user/me with Cookie: docs_cookie

# Refresh NAK without SSO (when ~2h token expires but _zm_ssid is still valid)
from personal.zoom.sso import refresh_nak
new_nak = refresh_nak(env)  # POSTs to /nws/common/2.0/nak with session cookies
```

---

## Refresh

```bash
# Refresh NAK only (~2h expiry) — no SSO needed:
source .venv/bin/activate
python3 personal/zoom/sso.py --refresh-nak

# Full SSO refresh (when _zm_ssid expires — days/weeks):
python3 personal/zoom/sso.py --force
# Okta SSO auto-completes on managed Workday machine
```

---

## Notes

- `_zm_ssid` is the master session cookie — when this expires, full SSO required
- `_zm_page_auth` is a per-page auth token — same lifetime as `_zm_ssid`
- NAK token is obtained from `POST workday.zoom.us/nws/common/2.0/nak` using session cookies (~2h TTL)
- `/rest/` endpoints work with cookies only — no Bearer needed
- `docs.zoom.us` requires Playwright storage state (NOT cookie injection) — uses `_zm_docs_nak` cookie stored in state
- AI summary full text is at `docs.zoom.us/doc/{docId}` (React SPA), not via REST API
- `docs.zoom.us/api/` endpoints work with `_zm_docs_nak` cookie (no Bearer header needed)
- Storage state: `~/.browser_automation/zoom_docs_auth.json` (gitignored, saved during SSO)
- `zm_cluster=aw1` — US West cluster for Workday's Zoom account
