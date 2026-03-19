#!/usr/bin/env python3
"""
Grafana SSO session capture via Playwright.

Opens a headed Chromium window, completes SSO login, and captures:
  - GRAFANA_SESSION  — session cookie (~8h TTL)

Usage:
    python3 tool_connections/grafana/sso.py
    python3 tool_connections/grafana/sso.py --force      # skip validity check
    python3 tool_connections/grafana/sso.py --env-file /path/to/.env

Requirements:
    pip install playwright && playwright install chromium
    GRAFANA_BASE_URL must be set in .env (e.g. https://grafana.yourcompany.com)
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

GRAFANA_BASE_URL = load_env_var("GRAFANA_BASE_URL", "https://grafana.yourcompany.com")


def is_valid(env_path: Path) -> bool:
    env = load_env_file(env_path)
    session = env.get("GRAFANA_SESSION", "")
    if not session:
        return False
    status = http_get(
        f"{GRAFANA_BASE_URL}/api/user",
        {"Cookie": f"grafana_session={session}"},
    )
    return status == 200


def capture(base_url: str) -> dict:
    """Open Grafana, complete SSO, return {grafana_session}."""
    print(f"  Opening Grafana ({base_url})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(base_url, wait_until="networkidle", timeout=60_000)
        time.sleep(2)

        grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([base_url])}
        session = grafana_cookies.get("grafana_session")

        if not session:
            print("  Waiting for manual login (3 min timeout)...", flush=True)
            for _ in range(90):
                time.sleep(2)
                grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([base_url])}
                session = grafana_cookies.get("grafana_session")
                if session:
                    break

        browser.close()

    if not session:
        raise RuntimeError("No grafana_session cookie captured.")

    print(f"  Captured: GRAFANA_SESSION ({len(session)} chars)")
    return {"grafana_session": session}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--force", action="store_true", help="Refresh even if token is still valid")
    args = parser.parse_args()

    if "yourcompany" in GRAFANA_BASE_URL:
        print("ERROR: GRAFANA_BASE_URL is not set in .env")
        print("  Add: GRAFANA_BASE_URL=https://grafana.yourcompany.com")
        sys.exit(1)

    if not args.force and is_valid(args.env_file):
        print("GRAFANA_SESSION is valid — nothing to do. Use --force to refresh anyway.")
        return

    tokens = capture(GRAFANA_BASE_URL)
    update_env_file(args.env_file, tokens)
    print("\nDone.")


if __name__ == "__main__":
    main()
