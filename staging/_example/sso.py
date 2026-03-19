#!/usr/bin/env python3
"""
{Tool Name} SSO session capture via Playwright.

Delete this file if the tool uses API tokens instead of SSO.

Follow the patterns in tool_connections/shared_utils/sso_patterns.py.
Usage: python3 staging/{tool-name}/sso.py
"""
import sys
from pathlib import Path

# Add tool_connections to path so shared_utils is importable
sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))

from shared_utils.browser import (
    sync_playwright,
    load_env_var,
    update_env_file,
    http_get_no_redirect,
    DEFAULT_ENV_FILE,
)

# --- Config ---
TOOL_BASE_URL = load_env_var("{TOOL}_BASE_URL", "https://yourtool.example.com/")
TOKEN_ENV_KEY = "{TOOL}_SESSION_TOKEN"


def is_valid(env_path: Path = DEFAULT_ENV_FILE) -> bool:
    """Return True if the stored session is still valid."""
    env = {k.strip(): v.strip() for line in env_path.read_text().splitlines()
           if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
    token = env.get(TOKEN_ENV_KEY, "")
    if not token:
        return False
    # Replace with a real validity check:
    status = http_get_no_redirect(f"{TOOL_BASE_URL}/api/me",
                                  {"Authorization": f"Bearer {token}"})
    return status == 200


def capture(base_url: str = TOOL_BASE_URL) -> dict:
    """Open a browser, let the user log in, extract and return the session token."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Navigate to the login page
        page.goto(f"{base_url}/login")
        print("Log in to {Tool Name} in the browser window, then press Enter here...")
        input()

        # Extract the token — adjust selector/storage key for the actual tool
        token = ctx.cookies()  # or page.evaluate("localStorage.getItem('token')")
        browser.close()

        return {TOKEN_ENV_KEY: token}


def main():
    if is_valid():
        print("Session still valid — skipping capture.")
        return
    print(f"Capturing {'{Tool Name}'} session for {TOOL_BASE_URL} ...")
    tokens = capture(TOOL_BASE_URL)
    update_env_file(DEFAULT_ENV_FILE, tokens)
    print("Session saved to .env")


if __name__ == "__main__":
    main()
