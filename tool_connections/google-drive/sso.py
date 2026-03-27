"""
Google Drive SSO capture — plugin for playwright_sso.py discovery.

Navigates to Google Drive, completes Google Workspace SSO, and saves
the full browser storage_state plus SAPISID cookie for API access.

Standalone usage:
    python3 tool_connections/google-drive/sso.py
    python3 tool_connections/google-drive/sso.py --force
"""

import sys
import time
import hashlib
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import ssl
import urllib.request

sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))
from shared_utils.browser import BROWSER_AUTOMATION_DIR

TOOL_NAME = "gdrive"
ENV_KEYS = ["GDRIVE_COOKIES", "GDRIVE_SAPISID"]
GDRIVE_AUTH_FILE = BROWSER_AUTOMATION_DIR / "gdrive_auth.json"
GDRIVE_URL = "https://drive.google.com/drive/my-drive"


def check(env: dict) -> bool:
    """Return True if GDRIVE session is valid."""
    sapisid = env.get("GDRIVE_SAPISID", "")
    cookies = env.get("GDRIVE_COOKIES", "")
    if not sapisid or not cookies:
        return False
    try:
        ts = str(int(time.time()))
        sha1 = hashlib.sha1(f"{ts} {sapisid} https://drive.google.com".encode()).hexdigest()
        auth = f"SAPISIDHASH {ts}_{sha1}"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://drive.google.com/drive/v2internal/about?fields=user",
            headers={"Authorization": auth, "Cookie": cookies, "X-Goog-AuthUser": "0"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """
    Open Google Drive in headed browser, complete Google Workspace SSO,
    save storage_state, and return GDRIVE_COOKIES + GDRIVE_SAPISID.

    ⚠ Raw cookie injection triggers Google's CookieMismatch check.
    storage_state correctly replays the full browser session and is the
    only approach that works.
    """
    print(f"  Opening Google Drive — Google Workspace SSO (~30s)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(GDRIVE_URL, wait_until="commit", timeout=30_000)
        try:
            page.wait_for_url("https://drive.google.com/**", timeout=60_000)
        except PlaywrightTimeout:
            if "accounts.google.com" in page.url or "google.com/signin" in page.url:
                print("  Google sign-in page — complete login manually (3 min timeout)...", flush=True)
                page.wait_for_url("https://drive.google.com/**", timeout=180_000)
            else:
                raise RuntimeError(f"Unexpected URL after Google Drive navigation: {page.url}")

        try:
            page.wait_for_load_state("networkidle", timeout=30_000)
        except PlaywrightTimeout:
            pass
        time.sleep(3)

        GDRIVE_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        ctx.storage_state(path=str(GDRIVE_AUTH_FILE))
        print(f"    storage_state saved to {GDRIVE_AUTH_FILE}")

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
        browser.close()

    print(f"    SAPISID captured ({len(sapisid)} chars)")
    return {"GDRIVE_COOKIES": cookie_str, "GDRIVE_SAPISID": sapisid}


if __name__ == "__main__":
    import argparse

    ENV_FILE = Path(__file__).parents[2] / ".env"

    def _load_env():
        if not ENV_FILE.exists():
            return {}
        return {k.strip(): v.strip() for line in ENV_FILE.read_text().splitlines()
                if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

    def _write_env(tokens):
        import re
        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
            elif "# --- Google Drive" in content:
                content = content.replace("# --- Google Drive\n", f"# --- Google Drive\n{new_line}\n", 1)
            else:
                content += f"\n# --- Google Drive\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("GDRIVE: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
