"""
Sana SSO capture — plugin for playwright_sso.py discovery.

Navigates to sana.ai via invite URL, completes SSO, and captures
the sana-ai-session cookie.

Standalone usage:
    python3 personal/sana/sso.py
    python3 personal/sana/sso.py --force
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

TOOL_NAME = "sana"
ENV_KEYS = ["SANA_SESSION_COOKIE", "SANA_WORKSPACE_ID"]
SANA_INVITE_URL = "https://sana.ai/tPNxyS5GyK1r"
SANA_BASE_URL = "https://sana.ai"


def check(env: dict) -> bool:
    """Return True if SANA_SESSION_COOKIE is valid (workspace-scoped check)."""
    cookie = env.get("SANA_SESSION_COOKIE", "")
    workspace_id = env.get("SANA_WORKSPACE_ID", "")
    if not cookie or not workspace_id or cookie.startswith("your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            f"{SANA_BASE_URL}/x-api/trpc/assistantV2.list",
            headers={
                "Cookie": f"sana-ai-session={cookie}",
                "Accept": "application/json",
                "sana-ai-workspace-id": workspace_id,
            },
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """
    Open Sana in headed browser, complete Okta SSO, and capture
    the sana-ai-session cookie AFTER the SAML callback completes.

    The cookie exists before SAML (pre-auth), so we must wait until
    POST /x-api/auth/saml finishes — that's when the session is
    upgraded to a fully authenticated workspace session.

    Token lifetime: varies with IdP session (typically hours–days).
    """
    saml_done = {"done": False}

    def _on_response(resp):
        if "/x-api/auth/saml" in resp.url and resp.request.method == "POST":
            saml_done["done"] = True
            print("    SAML callback completed — capturing cookie...", flush=True)

    print(f"  Opening Sana ({SANA_INVITE_URL}) — Okta SSO should auto-complete on managed machine...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.on("response", _on_response)
        page.goto(SANA_INVITE_URL, wait_until="commit", timeout=30_000)
        print("    Waiting for Okta SAML login to complete (up to 3 min)...", flush=True)

        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(1)
            if saml_done["done"]:
                # Give the app a moment to set the upgraded cookie
                time.sleep(3)
                break

        cookies = ctx.cookies(["https://sana.ai"])
        session_cookie = {c["name"]: c["value"] for c in cookies}.get("sana-ai-session")

        # Extract workspace ID from user.me (present in lastUsedWorkspaceId)
        workspace_id = None
        try:
            import json as _json
            ctx2 = ssl.create_default_context()
            ctx2.check_hostname = False
            ctx2.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                f"{SANA_BASE_URL}/x-api/trpc/user.me",
                headers={"Cookie": f"sana-ai-session={session_cookie}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, context=ctx2, timeout=8) as r:
                data = _json.loads(r.read())
                workspace_id = data.get("result", {}).get("data", {}).get("user", {}).get("lastUsedWorkspaceId")
        except Exception:
            pass

        browser.close()

    if not session_cookie:
        raise RuntimeError(
            "sana-ai-session cookie not found — SAML login may not have completed."
        )

    print(f"    sana-ai-session captured ({len(session_cookie)} chars)")
    result = {"SANA_SESSION_COOKIE": session_cookie}
    if workspace_id:
        print(f"    workspace ID: {workspace_id}")
        result["SANA_WORKSPACE_ID"] = workspace_id
    else:
        # Fallback: extract from invite URL
        result["SANA_WORKSPACE_ID"] = SANA_INVITE_URL.rstrip("/").split("/")[-1]
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
        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
            elif "# --- Sana" in content:
                content = content.replace("# --- Sana\n", f"# --- Sana\n{new_line}\n", 1)
            else:
                content += f"\n# --- Sana ---\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("SANA_SESSION_COOKIE: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
