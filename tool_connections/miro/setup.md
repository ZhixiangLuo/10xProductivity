---
name: miro-setup
description: Set up Miro connection. SSO browser session captures web app token; internal miro.com/api/v1. No OAuth Developer app.
---

# Miro — Setup

## Auth method: SSO browser session (`token` cookie)

Miro’s public REST API is `api.miro.com/v2` (OAuth app). This recipe uses the **web app session**: after sign-in, **`MIRO_TOKEN`** is the `token` cookie for **`https://miro.com/api/v1/`**.

**What to ask the user:** Any Miro URL (e.g. dashboard) is enough to confirm the product; complete sign-in when the browser window opens.

**First-time use (per root `setup.md`):** copy this folder to your working layer — `cp -r tool_connections/miro personal/miro` — then run scripts from **`personal/miro/`** so upstream pulls never overwrite your copy.

---

## Steps

```bash
source .venv/bin/activate
pip install playwright -q && playwright install chromium   # once
python3 tool_connections/shared_utils/playwright_sso.py --miro-only
# or:
python3 tool_connections/miro/sso.py
```

Writes **`MIRO_TOKEN`** to repo root **`.env`**.

---

## Verify

```bash
python3 tool_connections/miro/read_miro.py --check
python3 tool_connections/miro/read_miro.py --recent
```

**Connection details:** `tool_connections/miro/connection-sso.md`

---

## `.env`

```bash
# --- Miro ---
MIRO_TOKEN=your-token-here
# Refresh: python3 tool_connections/shared_utils/playwright_sso.py --miro-only --force
```

---

## Refresh

Session typically lasts **days**. On 401 / auth errors:

```bash
python3 tool_connections/shared_utils/playwright_sso.py --miro-only --force
```
