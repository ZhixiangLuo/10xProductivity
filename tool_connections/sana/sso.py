"""
Sana (sana.ai) session capture — plugin for tool_connections/shared_utils/playwright_sso.py.

Opens your Sana workspace URL in a headed browser, completes SSO if prompted, and
extracts the `sana-ai-session` cookie.

.env before capture:
  SANA_WORKSPACE_URL=https://sana.ai/your-workspace-id   (or /profile URL)

Standalone:
    python3 tool_connections/sana/sso.py
    python3 tool_connections/sana/sso.py --force
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import os

    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

TOOL_NAME = "sana"
ENV_KEYS = ["SANA_SESSION", "SANA_WORKSPACE_URL", "SANA_WORKSPACE_ID"]


def _workspace_id_from_url(url: str) -> str:
    if not url or "://" not in url:
        return ""
    path = urlparse(url.strip()).path.strip("/").split("/")
    # https://sana.ai/{workspaceId}/...  → first segment
    return path[0] if path and path[0] not in ("", "signin", "login") else ""


def check(env: dict) -> bool:
    """True if SANA_SESSION is valid (user.me returns 200)."""
    session = env.get("SANA_SESSION", "").strip()
    if not session or session == "your-sana-session-cookie":
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://sana.ai/x-api/trpc/user.me",
            headers={"Cookie": f"sana-ai-session={session}"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    base = env.get("SANA_WORKSPACE_URL", "").strip().rstrip("/")
    if not base or "your-workspace" in base.lower() or "example" in base.lower():
        raise RuntimeError(
            "Set SANA_WORKSPACE_URL in .env to your workspace entry URL, e.g. "
            "https://sana.ai/your-workspace-id (open Sana in the browser and copy "
            "the URL after login). Then retry."
        )

    wid = env.get("SANA_WORKSPACE_ID", "").strip() or _workspace_id_from_url(base)
    if not wid:
        raise RuntimeError(
            "Could not derive workspace id from SANA_WORKSPACE_URL. "
            "Set SANA_WORKSPACE_ID explicitly to the workspace slug from the URL."
        )

    # Normalize entry URL (avoid /agent/... as sole entry — parent workspace path is enough)
    entry = base
    if "/agent/" in entry:
        entry = re.sub(r"/agent/.*$", "", entry).rstrip("/") or base

    print(f"  Opening Sana ({entry}) — complete SSO if prompted (up to 3 min)...", flush=True)
    session = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1100,800", "--window-position=120,120"],
        )
        try:
            ctx = browser.new_context(ignore_https_errors=True)
            page = ctx.new_page()
            page.goto(entry, wait_until="domcontentloaded", timeout=90_000)

            deadline = time.time() + 180
            while time.time() < deadline:
                time.sleep(2)
                cookies = {c["name"]: c["value"] for c in ctx.cookies(["https://sana.ai"])}
                session = cookies.get("sana-ai-session")
                if session:
                    break
        finally:
            browser.close()

    if not session:
        raise RuntimeError(
            "No sana-ai-session cookie after timeout — finish signing in and run again."
        )

    print(f"    Sana session captured ({len(session)} chars)")
    return {
        "SANA_SESSION": session,
        "SANA_WORKSPACE_ID": wid,
        "SANA_WORKSPACE_URL": entry,
    }


if __name__ == "__main__":
    import argparse

    ENV_FILE = Path(__file__).parents[2] / ".env"

    def _load_env():
        if not ENV_FILE.exists():
            return {}
        return {
            k.strip(): v.strip()
            for line in ENV_FILE.read_text().splitlines()
            if "=" in line and not line.startswith("#")
            for k, v in [line.split("=", 1)]
        }

    def _write_env(tokens: dict[str, str]) -> None:
        import re as _re

        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if _re.search(rf"^{_re.escape(key)}=", content, flags=_re.MULTILINE):
                content = _re.sub(
                    rf"^{_re.escape(key)}=.*$", new_line, content, flags=_re.MULTILINE
                )
            else:
                content += f"\n{new_line}\n"
        ENV_FILE.write_text(content)
        print(f"  Updated {ENV_FILE}")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("SANA_SESSION ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print("Done.")
