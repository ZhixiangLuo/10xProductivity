#!/usr/bin/env python3
"""
Miro SSO capture — plugin for playwright_sso.py discovery.

Opens miro.com, completes SSO, saves the web app `token` cookie to .env as MIRO_TOKEN.
Uses internal https://miro.com/api/v1/ — not api.miro.com OAuth.

Usage (repo root):
    python3 tool_connections/shared_utils/playwright_sso.py --miro-only
    python3 tool_connections/miro/sso.py
    python3 tool_connections/miro/sso.py --force
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os

    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TOOL_NAME = "miro"
ENV_KEYS = ["MIRO_TOKEN"]
MIRO_URL = "https://miro.com/app/"
COOKIE_URLS = ["https://miro.com", "https://www.miro.com"]
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def check(env: dict) -> bool:
    """Return True if MIRO_TOKEN works against internal /users/me/."""
    token = (env.get("MIRO_TOKEN") or "").strip()
    if not token or token.startswith("your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://miro.com/api/v1/users/me/",
            headers={"Cookie": f"token={token}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
            return r.status == 200
    except Exception:
        return False


def capture(_env: dict) -> dict:
    """Headed browser → miro.com/app → wait for `token` cookie (post-SSO)."""

    def _on_response(resp):
        try:
            u = resp.url
            if "/sso/saml" in u and resp.request.method == "POST":
                print("  SAML callback completed — waiting for session cookie...", flush=True)
        except Exception:
            pass

    print(f"  Opening Miro ({MIRO_URL}) — sign in if prompted (up to 3 min)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.on("response", _on_response)

        page.goto(MIRO_URL, wait_until="commit", timeout=60_000)
        try:
            page.wait_for_url("**/miro.com/**", timeout=15_000)
        except PlaywrightTimeout:
            pass

        deadline = time.time() + 180
        token = None
        while time.time() < deadline:
            cookies = ctx.cookies(COOKIE_URLS)
            token = {c["name"]: c["value"] for c in cookies}.get("token")
            if token:
                break
            time.sleep(2)

        browser.close()

    if not token:
        raise RuntimeError(
            "Miro `token` cookie not found — complete sign-in in the browser window, then re-run."
        )

    print(f"  Miro token captured ({len(token)} chars)")
    return {"MIRO_TOKEN": token}


def _load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    return {
        k.strip(): v.strip()
        for line in ENV_FILE.read_text().splitlines()
        if "=" in line and not line.startswith("#")
        for k, v in [line.split("=", 1)]
    }


def _write_env(tokens: dict[str, str]) -> None:
    content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    for key, value in tokens.items():
        new_line = f"{key}={value}"
        if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
            content = re.sub(
                rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE
            )
        elif "# --- Miro" in content:
            content = content.replace("# --- Miro\n", f"# --- Miro\n{new_line}\n", 1)
        else:
            content += f"\n# --- Miro\n{new_line}\n"
    ENV_FILE.write_text(content)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Capture Miro session token to .env")
    parser.add_argument("--force", action="store_true", help="Refresh even if token looks valid")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("MIRO_TOKEN: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")


if __name__ == "__main__":
    main()
