---
name: linkedin-setup
description: Set up LinkedIn connection using li_at session cookie. No developer app needed. Opens a browser once for login, then reuses the persistent profile.
---

# LinkedIn — Setup

## Auth method: session-cookie (li_at)

LinkedIn has no public API for personal use without app approval. This connection uses your browser session cookie (`li_at`) extracted via Playwright. A persistent browser profile is saved to `~/.browser_automation/linkedin_profile/` so LinkedIn recognizes the device — no 2FA after the first login.

**What to ask the user:** Nothing. Just run `sso.py` — it opens a browser window for login.

---

## Steps

1. Run the SSO capture script:

```bash
source .venv/bin/activate
python3 personal/linkedin/sso.py   # run from personal/ copy (see setup.md Step 1)
```

2. A Chromium window opens. Log in to LinkedIn (complete 2FA if prompted — this is the only time).
3. Once the feed loads, the script captures `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` and writes them to `.env` automatically.
4. The browser window closes.

**Second run and beyond:** the script reuses `~/.browser_automation/linkedin_profile/` and skips straight to feed — no login, no 2FA.

---

## Refresh

- `LINKEDIN_JSESSIONID` expires in ~24h. Re-run `sso.py` to refresh (no 2FA, takes ~6s).
- `LINKEDIN_LI_AT` is long-lived (weeks to months). Re-run `sso.py --force` if it expires.

```bash
# Check if session is still valid:
python3 personal/linkedin/sso.py
# → LINKEDIN_LI_AT is valid — nothing to do.

# Force refresh:
python3 personal/linkedin/sso.py --force
```

---

## Verify

```python
import sys, time
from pathlib import Path
sys.path.insert(0, "tool_connections")
from shared_utils.browser import sync_playwright, DEFAULT_ENV_FILE, load_env_file

PROFILE_DIR = Path.home() / ".browser_automation" / "linkedin_profile"
env = load_env_file(DEFAULT_ENV_FILE)
li_at = env["LINKEDIN_LI_AT"]
csrf = env["LINKEDIN_JSESSIONID"].strip('"')

with sync_playwright() as p:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_DIR), headless=False,
        args=["--window-size=1024,768"], ignore_https_errors=True,
    )
    page = ctx.new_page()
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    r = page.evaluate(f"""async () => {{
        const r = await fetch('/voyager/api/me', {{
            headers: {{'Csrf-Token': '{csrf}', 'X-RestLi-Protocol-Version': '2.0.0', 'Accept': 'application/json'}}
        }});
        return {{status: r.status, body: await r.json()}};
    }}""")
    mini = r['body']['miniProfile']
    print(r['status'], mini['firstName'], mini['lastName'])
    # → 200 Alice Smith
    ctx.close()
```

**Connection details:** `tool_connections/linkedin/connection-session-cookie.md`

---

## `.env` entries

```bash
# --- LinkedIn ---
# Short-lived JSESSIONID (~24h) — refresh with: python3 personal/linkedin/sso.py
# Long-lived li_at (weeks/months) — refresh with: python3 personal/linkedin/sso.py --force
# Persistent profile at: ~/.browser_automation/linkedin_profile/ (do not delete)
LINKEDIN_LI_AT=your-li_at-cookie-value
LINKEDIN_JSESSIONID=your-jsessionid-value
```
