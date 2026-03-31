---
name: linkedin
auth: session-cookie
description: LinkedIn — personal use via browser session cookie. Read/send messages, create posts, look up your own profile. Uses Voyager API (internal) via Playwright persistent browser profile — no developer app required. Use when reading LinkedIn messages, replying to conversations, creating posts, or fetching your own profile.
env_vars:
  - LINKEDIN_LI_AT
  - LINKEDIN_JSESSIONID
---

# LinkedIn — session cookie (li_at)

LinkedIn for personal use: read messages, reply, make posts, look up your own profile. No developer app required. Uses the `li_at` session cookie extracted from a logged-in browser via Playwright.

API: Voyager (internal) — `https://www.linkedin.com/voyager/api/`

**Verified:** Production (www.linkedin.com) — `/me`, messaging conversations, send message, post creation — 2026-03. No VPN required. Works with any LinkedIn personal account.

---

## Credentials

Setup: `tool_connections/linkedin/setup.md`

```bash
# .env entries (set automatically by sso.py):
LINKEDIN_LI_AT=your-li_at-cookie-value          # long-lived (weeks/months)
LINKEDIN_JSESSIONID=your-jsessionid-value        # CSRF token (~24h, re-captured with sso.py)
```

---

## Auth

All Voyager API calls are made from within a Playwright page context (injecting the cookies), because LinkedIn's bot detection blocks raw `urllib` calls. `JSESSIONID` doubles as the CSRF token (`Csrf-Token` header).

**Important:** Always use the persistent profile (`~/.browser_automation/linkedin_profile/`) so LinkedIn doesn't trigger 2FA on every run.

```python
import sys, time
from pathlib import Path
sys.path.insert(0, "tool_connections")
from shared_utils.browser import sync_playwright, DEFAULT_ENV_FILE, load_env_file

PROFILE_DIR = Path.home() / ".browser_automation" / "linkedin_profile"

def linkedin_page(p):
    """Open a Playwright page pre-authenticated with LinkedIn session cookies."""
    env = load_env_file(DEFAULT_ENV_FILE)
    li_at = env["LINKEDIN_LI_AT"]
    jsession = env["LINKEDIN_JSESSIONID"].strip('"')
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_DIR), headless=False,
        args=["--window-size=1024,768"], ignore_https_errors=True,
    )
    page = ctx.new_page()
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    return ctx, page, jsession
```

---

## Verified snippets

### Get your own profile

```python
with sync_playwright() as p:
    ctx, page, csrf = linkedin_page(p)
    r = page.evaluate(f"""async () => {{
        const r = await fetch('/voyager/api/me', {{
            headers: {{'Csrf-Token': '{csrf}', 'X-RestLi-Protocol-Version': '2.0.0', 'Accept': 'application/json'}}
        }});
        return {{status: r.status, body: await r.json()}};
    }}""")
    mini = r['body']['miniProfile']
    print(mini['firstName'], mini['lastName'], mini['publicIdentifier'])
    # → Alice Smith alice-smith-123456
    ctx.close()
```

### List conversations

```python
with sync_playwright() as p:
    ctx, page, csrf = linkedin_page(p)
    env = load_env_file(DEFAULT_ENV_FILE)
    # Use your entityUrn from /me response: miniProfile.entityUrn → strip "urn:li:fs_miniProfile:" prefix
    mailbox_urn = "urn:li:fsd_profile:YOUR_ENTITY_URN"  # replace with your entityUrn from /me
    from urllib.parse import quote
    r = page.evaluate(f"""async () => {{
        const mailbox = '{mailbox_urn}';
        const url = '/voyager/api/voyagerMessagingGraphQL/graphql'
            + '?queryId=messengerConversations.9501074288a12f3ae9e3c7ea243bccbf'
            + '&variables=(query:(predicateUnions:List((conversationCategoryPredicate:(category:PRIMARY_INBOX)))),count:20,mailboxUrn:' + encodeURIComponent(mailbox) + ')';
        const r = await fetch(url, {{
            headers: {{'Csrf-Token': '{csrf}', 'X-RestLi-Protocol-Version': '2.0.0', 'Accept': 'application/json'}}
        }});
        return {{status: r.status, body: await r.json()}};
    }}""")
    convos = r['body'].get('data', {}).get('messengerConversationsByCategoryWithMetadata', {}).get('elements', [])
    for c in convos[:5]:
        urn = c.get('entityUrn', '')
        participants = [p.get('participant', {}).get('com.linkedin.voyager.messaging.MessagingMember', {}).get('miniProfile', {}).get('firstName', '?')
                        for p in c.get('participants', {}).get('elements', [])]
        print(f"{urn[-30:]}  participants={participants}")
    # → ...ZmEwMDQ2ZGYt...  participants=['Alice', 'Bob']
    ctx.close()
```

### Read messages in a conversation

```python
# conversation_urn: from list above, e.g. "urn:li:msg_conversation:(urn:li:fsd_profile:...,2-ZmEwM...)"
with sync_playwright() as p:
    ctx, page, csrf = linkedin_page(p)
    conversation_urn = "urn:li:msg_conversation:(urn:li:fsd_profile:YOUR_ENTITY_URN,2-YOUR_CONVO_ID)"
    r = page.evaluate(f"""async () => {{
        const convoUrn = encodeURIComponent('{conversation_urn}');
        const url = '/voyager/api/voyagerMessagingGraphQL/graphql'
            + '?queryId=messengerMessages.5846eeb71c981f11e0134cb6626cc314'
            + '&variables=(conversationUrn:' + convoUrn + ',countBefore:20,countAfter:0)';
        const r = await fetch(url, {{
            headers: {{'Csrf-Token': '{csrf}', 'X-RestLi-Protocol-Version': '2.0.0', 'Accept': 'application/json'}}
        }});
        return {{status: r.status, body: await r.json()}};
    }}""")
    msgs = r['body'].get('data', {}).get('messengerMessagesByAnchor', {}).get('elements', [])
    for m in msgs[-5:]:
        sender = m.get('sender', {}).get('com.linkedin.voyager.messaging.MessagingMember', {}).get('miniProfile', {}).get('firstName', '?')
        text = m.get('body', {}).get('text', '')
        print(f"[{sender}]: {text[:100]}")
    # → [Bob]: Hey, let's catch up!
    ctx.close()
```

### Send a message (reply to a conversation)

Verified: `POST /voyager/api/voyagerMessagingDashMessengerMessages?action=createMessage` → HTTP 201

```python
import uuid
with sync_playwright() as p:
    ctx, page, csrf = linkedin_page(p)
    conversation_urn = "urn:li:msg_conversation:(urn:li:fsd_profile:YOUR_ENTITY_URN,2-YOUR_CONVO_ID)"
    mailbox_urn = "urn:li:fsd_profile:YOUR_ENTITY_URN"
    token = str(uuid.uuid4())
    payload = {
        "message": {
            "body": {"attributes": [], "text": "Hello from agent 🤖"},
            "renderContentUnions": [],
            "conversationUrn": conversation_urn,
            "originToken": token,
        },
        "mailboxUrn": mailbox_urn,
        "dedupeByClientGeneratedToken": False,
    }
    import json
    r = page.evaluate(f"""async () => {{
        const r = await fetch('/voyager/api/voyagerMessagingDashMessengerMessages?action=createMessage', {{
            method: 'POST',
            headers: {{
                'Csrf-Token': '{csrf}',
                'X-RestLi-Protocol-Version': '2.0.0',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }},
            body: JSON.stringify({json.dumps(payload)})
        }});
        let body; try {{ body = await r.json(); }} catch(e) {{ body = {{}}; }}
        return {{status: r.status, body}};
    }}""")
    print(f"HTTP {r['status']}")  # → HTTP 201
    ctx.close()
```

### Make a post

LinkedIn's feed now uses React Server Components (`flagship-web`). Post creation goes through `POST /flagship-web/rsc-action/actions/` with a proto-encoded body — not feasible to construct manually. Use the Playwright UI automation approach instead:

```python
with sync_playwright() as p:
    ctx, page, csrf = linkedin_page(p)
    text = "Hello from agent 🤖 — test post"

    # Navigate to post creation via URL (opens modal)
    page.goto("https://www.linkedin.com/sharing/share-offsite/?text=" + text.replace(" ", "+"),
              wait_until="domcontentloaded", timeout=15000)
    time.sleep(2)

    # If modal opened, click Post
    try:
        post_btn = page.get_by_role("button", name="Post", exact=True).last
        post_btn.click(timeout=5000)
        time.sleep(3)
        print("Post submitted")
    except Exception:
        # Alternate: use the direct UGC endpoint (works for simple text posts)
        payload = {
            "author": "urn:li:person:YOUR_PERSON_ID",  # from entityUrn in /me response
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        import json
        r = page.evaluate(f"""async () => {{
            const r = await fetch('/voyager/api/contentcreation/normShares', {{
                method: 'POST',
                headers: {{
                    'Csrf-Token': '{csrf}',
                    'X-RestLi-Protocol-Version': '2.0.0',
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({json.dumps(payload)})
            }});
            return {{status: r.status}};
        }}""")
        print(f"POST normShares → HTTP {r['status']}")

    ctx.close()
```

---

## API surface

| Endpoint | Method | What it does | Verified |
|----------|--------|-------------|---------|
| `/voyager/api/me` | GET | Your profile: name, publicId, entityUrn | ✅ HTTP 200 |
| `/voyager/api/voyagerMessagingGraphQL/graphql?queryId=messengerConversations.9501074288...` | GET | List inbox conversations | ✅ HTTP 200 |
| `/voyager/api/voyagerMessagingGraphQL/graphql?queryId=messengerMessages.5846eeb71c981f...` | GET | Read messages in a conversation | ✅ HTTP 200 |
| `/voyager/api/voyagerMessagingDashMessengerMessages?action=createMessage` | POST | Send/reply a message | ✅ HTTP 201 |
| `/voyager/api/contentcreation/normShares` | POST | Create a text post | ⚠ 400 with wrong actor URN — use person URN, not miniProfile URN |

---

## Notes

- **Persistent profile required:** `~/.browser_automation/linkedin_profile/` — never delete this folder or LinkedIn will 2FA again on next run.
- **JSESSIONID expires in ~24h.** Re-run `sso.py` to refresh (no 2FA since profile is trusted).
- **li_at is long-lived** (weeks to months). If it expires, re-run `sso.py --force`.
- **No VPN required.**
- **Bot detection:** Raw `urllib` or `requests` calls are blocked (HTTP 999 / redirect loop). All API calls must be made from within a Playwright page context with the persistent profile.
- **Actor URN for posts:** Use `urn:li:person:{id}`. Get your `entityUrn` from the `/me` response (`miniProfile.entityUrn`), then use that ID in the person URN format.
