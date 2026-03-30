---
name: gmail
auth: app-password
---

# Gmail Setup

## What to ask the user

Ask for their Gmail address and a 16-character App Password (not their Google password).

To generate an App Password:
1. Go to https://myaccount.google.com/apppasswords
2. Sign in if prompted
3. Click "Create app password", name it anything (e.g. "Cursor Agent")
4. Copy the 16-character password shown

Also confirm IMAP is enabled:
- Gmail → Settings (gear) → See all settings → Forwarding and POP/IMAP → Enable IMAP → Save

## `.env` entries

```bash
# --- Gmail ---
GMAIL_EMAIL=you@gmail.com
GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxxxxxx   # 16-char App Password, spaces optional
GMAIL_IMAP_HOST=imap.gmail.com
GMAIL_IMAP_PORT=993
# Generate at: https://myaccount.google.com/apppasswords
# Token lifetime: long-lived (until revoked)
```

## Verify snippet

```bash
source .env && python3 - <<'EOF'
import imaplib, os
mail = imaplib.IMAP4_SSL(os.environ['GMAIL_IMAP_HOST'], int(os.environ['GMAIL_IMAP_PORT']))
result = mail.login(os.environ['GMAIL_EMAIL'], os.environ['GMAIL_APP_PASSWORD'])
print('Auth:', result)
mail.select('INBOX')
_, data = mail.search(None, 'ALL')
print(f'INBOX emails: {len(data[0].split())}')
mail.logout()
EOF
```

Expected output:
```
Auth: ('OK', [b'you@gmail.com authenticated (Success)'])
INBOX emails: <count>
```
