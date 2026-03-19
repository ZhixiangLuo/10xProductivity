---
name: outlook
auth: sso-session
description: Outlook / Microsoft 365 work account — email, calendar, contacts, people suggestions via Outlook REST API v2.0 and Microsoft Graph. Use when reading mail, checking calendar events, looking up contacts, or finding colleague info for a work Microsoft 365 account.
env_vars:
  - GRAPH_ACCESS_TOKEN
  - OWA_ACCESS_TOKEN
---

# Outlook / Microsoft 365 (Work Account)

Work Outlook access for email, calendar, and contacts via two captured Bearer tokens:

- **Graph token** (`GRAPH_ACCESS_TOKEN`): `graph.microsoft.com` — user profile, people suggestions
- **OWA token** (`OWA_ACCESS_TOKEN`): `outlook.office.com/api/v2.0` — mail folders, messages, calendar, contacts

Both are captured in a single Playwright SSO pass (~30–40s). Token lifetime: ~1h.

> **⚠ Tenant note:** `graph.microsoft.com/v1.0/me/messages` and `/me/mailFolders` return 403 on some tenants (admin policy). Use the OWA REST API (`outlook.office.com/api/v2.0`) for all mail/calendar operations — it returns 200 for the same data.

Env: `GRAPH_ACCESS_TOKEN`, `OWA_ACCESS_TOKEN` (~1h — refresh with `assets/playwright_sso.py --outlook-only`)
API docs: [Outlook REST API v2.0](https://learn.microsoft.com/en-us/previous-versions/office/office-365-api/api/version-2.0/mail-rest-operations)

**Verified:** Production (outlook.office.com + graph.microsoft.com) — MailFolders, Messages, CalendarView, Contacts, /me, /me/people — 2026-03-17. No VPN required. Work Microsoft 365 account (Azure AD SSO). macOS enterprise SSO auto-completes in Playwright Chromium.

---

## Auth setup

Tokens are captured by opening `outlook.office.com` in a headed Playwright browser. On a Workday-managed Mac (or any machine with the Microsoft Enterprise SSO extension), Azure AD login auto-completes in ~30s. On unmanaged machines, complete the login once manually through the browser.

```bash
source .venv/bin/activate
python3 tool_connections/shared_utils/playwright_sso.py --outlook-only
# Opens browser → Azure AD SSO (auto-completes on managed Mac, ~30s)
# Writes GRAPH_ACCESS_TOKEN + OWA_ACCESS_TOKEN to .env
```

The script intercepts two tokens from network requests as the Outlook app loads:
- **Graph token**: from the first `graph.microsoft.com` request (user photo)
- **OWA token**: from `outlook.office.com/owa/startupdata.ashx` (app startup data)

---

## Verify connection

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

# Verify Graph token
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
    headers={"Authorization": f"Bearer {env['GRAPH_ACCESS_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r["displayName"], r["mail"])
# → Alice Smith  alice@yourcompany.com

# Verify OWA token
req = urllib.request.Request("https://outlook.office.com/api/v2.0/me/MailFolders/Inbox?$select=DisplayName,UnreadItemCount",
    headers={"Authorization": f"Bearer {env['OWA_ACCESS_TOKEN']}"})
r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
print(r["DisplayName"], r["UnreadItemCount"])
# → Inbox  42
# If 401: token expired — run playwright_sso.py --outlook-only to refresh
```

---

## Quick-reference snippets (verified)

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
graph_tok = env["GRAPH_ACCESS_TOKEN"]
owa_tok   = env["OWA_ACCESS_TOKEN"]
OWA_BASE  = "https://outlook.office.com/api/v2.0"

def owa_get(path):
    req = urllib.request.Request(f"{OWA_BASE}{path}",
        headers={"Authorization": f"Bearer {owa_tok}", "Accept": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())

def graph_get(path):
    req = urllib.request.Request(f"https://graph.microsoft.com/v1.0{path}",
        headers={"Authorization": f"Bearer {graph_tok}", "Accept": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())

# --- User profile (Graph) ---
me = graph_get("/me")
print(me["displayName"], me["mail"], me["jobTitle"])
# → Alice Smith  alice@yourcompany.com  Senior Engineer

# --- Mail folders (OWA) ---
folders = owa_get("/me/MailFolders?$top=10&$select=DisplayName,UnreadItemCount,TotalItemCount")
for f in folders["value"]:
    print(f["DisplayName"], f["UnreadItemCount"], "/", f["TotalItemCount"])
# → Inbox 5 / 1240
# → Sent Items 0 / 832
# → Archive 0 / 15

# --- Inbox folder details ---
inbox = owa_get("/me/MailFolders/Inbox?$select=Id,DisplayName,UnreadItemCount")
print(inbox["DisplayName"], inbox["UnreadItemCount"])
# → Inbox 5

# --- Recent messages (OWA) ---
msgs = owa_get("/me/MailFolders/Inbox/Messages?$top=5&$orderby=ReceivedDateTime desc"
               "&$select=Subject,ReceivedDateTime,From,IsRead,BodyPreview")
for m in msgs["value"]:
    sender = m["From"]["EmailAddress"]["Name"]
    print(f"[{'READ' if m['IsRead'] else 'UNREAD'}] {m['Subject'][:60]}  from {sender}")
# → [UNREAD] Q1 planning update  from Alice Smith
# → [READ]   Weekly standup notes  from Bob Jones

# --- Calendar events (OWA) — today's meetings ---
import datetime
today = datetime.date.today().isoformat()
tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
events = owa_get(f"/me/CalendarView?startDateTime={today}T00:00:00Z&endDateTime={tomorrow}T00:00:00Z"
                  "&$top=10&$select=Subject,Start,End,Organizer,Attendees")
for e in events["value"]:
    start = e["Start"]["DateTime"][:16].replace("T", " ")
    print(f"{start}  {e['Subject']}")
# → 2026-03-17 14:00  Weekly Sync
# → 2026-03-17 18:30  1:1 with Manager

# --- People suggestions (Graph — who you work with most) ---
people = graph_get("/me/people?$top=5&$select=displayName,emailAddresses,jobTitle")
for p in people["value"]:
    emails = [e["address"] for e in p.get("emailAddresses", [])]
    print(p["displayName"], emails[0] if emails else "")
# → Bob Jones  bob@yourcompany.com
# → Alice Smith  alice@yourcompany.com

# --- Search messages (OWA) ---
results = owa_get("/me/Messages?$search=\"project review\"&$top=5&$select=Subject,ReceivedDateTime,From")
for m in results.get("value", []):
    print(m["Subject"])
# → Q4 project review notes

# --- Specific folder messages ---
# Use folder DisplayName as shortcut: Inbox, SentItems, Drafts, DeletedItems, Archive
msgs = owa_get("/me/MailFolders/SentItems/Messages?$top=5&$orderby=LastModifiedDateTime desc"
               "&$select=Subject,ReceivedDateTime,ToRecipients")
for m in msgs["value"]:
    to = [r["EmailAddress"]["Name"] for r in m.get("ToRecipients", [])]
    print(f"{m['Subject'][:50]}  → {', '.join(to[:2])}")
```

---

## Full API surface (verified working)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `graph.microsoft.com/v1.0/me` | Graph | Current user profile |
| GET | `graph.microsoft.com/v1.0/me/people?$top=N` | Graph | Colleagues you interact with most |
| GET | `outlook.office.com/api/v2.0/me/MailFolders` | OWA | All mail folders |
| GET | `outlook.office.com/api/v2.0/me/MailFolders/Inbox` | OWA | Inbox with unread count |
| GET | `outlook.office.com/api/v2.0/me/MailFolders/{name}/Messages` | OWA | Messages in folder |
| GET | `outlook.office.com/api/v2.0/me/Messages?$search="..."` | OWA | Full-text search across all mail |
| GET | `outlook.office.com/api/v2.0/me/CalendarView?startDateTime=...&endDateTime=...` | OWA | Calendar events in date range |
| GET | `outlook.office.com/api/v2.0/me/Contacts` | OWA | Contacts |

---

## Notes

- **OWA API deprecation:** `outlook.office.com/api/v2.0` is the "Outlook REST API" (legacy) but still fully functional as of 2026-03. Microsoft Graph (`graph.microsoft.com/v1.0/me/messages`) is the preferred API but requires `Mail.Read` consent which may be blocked by tenant policy. Use OWA v2.0 as the reliable fallback.
- **Token sources:** Graph token comes from the `graph.microsoft.com/v1.0/users/{upn}/photo/$value` request fired by the Outlook app header. OWA token comes from `outlook.office.com/owa/startupdata.ashx?app=Mail`. Both fire within seconds of the app loading.
- **Folder name shortcuts:** `Inbox`, `SentItems`, `Drafts`, `DeletedItems`, `JunkEmail`, `Archive` work as well-known folder names without needing to look up folder IDs.
- **Graph mail 403:** If `graph.microsoft.com/v1.0/me/messages` returns 403, it's a tenant policy — use OWA v2.0 instead. Graph `/me` and `/me/people` are not affected.
- **No VPN required:** All endpoints accessible from any network.
