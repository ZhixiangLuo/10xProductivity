"""
Microsoft 365 Copilot Search SSO capture.

Opens m365.cloud.microsoft/search in a headed browser, completes Azure AD SSO,
and captures the Bearer token used for Microsoft Graph Search API calls.

Token scopes include Files.ReadWrite.All, User.Read, People.Read — sufficient
for driveItem, event, site, and listItem searches. Does NOT include Mail.Read
or ChannelMessage.Read.All (use the Outlook connection for email).

Usage:
    python3 tool_connections/m365-copilot-search/sso.py
    python3 tool_connections/m365-copilot-search/sso.py --force
"""

import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

import ssl
import urllib.request
import json

TOOL_NAME = "m365-copilot-search"
ENV_KEYS = ["M365_SEARCH_TOKEN"]
M365_SEARCH_URL = "https://m365.cloud.microsoft/search/"


def check(env: dict) -> bool:
    """Return True if M365_SEARCH_TOKEN is valid for Graph search."""
    token = env.get("M365_SEARCH_TOKEN", "")
    if not token or token.startswith("your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        body = json.dumps({
            "requests": [{"entityTypes": ["driveItem"],
                          "query": {"queryString": "test"}, "from": 0, "size": 1}]
        }).encode()
        req = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/search/query",
            data=body,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """
    Open m365.cloud.microsoft/search in headed browser, complete Azure AD SSO,
    and capture the Bearer token used in Graph API search requests.

    On managed Macs with macOS Enterprise SSO, auto-completes in ~30s.
    On unmanaged machines, complete the login manually when the browser opens.
    Token lifetime: ~1h.
    """
    def _is_jwt(t: str) -> bool:
        return isinstance(t, str) and t.count(".") in (2, 4) and len(t) > 100

    captured: dict[str, str] = {}

    def _on_request(req):
        auth = req.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return
        t = auth[7:]
        if not _is_jwt(t):
            return
        if "graph.microsoft.com" in req.url and "search_token" not in captured:
            captured["search_token"] = t
            print(f"    M365 search token captured ({len(t)} chars)", flush=True)

    print(f"  Opening M365 Copilot Search ({M365_SEARCH_URL}) — Azure AD SSO auto-completes on managed Mac...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1280,900", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.on("request", _on_request)
        page.goto(M365_SEARCH_URL, wait_until="commit", timeout=30_000)
        print("    Waiting for login + token (up to 3 min)...", flush=True)

        deadline = time.time() + 180
        while time.time() < deadline:
            if "search_token" in captured:
                time.sleep(3)
                break
            time.sleep(1)

        browser.close()

    if not captured:
        raise RuntimeError("No M365 search token captured — login may not have completed within 3 minutes.")

    return {"M365_SEARCH_TOKEN": captured["search_token"]}


if __name__ == "__main__":
    import argparse
    import re
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
            else:
                content += f"\n# --- M365 Copilot Search\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("M365_SEARCH_TOKEN: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    print("Capturing M365 Copilot Search token...")
    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
    print("Done.")
