"""
Microsoft Teams Enterprise SSO capture — plugin for playwright_sso.py discovery.

Extracts MSAL access tokens from Teams web app localStorage:
  - TEAMS_ENTERPRISE_GRAPH_TOKEN  — graph.microsoft.com (list teams, channels, read, search)
  - TEAMS_ENTERPRISE_CHATSVC_TOKEN — chatsvc API (read + post messages, DMs, thread replies)

Navigates to teams.microsoft.com using a persistent browser profile so MFA is
only required once. On subsequent runs the saved Azure AD session auto-completes.

Standalone usage:
    python3 tool_connections/microsoft-teams-enterprise/sso.py
    python3 tool_connections/microsoft-teams-enterprise/sso.py --force
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))

from shared_utils.browser import (
    sync_playwright,
    load_env_file,
    update_env_file,
    http_get,
    DEFAULT_ENV_FILE,
    BROWSER_AUTOMATION_DIR,
)

TOOL_NAME = "teams-enterprise"
ENV_KEYS = ["TEAMS_ENTERPRISE_GRAPH_TOKEN", "TEAMS_ENTERPRISE_CHATSVC_TOKEN"]
TEAMS_URL = "https://teams.microsoft.com/"
PROFILE_DIR = BROWSER_AUTOMATION_DIR / "teams_enterprise_profile"


def check(env: dict) -> bool:
    """Return True if both tokens are present and valid."""
    graph_token = env.get("TEAMS_ENTERPRISE_GRAPH_TOKEN", "")
    chatsvc_token = env.get("TEAMS_ENTERPRISE_CHATSVC_TOKEN", "")
    if not graph_token or len(graph_token) < 100:
        return False
    if not chatsvc_token or len(chatsvc_token) < 100:
        return False
    return http_get("https://graph.microsoft.com/v1.0/me",
                    {"Authorization": f"Bearer {graph_token}"}) == 200


def capture(env: dict) -> dict:
    """
    Open Teams enterprise in a persistent headed browser, extract MSAL access
    tokens from localStorage.

    First run: complete login + MFA in the browser window (~60s).
    Subsequent runs: Azure AD session cookie auto-completes (~15s).
    Token TTL: ~1h.

    Returns:
        dict with TEAMS_ENTERPRISE_GRAPH_TOKEN and optionally
        TEAMS_ENTERPRISE_CHATSVC_TOKEN if found in localStorage.
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"  Opening Teams ({TEAMS_URL}) — login auto-completes if profile is saved...")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            args=["--window-size=1200,800"],
        )
        page = ctx.new_page()
        page.goto(TEAMS_URL, wait_until="networkidle", timeout=60_000)
        print("    Teams loaded. Extracting token from MSAL cache...", flush=True)
        time.sleep(3)

        # MSAL stores access tokens as flat entries in localStorage:
        # key: <oid>.<tid>-login.windows.net-accesstoken-<clientId>-<tid>-<scopes>--
        # value: JSON with credentialType="AccessToken" and secret=<jwt>
        msal_tokens = page.evaluate("""() => {
            const out = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const raw = localStorage.getItem(key);
                if (!raw) continue;
                try {
                    const obj = JSON.parse(raw);
                    const check = (k, v) => {
                        if (v && v.credentialType === 'AccessToken' && v.secret && v.target)
                            out[k] = {secret: v.secret, target: v.target};
                    };
                    check(key, obj);
                    if (obj && typeof obj === 'object')
                        for (const [k2, v2] of Object.entries(obj)) check(k2, v2);
                } catch(e) {}
            }
            return out;
        }""")

        ctx.close()

    # Extract Graph token (prefer one with Chat/Channel scopes)
    graph_token = None
    for k, v in msal_tokens.items():
        t = v["target"]
        if "graph.microsoft.com" in t and ("Chat" in t or "Channel" in t):
            graph_token = v["secret"]
            print(f"    Graph+Chat token found ({len(graph_token)} chars)", flush=True)
            break
    if not graph_token:
        for k, v in msal_tokens.items():
            if "graph.microsoft.com" in v["target"]:
                graph_token = v["secret"]
                print(f"    Graph token found ({len(graph_token)} chars)", flush=True)
                break

    # Extract chatsvc token (Teams internal API — used for read + post)
    chatsvc_token = None
    for k, v in msal_tokens.items():
        if "chatsvcagg.teams.microsoft.com" in v["target"] or "chatsvc" in v["target"].lower():
            chatsvc_token = v["secret"]
            print(f"    chatsvc token found ({len(chatsvc_token)} chars)", flush=True)
            break

    if not graph_token:
        raise RuntimeError(
            "No MSAL Graph token found in Teams localStorage.\n"
            "Ensure Teams loaded fully and you are logged in.\n"
            f"Tip: delete {PROFILE_DIR} and retry to force fresh login."
        )

    result = {"TEAMS_ENTERPRISE_GRAPH_TOKEN": graph_token}
    if chatsvc_token:
        result["TEAMS_ENTERPRISE_CHATSVC_TOKEN"] = chatsvc_token
    else:
        # chatsvc token may not appear in localStorage on all tenants.
        # It will be present from a previous run in .env — only the graph token is refreshed here.
        print("    Warning: chatsvc token not in localStorage — keeping existing .env value", flush=True)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = load_env_file(DEFAULT_ENV_FILE)
    if not args.force and check(env):
        print("Tokens valid — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    update_env_file(DEFAULT_ENV_FILE, tokens)
    print(f"  Written to {DEFAULT_ENV_FILE}")
