"""
Slack SSO capture — plugin for playwright_sso.py discovery.

Navigates to your Slack workspace, completes Okta/SSO login, and extracts
the xoxc client token + d cookie from localStorage and browser cookies.

Standalone usage:
    python3 tool_connections/slack/sso.py
    python3 tool_connections/slack/sso.py --force
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
import json

TOOL_NAME = "slack"
ENV_KEYS = ["SLACK_XOXC", "SLACK_D_COOKIE"]


def check(env: dict) -> bool:
    """Return True if SLACK_XOXC is valid."""
    xoxc = env.get("SLACK_XOXC", "")
    if not xoxc or xoxc.startswith("xoxc-your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {xoxc}"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return json.loads(r.read()).get("ok") is True
    except Exception:
        return False


def capture(env: dict) -> dict:
    """Open Slack workspace in headed browser, extract xoxc + d cookie."""
    workspace_url = env.get("SLACK_WORKSPACE_URL", "")
    if not workspace_url or "yourcompany" in workspace_url:
        raise RuntimeError(
            "SLACK_WORKSPACE_URL not set in .env. "
            "Add SLACK_WORKSPACE_URL=https://yourcompany.slack.com/ and retry."
        )

    print(f"  Opening Slack ({workspace_url}) — SSO should auto-complete...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=900,600", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(workspace_url, wait_until="commit", timeout=30_000)
        print("    Waiting for Slack login to complete (up to 3 min)...", flush=True)

        xoxc = None
        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(2)
            try:
                xoxc = page.evaluate("""() => {
                    try {
                        const cfg = JSON.parse(localStorage.getItem('localConfig_v2') || 'null');
                        if (cfg && cfg.teams) {
                            const tid = Object.keys(cfg.teams)[0];
                            const t = cfg.teams[tid]?.token;
                            if (t && t.startsWith('xoxc')) return t;
                        }
                    } catch(e) {}
                    for (let i = 0; i < localStorage.length; i++) {
                        const raw = localStorage.getItem(localStorage.key(i)) || '';
                        const m = raw.match(/xoxc-[a-zA-Z0-9%-]+/);
                        if (m) return m[0];
                    }
                    return null;
                }""")
            except Exception:
                continue
            if xoxc:
                break

        if not xoxc:
            raise RuntimeError("No xoxc token found — login may not have completed within 3 minutes.")

        all_cookies = ctx.cookies(["https://slack.com", "https://app.slack.com"])
        d_cookie = {c["name"]: c["value"] for c in all_cookies}.get("d", "")
        if not d_cookie:
            raise RuntimeError("No 'd' cookie found after Slack SSO.")

        browser.close()

    print(f"    Slack xoxc captured ({len(xoxc)} chars)")
    return {"SLACK_XOXC": xoxc, "SLACK_D_COOKIE": d_cookie}


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
            elif "# --- Slack" in content:
                content = content.replace("# --- Slack\n", f"# --- Slack\n{new_line}\n", 1)
            else:
                content += f"\n# --- Slack\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("SLACK_XOXC: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
