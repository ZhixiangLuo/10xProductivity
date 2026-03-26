"""
Outlook / Microsoft 365 SSO capture — plugin for playwright_sso.py discovery.

Navigates to outlook.office.com, completes Azure AD SSO, and captures
Bearer tokens from network requests for Graph API and OWA.

Standalone usage:
    python3 tool_connections/outlook/sso.py
    python3 tool_connections/outlook/sso.py --force
"""

import sys
import time

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import ssl
import urllib.request

TOOL_NAME = "outlook"
ENV_KEYS = ["GRAPH_ACCESS_TOKEN", "OWA_ACCESS_TOKEN"]
OUTLOOK_URL = "https://outlook.office.com/mail/"


def check(env: dict) -> bool:
    """Return True if GRAPH_ACCESS_TOKEN is valid."""
    token = env.get("GRAPH_ACCESS_TOKEN", "")
    if not token or token.startswith("your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """
    Open Outlook web in headed browser, complete Azure AD SSO, and capture
    Bearer tokens from network requests.

    On managed machines with macOS Enterprise SSO, auto-completes in ~30s.
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
        if "graph.microsoft.com" in req.url and "graph" not in captured:
            captured["graph"] = t
        elif "outlook.office.com" in req.url and "owa" not in captured:
            captured["owa"] = t

    print(f"  Opening Outlook ({OUTLOOK_URL}) — Azure AD SSO should auto-complete...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.on("request", _on_request)
        page.goto(OUTLOOK_URL, wait_until="commit", timeout=30_000)
        print("    Waiting for Outlook login to complete (up to 3 min)...", flush=True)

        deadline = time.time() + 180
        while time.time() < deadline:
            if "graph" in captured and "owa" in captured:
                break
            time.sleep(1)

        browser.close()

    if not captured:
        raise RuntimeError("No Outlook tokens captured — login may not have completed within 3 minutes.")

    graph_token = captured.get("graph", "")
    owa_token = captured.get("owa", "")

    if not graph_token:
        raise RuntimeError("Graph token not captured — Outlook page may not have loaded.")
    if not owa_token:
        print("    Warning: OWA token not captured — only Graph token available.")

    print(f"    Graph token captured ({len(graph_token)} chars)")
    if owa_token:
        print(f"    OWA token captured ({len(owa_token)} chars)")

    result = {"GRAPH_ACCESS_TOKEN": graph_token}
    if owa_token:
        result["OWA_ACCESS_TOKEN"] = owa_token
    return result


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
        import re
        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
            elif "# --- Outlook / Microsoft 365" in content:
                content = content.replace(
                    "# --- Outlook / Microsoft 365\n",
                    f"# --- Outlook / Microsoft 365\n{new_line}\n", 1)
            else:
                content += f"\n# --- Outlook / Microsoft 365\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("GRAPH_ACCESS_TOKEN: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
