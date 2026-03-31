"""
Miro SSO capture — plugin for playwright_sso.py discovery.

Navigates to miro.com, completes Okta SSO, and captures
the internal `token` cookie used by the Miro web app API.

Note: Uses miro.com/api/v1/ (internal API), NOT api.miro.com/v2/
(the official API requires OAuth app registration — this approach
captures the same token the browser uses, no app needed).

Standalone usage:
    python3 personal/miro/sso.py
    python3 personal/miro/sso.py --force
"""

import sys
import time
import re

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import ssl
import urllib.request
import json

TOOL_NAME = "miro"
ENV_KEYS = ["MIRO_TOKEN"]
MIRO_URL = "https://miro.com/app/"


def check(env: dict) -> bool:
    """Return True if MIRO_TOKEN is valid."""
    token = env.get("MIRO_TOKEN", "")
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
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """
    Open Miro in headed browser, complete Okta SSO, and capture
    the `token` cookie after SAML auth completes.

    On managed Workday machines, Okta SSO auto-completes in ~30s.
    Token lifetime: session-based (typically days).
    """
    saml_done = {"done": False}

    def _on_response(resp):
        if "/sso/saml" in resp.url and resp.request.method == "POST":
            saml_done["done"] = True
            print("    SAML callback completed — capturing token...", flush=True)

    print(f"  Opening Miro ({MIRO_URL}) — Okta SSO should auto-complete on managed machine...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.on("response", _on_response)
        page.goto(MIRO_URL, wait_until="commit", timeout=30_000)
        print("    Waiting for Okta SAML login to complete (up to 3 min)...", flush=True)

        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(1)
            if saml_done["done"]:
                time.sleep(3)  # let cookies settle
                break

        cookies = ctx.cookies(["https://miro.com"])
        token = {c["name"]: c["value"] for c in cookies}.get("token")
        browser.close()

    if not token:
        raise RuntimeError(
            "Miro token cookie not found — SAML login may not have completed."
        )

    print(f"    Miro token captured ({len(token)} chars)")
    return {"MIRO_TOKEN": token}


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    ENV_FILE = Path(__file__).parents[2] / ".env"

    def _load_env():
        if not ENV_FILE.exists():
            return {}
        return {k.strip(): v.strip() for line in ENV_FILE.read_text().splitlines()
                if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

    def _write_env(tokens):
        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
            elif "# --- Miro" in content:
                content = content.replace("# --- Miro\n", f"# --- Miro\n{new_line}\n", 1)
            else:
                content += f"\n# --- Miro ---\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("MIRO_TOKEN: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
