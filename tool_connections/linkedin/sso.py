#!/usr/bin/env python3
"""
LinkedIn session capture via Playwright.

Uses a PERSISTENT browser profile (~/.browser_automation/linkedin_profile/) so
LinkedIn treats the browser as a known device — no 2FA after the first login.

Captures:
  - LINKEDIN_LI_AT       — main session cookie (long-lived, weeks/months)
  - LINKEDIN_JSESSIONID  — CSRF token (required for Voyager API calls, ~24h)

Usage:
    python3 personal/linkedin/sso.py           # run from your personal/ copy
    python3 personal/linkedin/sso.py --force   # force re-capture even if valid
    python3 personal/linkedin/sso.py --env-file /path/to/.env

Requirements:
    pip install playwright && playwright install chromium
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))
from shared_utils.browser import (
    sync_playwright,
    load_env_file,
    update_env_file,
    DEFAULT_ENV_FILE,
    BROWSER_AUTOMATION_DIR,
)

# Persistent profile — LinkedIn remembers this as a trusted device after first login
PROFILE_DIR = BROWSER_AUTOMATION_DIR / "linkedin_profile"


def _open_persistent(p):
    """Launch a persistent Chromium context using the saved profile."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return p.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,
        args=["--window-size=1024,768", "--window-position=100,100"],
        ignore_https_errors=True,
    )


def is_valid(env_path: Path) -> bool:
    env = load_env_file(env_path)
    li_at = env.get("LINKEDIN_LI_AT", "")
    jsession = env.get("LINKEDIN_JSESSIONID", "").strip('"')
    if not li_at or li_at == "your-li_at-cookie-value" or not jsession:
        return False
    with sync_playwright() as p:
        ctx = _open_persistent(p)
        page = ctx.new_page()
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
            result = page.evaluate(f"""async () => {{
                const r = await fetch('/voyager/api/me', {{
                    headers: {{'Csrf-Token': '{jsession}', 'X-RestLi-Protocol-Version': '2.0.0', 'Accept': 'application/json'}}
                }});
                return r.status;
            }}""")
            return result == 200
        except Exception:
            return False
        finally:
            ctx.close()


def capture() -> dict:
    """Open LinkedIn in the persistent profile, let user log in, extract cookies."""
    print(f"  Using persistent profile: {PROFILE_DIR}")
    print("  Opening LinkedIn login page...")
    with sync_playwright() as p:
        ctx = _open_persistent(p)
        page = ctx.new_page()

        page.goto("https://www.linkedin.com/login", wait_until="commit", timeout=30_000)
        print("  Log in to LinkedIn in the browser window.")
        print("  (If already logged in from a previous run, it will skip straight to feed.)")
        print("  Waiting for feed to load (up to 3 min)...", flush=True)

        li_at = None
        jsession = None
        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(2)
            cookies = {c["name"]: c["value"] for c in ctx.cookies(["https://www.linkedin.com"])}
            li_at = cookies.get("li_at")
            jsession = cookies.get("JSESSIONID", "").strip('"')
            current_url = page.url
            if li_at and jsession and (
                "linkedin.com/feed" in current_url
                or "linkedin.com/in/" in current_url
                or "linkedin.com/mynetwork" in current_url
            ):
                break

        ctx.close()

    if not li_at:
        raise RuntimeError("No li_at cookie found — login may not have completed within 3 minutes.")
    if not jsession:
        raise RuntimeError("No JSESSIONID found — could not extract CSRF token.")

    print(f"  Captured: LINKEDIN_LI_AT ({len(li_at)} chars), LINKEDIN_JSESSIONID ({len(jsession)} chars)")
    return {"linkedin_li_at": li_at, "linkedin_jsessionid": jsession}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--force", action="store_true", help="Refresh even if cookie is still valid")
    args = parser.parse_args()

    if not args.force and is_valid(args.env_file):
        print("LINKEDIN_LI_AT is valid — nothing to do. Use --force to refresh anyway.")
        return

    tokens = capture()
    update_env_file(args.env_file, tokens)
    print("\nDone. Run the verify snippet in connection-session-cookie.md to confirm.")


if __name__ == "__main__":
    main()
