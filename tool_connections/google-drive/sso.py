#!/usr/bin/env python3
"""
Google Drive SSO session capture via Playwright.

Opens a headed Chromium window, completes Google Workspace SSO, and saves:
  - ~/.browser_automation/gdrive_auth.json  — Playwright storage_state (days/weeks TTL)
  - GDRIVE_COOKIES, GDRIVE_SAPISID in .env  — informational only

NOTE: Raw cookie injection triggers Google's CookieMismatch security check.
Playwright's storage_state is the only approach that works for Google Drive.

Usage:
    python3 tool_connections/google-drive/sso.py
    python3 tool_connections/google-drive/sso.py --force
    python3 tool_connections/google-drive/sso.py --env-file /path/to/.env

Requirements:
    pip install playwright && playwright install chromium
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from shared_utils.browser import (
    sync_playwright, PlaywrightTimeout, load_env_file,
    update_env_file, DEFAULT_ENV_FILE,
)

GDRIVE_URL      = "https://drive.google.com/drive/my-drive"
GDRIVE_AUTH_FILE = Path.home() / ".browser_automation" / "gdrive_auth.json"


def is_valid() -> bool:
    """Check if the saved storage_state is still usable."""
    if not GDRIVE_AUTH_FILE.exists():
        return False
    # Quick heuristic: file exists and is non-empty
    return GDRIVE_AUTH_FILE.stat().st_size > 1000


def capture() -> dict:
    """Open Google Drive, complete SSO, save storage_state, return cookie info."""
    print("  Opening Google Drive (~30s to sign in)...")
    # Use a persistent context so Google sees a real browser profile, not a fresh
    # automation session — this avoids the "browser may not be secure" block that
    # personal accounts trigger when cookies are absent.
    user_data_dir = str(Path.home() / ".browser_automation" / "gdrive_profile")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=[
                "--window-size=1200,800",
                "--window-position=100,100",
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        page.goto(GDRIVE_URL, wait_until="commit", timeout=30_000)

        try:
            page.wait_for_url("https://drive.google.com/**", timeout=60_000)
        except PlaywrightTimeout:
            if "accounts.google.com" in page.url or "google.com/signin" in page.url:
                print("  Google sign-in page — complete login manually (3 min timeout)...", flush=True)
                page.wait_for_url("https://drive.google.com/**", timeout=180_000)
            else:
                raise RuntimeError(f"Unexpected URL after Drive navigation: {page.url}")

        try:
            page.wait_for_load_state("networkidle", timeout=30_000)
        except PlaywrightTimeout:
            pass
        time.sleep(3)

        GDRIVE_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        ctx.storage_state(path=str(GDRIVE_AUTH_FILE))
        print(f"  Session saved to {GDRIVE_AUTH_FILE} ({GDRIVE_AUTH_FILE.stat().st_size} bytes)")

        google_cookies = ctx.cookies([
            "https://google.com", "https://www.google.com",
            "https://drive.google.com", "https://accounts.google.com",
        ])
        cookie_dict = {c["name"]: c["value"] for c in google_cookies}
        sapisid = cookie_dict.get("SAPISID", "")
        cookie_keys = [
            "SID", "HSID", "SSID", "APISID", "SAPISID",
            "__Secure-1PSID", "__Secure-3PSID",
            "__Secure-1PAPISID", "__Secure-3PAPISID",
            "__Secure-1PSIDTS", "__Secure-3PSIDTS",
            "__Secure-1PSIDCC", "__Secure-3PSIDCC",
            "NID", "ACCOUNT_CHOOSER",
        ]
        cookie_str = "; ".join(
            f"{k}={cookie_dict[k]}" for k in cookie_keys
            if k in cookie_dict and cookie_dict[k]
        )
        ctx.close()

    print(f"  Captured: GDRIVE_SAPISID ({len(sapisid)} chars)")
    return {"gdrive_cookies": cookie_str, "gdrive_sapisid": sapisid}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--force", action="store_true", help="Refresh even if session file exists")
    args = parser.parse_args()

    if not args.force and is_valid():
        print(f"Google Drive session exists at {GDRIVE_AUTH_FILE} — nothing to do. Use --force to refresh.")
        return

    tokens = capture()
    update_env_file(args.env_file, tokens)
    print("\nDone.")


if __name__ == "__main__":
    main()
