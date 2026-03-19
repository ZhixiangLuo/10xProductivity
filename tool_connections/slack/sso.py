#!/usr/bin/env python3
"""
Slack SSO session capture via Playwright.

Opens a headed Chromium window, completes SSO login, and captures:
  - SLACK_XOXC       — client token (~8h TTL)
  - SLACK_D_COOKIE   — session cookie (~8h TTL)

Usage:
    python3 tool_connections/slack/sso.py
    python3 tool_connections/slack/sso.py --force      # skip validity check
    python3 tool_connections/slack/sso.py --env-file /path/to/.env

Requirements:
    pip install playwright && playwright install chromium
    SLACK_WORKSPACE_URL must be set in .env (e.g. https://yourcompany.slack.com/)
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from shared_utils.browser import (
    sync_playwright, load_env_var, load_env_file,
    update_env_file, http_get, DEFAULT_ENV_FILE,
)

SLACK_WORKSPACE_URL = load_env_var("SLACK_WORKSPACE_URL", "https://yourcompany.slack.com/")


def is_valid(env_path: Path) -> bool:
    env = load_env_file(env_path)
    xoxc = env.get("SLACK_XOXC", "")
    if not xoxc or xoxc.startswith("xoxc-your-"):
        return False
    import ssl, json, urllib.request
    try:
        req = urllib.request.Request(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {xoxc}"},
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            return json.loads(resp.read()).get("ok") is True
    except Exception:
        return False


def capture(workspace_url: str) -> dict:
    """Open Slack workspace, complete SSO, return {slack_xoxc, slack_d_cookie}."""
    print(f"  Opening Slack ({workspace_url})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=900,600", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(workspace_url, wait_until="commit", timeout=30_000)
        print("  Waiting for Slack login to complete (up to 3 min)...", flush=True)

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
            browser.close()
            raise RuntimeError("No xoxc token found — login may not have completed within 3 minutes.")

        all_cookies = ctx.cookies(["https://slack.com", "https://app.slack.com"])
        d_cookie = {c["name"]: c["value"] for c in all_cookies}.get("d", "")
        browser.close()

    if not d_cookie:
        raise RuntimeError("No 'd' cookie found after Slack SSO.")

    print(f"  Captured: SLACK_XOXC ({len(xoxc)} chars), SLACK_D_COOKIE ({len(d_cookie)} chars)")
    return {"slack_xoxc": xoxc, "slack_d_cookie": d_cookie}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--force", action="store_true", help="Refresh even if token is still valid")
    args = parser.parse_args()

    if "yourcompany" in SLACK_WORKSPACE_URL:
        print("ERROR: SLACK_WORKSPACE_URL is not set in .env")
        print("  Add: SLACK_WORKSPACE_URL=https://yourcompany.slack.com/")
        sys.exit(1)

    if not args.force and is_valid(args.env_file):
        print("SLACK_XOXC is valid — nothing to do. Use --force to refresh anyway.")
        return

    tokens = capture(SLACK_WORKSPACE_URL)
    update_env_file(args.env_file, tokens)
    print("\nDone.")


if __name__ == "__main__":
    main()
