---
name: gmail
auth: app-password
description: Gmail personal inbox via IMAP. Read, list, and search emails by subject, sender, date, or read state. Supports all Gmail folders/labels.
env_vars:
  - GMAIL_EMAIL
  - GMAIL_APP_PASSWORD
  - GMAIL_IMAP_HOST
  - GMAIL_IMAP_PORT
---

# Gmail — App Password (IMAP)

Gmail personal email via IMAP using a Google App Password. Supports reading, searching, and listing emails without OAuth app creation.

API docs: https://developers.google.com/workspace/gmail/imap/imap-smtp

**Verified:** Production (imap.gmail.com:993) — login, list, fetch, search — 2026-03. No VPN required.

---

## Credentials

```bash
# Add to .env:
# GMAIL_EMAIL=you@gmail.com
# GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (16-char, spaces optional)
# GMAIL_IMAP_HOST=imap.gmail.com
# GMAIL_IMAP_PORT=993
# Generate App Password at: https://myaccount.google.com/apppasswords
# Requires: Google account → Security → 2-Step Verification must be ON
```

---

## Auth

IMAP SSL on port 993. Login with Gmail address and 16-character App Password (not your Google account password).

```bash
source .env
python3 - <<'EOF'
import imaplib
mail = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, int(GMAIL_IMAP_PORT))
result = mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
print(result)
# → ('OK', [b'you@gmail.com authenticated (Success)'])
mail.logout()
EOF
```

---

## Verified snippets

```python
import imaplib, email, os
from email.header import decode_header

def gmail_connect():
    mail = imaplib.IMAP4_SSL(os.environ['GMAIL_IMAP_HOST'], int(os.environ['GMAIL_IMAP_PORT']))
    mail.login(os.environ['GMAIL_EMAIL'], os.environ['GMAIL_APP_PASSWORD'])
    return mail

# List recent emails (N most recent from INBOX)
def list_recent(n=10):
    mail = gmail_connect()
    mail.select('INBOX')
    _, data = mail.search(None, 'ALL')
    ids = data[0].split()[-n:]
    results = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        subject, enc = decode_header(msg['Subject'])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(enc or 'utf-8', errors='replace')
        results.append({'from': msg['From'], 'subject': subject, 'date': msg['Date']})
    mail.logout()
    return results
# → [{'from': 'Google <no-reply@accounts.google.com>', 'subject': 'Security alert', 'date': '...'}, ...]

# Search by subject keyword
def search_by_subject(keyword):
    mail = gmail_connect()
    mail.select('INBOX')
    _, data = mail.search(None, 'SUBJECT', keyword)
    ids = data[0].split()
    mail.logout()
    return len(ids)
# search_by_subject('GitHub') → N matching emails

# Search by sender domain
def search_by_sender(domain):
    mail = gmail_connect()
    mail.select('INBOX')
    _, data = mail.search(None, 'FROM', domain)
    ids = data[0].split()
    mail.logout()
    return len(ids)
# search_by_sender('github.com') → N matching emails

# Count unread emails
def count_unread():
    mail = gmail_connect()
    mail.select('INBOX')
    _, data = mail.search(None, 'UNSEEN')
    mail.logout()
    return len(data[0].split())
# → 0

# ⚠ IMAP SEARCH criteria use server-side search — case-insensitive but exact substring match only.
# Use 'SUBJECT', 'FROM', 'TO', 'BODY', 'SINCE', 'BEFORE', 'UNSEEN', 'SEEN' as criteria.
# Example: mail.search(None, 'SINCE', '01-Mar-2026') — date format: DD-Mon-YYYY
```

---

## Notes

- No search API (REST). All search is via IMAP SEARCH criteria — works well for filtering by subject, sender, date, and read state.
- No AI/chat API available via IMAP.
- Gmail must have IMAP enabled: Gmail Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP.
- App Password is long-lived (until manually revoked at myaccount.google.com/apppasswords).
- IMAP SEARCH `BODY` keyword is slow on large mailboxes — prefer `SUBJECT` or `FROM` filters.
- `mail.select('INBOX')` selects inbox; use `mail.list()` to enumerate all folders (Labels in Gmail).
- INBOX with large mailboxes verified accessible.
