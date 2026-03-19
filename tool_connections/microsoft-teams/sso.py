#!/usr/bin/env python3
"""
Microsoft Teams (personal) SSO session capture via Playwright.

Opens a headed Chromium window, completes Microsoft personal account login, and captures:
  - TEAMS_SKYPETOKEN  — x-skypetoken (~24h TTL)
  - TEAMS_SESSION_ID  — x-ms-session-id (~24h TTL)

NOTE: This is for personal Microsoft accounts (teams.live.com).
Enterprise Teams (teams.microsoft.com) uses Microsoft Graph API instead.

Usage:
    python3 tool_connections/microsoft-teams/sso.py
    python3 tool_connections/microsoft-teams/sso.py --force
    python3 tool_connections/microsoft-teams/sso.py --env-file /path/to/.env

Requirements:
    pip install playwright && playwright install chromium
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from shared_utils.browser import (
    sync_playwright, load_env_file, update_env_file,
    http_get, DEFAULT_ENV_FILE,
)

TEAMS_URL = "https://teams.live.com/v2/"


def is_valid(env_path: Path) -> bool:
    env = load_env_file(env_path)
    token = env.get("TEAMS_SKYPETOKEN", "")
    if not token or token.startswith("your-"):
        return False
    status = http_get(
        "https://teams.live.com/api/csa/api/v1/teams/users/me",
        {"x-skypetoken": token},
    )
    return status == 200


def capture() -> dict:
    """Open Teams (personal), complete login, return {teams_skypetoken, teams_session_id}."""
    print(f"  Opening Microsoft Teams personal ({TEAMS_URL})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(TEAMS_URL, wait_until="commit", timeout=30_000)
        print("  Waiting for Teams login to complete (up to 3 min)...", flush=True)

        skypetoken = None
        session_id = None
        captured_headers: list[dict] = []

        def _on_request(req):
            hdrs = req.headers
            if "x-skypetoken" in hdrs:
                captured_headers.append(hdrs)

        page.on("request", _on_request)
        deadline = time.time() + 180

        while time.time() < deadline:
            time.sleep(2)
            for hdrs in captured_headers:
                t = hdrs.get("x-skypetoken", "")
                s = hdrs.get("x-ms-session-id", "")
                if t and not t.startswith("your-"):
                    skypetoken = t
                    session_id = s or session_id
                    break
            if skypetoken:
                break
            try:
                skypetoken = page.evaluate("""() => {
                    try {
                        for (let i = 0; i < localStorage.length; i++) {
                            const raw = localStorage.getItem(localStorage.key(i)) || '';
                            const m = raw.match(/"skypeToken":"([^"]+)"/);
                            if (m) return m[1];
                            const m2 = raw.match(/"SkypeToken":"([^"]+)"/);
                            if (m2) return m2[1];
                        }
                    } catch(e) {}
                    return null;
                }""")
            except Exception:
                continue
            if skypetoken:
                break

        browser.close()

    if not skypetoken:
        raise RuntimeError("No x-skypetoken captured — login may not have completed within 3 minutes.")

    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        print("  x-ms-session-id not captured — generated a new UUID.")

    print(f"  Captured: TEAMS_SKYPETOKEN ({len(skypetoken)} chars)")
    return {"teams_skypetoken": skypetoken, "teams_session_id": session_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--force", action="store_true", help="Refresh even if token is still valid")
    args = parser.parse_args()

    if not args.force and is_valid(args.env_file):
        print("TEAMS_SKYPETOKEN is valid — nothing to do. Use --force to refresh anyway.")
        return

    tokens = capture()
    update_env_file(args.env_file, tokens)
    print("\nDone.")


if __name__ == "__main__":
    main()
