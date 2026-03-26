"""
Grafana SSO capture — plugin for playwright_sso.py discovery.

Navigates to your Grafana instance, completes SSO login, and captures
the grafana_session cookie.

Standalone usage:
    python3 tool_connections/grafana/sso.py
    python3 tool_connections/grafana/sso.py --force
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

TOOL_NAME = "grafana"
ENV_KEYS = ["GRAFANA_SESSION"]


def check(env: dict) -> bool:
    """Return True if GRAFANA_SESSION is valid."""
    session = env.get("GRAFANA_SESSION", "")
    base = env.get("GRAFANA_BASE_URL", "")
    if not session or not base or "yourcompany" in base:
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            f"{base.rstrip('/')}/api/user",
            headers={"Cookie": f"grafana_session={session}"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """Open Grafana in headed browser, complete SSO, return grafana_session cookie."""
    base = env.get("GRAFANA_BASE_URL", "")
    if not base or "yourcompany" in base:
        raise RuntimeError(
            "GRAFANA_BASE_URL not set in .env. "
            "Add GRAFANA_BASE_URL=https://grafana.yourcompany.com and retry."
        )

    print(f"  Opening Grafana ({base}) — SSO should auto-complete...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.goto(base, wait_until="networkidle", timeout=60_000)
        time.sleep(2)

        grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([base])}
        session = grafana_cookies.get("grafana_session")

        if not session:
            print("  Waiting for manual login (3 min timeout)...", flush=True)
            for _ in range(90):
                time.sleep(2)
                grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([base])}
                session = grafana_cookies.get("grafana_session")
                if session:
                    break

        browser.close()

    if not session:
        raise RuntimeError("No grafana_session cookie captured.")

    print(f"    Grafana session captured ({len(session)} chars)")
    return {"GRAFANA_SESSION": session}


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
            elif "# --- Grafana" in content:
                content = content.replace("# --- Grafana\n", f"# --- Grafana\n{new_line}\n", 1)
            else:
                content += f"\n# --- Grafana\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("GRAFANA_SESSION: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
