---
name: m365-copilot-search
auth: sso
description: Microsoft 365 Copilot Search — searches across SharePoint files, calendar events, SharePoint sites, and list items via Microsoft Graph Search API. Use when searching company knowledge in SharePoint, finding files or calendar events, or querying M365 content.
env_vars:
  - M365_SEARCH_TOKEN
---

# Microsoft 365 Copilot Search — SSO

Microsoft 365 Copilot Search (`m365.cloud.microsoft/search`) — searches across SharePoint files, calendar events, SharePoint sites, and list items via Microsoft Graph Search API. Email is searched separately via OWA (requires the Outlook connection).

API docs: [Microsoft Graph Search API](https://learn.microsoft.com/en-us/graph/api/search-query)

**Verified:** Production (`graph.microsoft.com/v1.0/search/query`) — driveItem, event, site, listItem — 2026-03. No VPN required.

---

## Credentials

```bash
# Captured automatically by sso.py — no manual token generation needed.
# M365_SEARCH_TOKEN=<captured by tool_connections/m365-copilot-search/sso.py>
# Token lifetime: ~1h
# Refresh: python3 tool_connections/shared_utils/playwright_sso.py --m365-copilot-search-only
#          OR: python3 tool_connections/m365-copilot-search/sso.py --force
```

---

## Auth

Bearer token captured from `m365.cloud.microsoft/search` page load via Playwright SSO. Azure AD SSO auto-completes on managed Macs (macOS Enterprise SSO extension) in ~30s. On unmanaged machines, complete the login once manually.

```bash
source .venv/bin/activate && python3 tool_connections/m365-copilot-search/sso.py
# → Opens browser → Azure AD SSO → writes M365_SEARCH_TOKEN to .env
```

---

## Verified snippets

```python
from pathlib import Path
env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
import urllib.request, json, ssl

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
tok = env["M365_SEARCH_TOKEN"]

def graph_search(entity_types, query, size=5):
    body = json.dumps({"requests": [{"entityTypes": entity_types,
                                      "query": {"queryString": query},
                                      "from": 0, "size": size}]}).encode()
    req = urllib.request.Request("https://graph.microsoft.com/v1.0/search/query",
        data=body, headers={"Authorization": f"Bearer {tok}",
                            "Content-Type": "application/json"}, method="POST")
    r = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read())
    return r["value"][0]["hitsContainers"][0]

# --- Search files (OneDrive + SharePoint) ---
hc = graph_search(["driveItem"], "product review")
print(f"Files: {hc['total']} hits")
for h in hc["hits"][:3]:
    res = h["resource"]
    print(f"  {res['name']} — {res.get('webUrl','')[:60]}")
# → Files: 12 hits
# →   Q4 Planning Session.pptx — https://yourorg.sharepoint.com/sites/...
# →   Team Onboarding Guide.docx — https://yourorg.sharepoint.com/sites/...

# --- Search calendar events ---
hc = graph_search(["event"], "standup")
print(f"Events: {hc['total']} hits")
for h in hc["hits"][:3]:
    res = h["resource"]
    print(f"  {res['subject']} — {res.get('start',{}).get('dateTime','?')[:16]}")
# → Events: 14 hits
# →   Weekly Team Standup — 2026-03-...
# →   Product Review | Monthly — 2026-03-...

# --- Search SharePoint sites ---
hc = graph_search(["site"], "engineering")
print(f"Sites: {hc['total']} hits")
for h in hc["hits"][:3]:
    res = h["resource"]
    print(f"  {res.get('displayName','?')} — {res.get('webUrl','')[:60]}")
# → Sites: 3 hits
# →   EngTeam — https://yourorg.sharepoint.com/sites/EngTeam

# --- Search SharePoint list items ---
hc = graph_search(["listItem"], "onboarding")
print(f"List items: {hc['total']} hits")
for h in hc["hits"][:3]:
    res = h["resource"]
    print(f"  {res.get('webUrl','?')[:80]}")
# → List items: 27 hits
# →   https://yourorg.sharepoint.com/sites/HR/Lists/Onboarding/...
```

---

## Email search (via Outlook connection — OWA_ACCESS_TOKEN)

Email is NOT covered by M365_SEARCH_TOKEN (Mail.Read scope not granted by this app registration). Use OWA_ACCESS_TOKEN from the Outlook connection:

```python
import urllib.parse
owa_tok = env["OWA_ACCESS_TOKEN"]
q = urllib.parse.quote('"product review"')
url = f"https://outlook.office.com/api/v2.0/me/Messages?%24search={q}&%24top=5&%24select=Subject,ReceivedDateTime,From"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {owa_tok}"})
msgs = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read()).get("value", [])
for m in msgs:
    print(f"  [{m['From']['EmailAddress']['Name']}] {m['Subject'][:60]}")
# → [Alice Smith] Re: Q4 project review notes
# → [Bob Jones] Product review — follow-up items
# If 401: run playwright_sso.py --outlook-only to refresh OWA_ACCESS_TOKEN
```

---

## Notes

- **Token scopes:** M365_SEARCH_TOKEN covers `Files.ReadWrite.All`, `User.Read`, `People.Read` — enough for driveItem, event, site, listItem. Does NOT include Mail.Read, ChannelMessage.Read.All, or ExternalItem.Read.All.
- **Email:** Use OWA_ACCESS_TOKEN (Outlook connection) for email search — always required alongside this connection.
- **Teams chat:** Not available — ChannelMessage.Read.All scope is not granted by this app registration. Returns 403.
- **Copilot connectors (externalItem):** Not available — ExternalItem.Read.All not granted. Returns 403.
- **listItem:** No `name`/`title` field in resource — use `webUrl` + `summary` from the hit.
- **No VPN required.** All endpoints accessible from any network.
- **Refresh:** Token expires in ~1h — run `python3 tool_connections/m365-copilot-search/sso.py --force`.
