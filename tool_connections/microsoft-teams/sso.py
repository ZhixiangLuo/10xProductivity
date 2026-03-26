"""
Microsoft Teams (personal) SSO capture — plugin for playwright_sso.py discovery.

Navigates to teams.live.com, completes Microsoft account login, and captures
the skypetoken from network request headers or localStorage.

Standalone usage:
    python3 tool_connections/microsoft-teams/sso.py
    python3 tool_connections/microsoft-teams/sso.py --force
"""

import sys
import time
import uuid

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import ssl
import urllib.request

TOOL_NAME = "teams"
ENV_KEYS = ["TEAMS_SKYPETOKEN", "TEAMS_SESSION_ID"]
TEAMS_URL = "https://teams.live.com/v2/"


def check(env: dict) -> bool:
    """Return True if TEAMS_SKYPETOKEN is valid."""
    token = env.get("TEAMS_SKYPETOKEN", "")
    if not token or token.startswith("your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://teams.live.com/api/csa/api/v1/teams/users/me",
            headers={"x-skypetoken": token},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def capture(env: dict) -> dict:
    """Open Teams (personal) in headed browser, capture skypetoken."""
    print(f"  Opening Microsoft Teams ({TEAMS_URL}) — login should auto-complete...")
    captured_headers: list[dict] = []
    skypetoken = None
    session_id = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        def _on_request(req):
            hdrs = req.headers
            if "x-skypetoken" in hdrs:
                captured_headers.append(hdrs)

        page.on("request", _on_request)
        page.goto(TEAMS_URL, wait_until="commit", timeout=30_000)
        print("    Waiting for Teams login to complete (up to 3 min)...", flush=True)

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
        session_id = str(uuid.uuid4())

    print(f"    Teams skypetoken captured ({len(skypetoken)} chars)")
    return {"TEAMS_SKYPETOKEN": skypetoken, "TEAMS_SESSION_ID": session_id}


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
            elif "# --- Microsoft Teams (personal)" in content:
                content = content.replace(
                    "# --- Microsoft Teams (personal)\n",
                    f"# --- Microsoft Teams (personal)\n{new_line}\n", 1)
            else:
                content += f"\n# --- Microsoft Teams (personal)\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("TEAMS_SKYPETOKEN: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
