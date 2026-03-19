---
name: outlook-com
auth: api-token
description: Outlook.com — read-only email via OWA REST API v2.0 using OUTLOOK_ACCESS_TOKEN captured by get_outlook_token.py. Use when reading inbox/mail folders, fetching message details, and searching messages for personal Microsoft accounts (outlook.live.com).
env_vars:
  - OUTLOOK_ACCESS_TOKEN
---

# Outlook.com — OWA REST API (outlook.live.com)

Outlook.com (outlook.live.com/mail/) for personal Microsoft accounts.

API base: `https://outlook.office.com/api/v2.0/me/`
API docs: https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview

---

## What works

| Capability | Status | Notes |
|---|---|---|
| Token capture | **Works** | `get_outlook_token.py` — ~15s, no login prompt if session < 24h |
| Read inbox | **Works** | `GET /me/mailfolders/inbox/messages` |
| List mail folders | **Works** | `GET /me/mailfolders` |
| Read `/me` (identity) | **Works** | Returns display name, email address |
| Send email | **Does not work** | Token has insufficient scope — see below |
| Compose via browser UI | **Not attempted fully** | Playwright UI automation hit session expiry timing issues |

---

## What does not work and why

### Send email (403 Forbidden)

The Bearer token captured by `get_outlook_token.py` comes from a request Outlook's page thread makes to `outlook.live.com/imageB2/v1.0/users/.../image/` (profile images). This token is **scoped for read operations only** — it does not include `mail.send` permission.

Attempts to use it against `POST /api/v2.0/me/sendmail` return:
```json
{"error": {"code": "ErrorAccessDenied", "message": "Access is denied."}}
```

**Root cause:** Outlook Live uses different tokens for different operations. The send token is acquired via the service worker (which processes outbound compose requests internally) — invisible to Playwright's page-level CDP `Network.enable`.

**What would fix it:** Intercept the token from inside the service worker. Playwright's `Worker` object does not expose `create_cdp_session()`, so this path is not directly available. The alternative is the Microsoft Graph device code flow (requires Azure app registration).

### Device code flow (first-party client ID blocked)

Attempt: use Outlook's own first-party client ID (`9199bf20-a13f-4107-85dc-02114787ef48`) with Python `msal` device code flow — no Azure app registration needed.

Result: Microsoft blocks device code flow for first-party app IDs when called from external callers. Login attempt failed.

### Browser UI compose + send via Playwright

Attempt: Open Outlook in a Playwright browser, click New mail, fill To/Subject/Body, click Send.

Result: The approach is sound but hit two issues:
1. The saved browser profile session expires in ~24h. When expired, Playwright opens a login page and the script exits without sending.
2. Timing: the script checked `page.url` to detect login completion but the URL matches the inbox path while Outlook's service worker is still booting (shows a loading screen for 5-10s). The "New mail" button didn't exist yet when the script tried to click it.

Both issues are fixable (add `wait_for_selector("button[aria-label='New mail']")` and handle the login wait loop) but not pursued further.

---

## Auth setup (token capture — read operations only)

```bash
python3 tool_connections/outlook/get_outlook_token.py
```

A browser window opens to `outlook.live.com/mail/inbox`. If already logged in (session < ~24h) the token is captured automatically in ~15s. If not, sign in — the script captures the token after login. Result: `OUTLOOK_ACCESS_TOKEN` written to `.env`.

**Token TTL:** ~1 hour. Re-run to refresh. Session TTL: ~24 hours.

---

## Working API calls

### Read inbox

```
GET https://outlook.live.com/api/v2.0/me/mailfolders/inbox/messages
    ?$top=10
    &$select=Subject,From,ReceivedDateTime,IsRead,BodyPreview
    &$orderby=ReceivedDateTime desc
Authorization: Bearer {OUTLOOK_ACCESS_TOKEN}
```

> **Note:** Use `outlook.live.com` as the base, not `outlook.office.com`. The `$orderby` parameter does not sort correctly via the office.com endpoint for this token type — use the live.com base URL and sort client-side if needed.

### Read full email

```
GET https://outlook.live.com/api/v2.0/me/messages/{message_id}
    ?$select=Subject,From,ToRecipients,Body,ReceivedDateTime
Authorization: Bearer {OUTLOOK_ACCESS_TOKEN}
```

### Search

```
GET https://outlook.live.com/api/v2.0/me/messages
    ?$search="from:alice@example.com"
    &$top=10
    &$select=Subject,From,ReceivedDateTime
Authorization: Bearer {OUTLOOK_ACCESS_TOKEN}
```

### List folders

```
GET https://outlook.live.com/api/v2.0/me/mailfolders
    ?$select=DisplayName,UnreadItemCount,TotalItemCount
Authorization: Bearer {OUTLOOK_ACCESS_TOKEN}
```

### Identity check

```
GET https://outlook.live.com/api/v2.0/me
Authorization: Bearer {OUTLOOK_ACCESS_TOKEN}
```

---

## For send capability — future work

Two viable paths, neither implemented:

**Option A — Microsoft Graph device code flow (requires Azure app registration)**

Free, ~5 min setup at portal.azure.com. Register an app, enable `Mail.Send` delegated scope, run device code flow once to get a refresh token. Refresh tokens are long-lived (90 days rolling). This is the clean, supported path.

**Option B — Playwright browser UI automation (no app registration)**

Open Outlook in a Playwright browser with the saved profile. Wait for `button[aria-label='New mail']` to appear (not just the URL), fill To/Subject/Body, click Send. The browser handles auth internally — no token extraction needed. Limitation: requires a live browser session (~24h before re-login).

---

## Notes

- **How token capture works:** Playwright CDP `Network.enable` intercepts HTTP requests on the page thread. Outlook's service worker handles internal caching but the page thread makes direct requests for profile images and config endpoints — these carry a Bearer token visible at the CDP level.
- **Service worker limitation:** `fetch()` calls made by the page's JavaScript are intercepted by `sw.js` before reaching the network. Only requests originating from the browser engine itself (image loads, preload hints) bypass the service worker and are visible to CDP.
- **No Azure app registration needed** for read operations. Required for send.
- **No VPN required.** `outlook.live.com` and `outlook.office.com` are public endpoints.

