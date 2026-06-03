"""
Slack SSO capture — plugin for playwright_sso.py discovery.

Navigates to your Slack workspace, completes Okta/SSO login, and extracts
the xoxc client token + d cookie from localStorage and browser cookies.

Standalone usage:
    python3 tool_connections/slack/sso.py
    python3 tool_connections/slack/sso.py --force
    python3 tool_connections/slack/sso.py --account acme --force
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

TOOL_NAME = "slack"
ENV_KEYS = ["SLACK_XOXC", "SLACK_D_COOKIE"]
ACCOUNT_ENV_KEYS = ["SLACK_WORKSPACE_URL"]


def check(env: dict) -> bool:
    """Return True if the selected Slack xoxc token is valid."""
    xoxc = env.get("SLACK_XOXC", "")
    d_cookie = env.get("SLACK_D_COOKIE", "")
    if not xoxc or xoxc.startswith("xoxc-your-"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://slack.com/api/auth.test",
            headers={
                "Authorization": f"Bearer {xoxc}",
                "Cookie": f"d={d_cookie}",
            },
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
            return json.loads(r.read()).get("ok") is True
    except Exception:
        return False


def _normalize_workspace_url(workspace_url: str) -> str:
    if workspace_url and "://" not in workspace_url:
        workspace_url = f"https://{workspace_url}"
    parsed = urllib.parse.urlparse(workspace_url)
    if not parsed.netloc:
        return workspace_url
    return f"{parsed.scheme or 'https'}://{parsed.netloc}/"


def _account_prefix(account: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", account).strip("_").upper()
    if not prefix:
        raise ValueError("--account must contain at least one letter or number")
    return prefix


def _account_env_key(account: str, key: str) -> str:
    """Backward-compatible account-first key, e.g. ACME_SLACK_XOXC."""
    return f"{_account_prefix(account)}_{key}"


def _scoped_env_key(account: str, key: str) -> str:
    """Tool-first account key, e.g. SLACK_ACME_XOXC."""
    if "_" not in key:
        return _account_env_key(account, key)
    namespace, suffix = key.split("_", 1)
    return f"{namespace}_{_account_prefix(account)}_{suffix}"


def _env_for_account(env: dict, account: str | None) -> dict:
    if not account:
        return dict(env)
    scoped = dict(env)
    for key in ACCOUNT_ENV_KEYS + ENV_KEYS:
        scoped_key = _scoped_env_key(account, key)
        legacy_key = _account_env_key(account, key)
        if scoped_key in env:
            scoped[key] = env[scoped_key]
        elif legacy_key in env:
            scoped[key] = env[legacy_key]
        else:
            scoped.pop(key, None)
    scoped["SSO_ACCOUNT"] = account
    scoped["SSO_ACCOUNT_PREFIX"] = _account_prefix(account)
    return scoped


def _tokens_for_account(tokens: dict, account: str | None) -> dict:
    if not account:
        return tokens
    return {_scoped_env_key(account, key): value for key, value in tokens.items()}


def capture(env: dict) -> dict:
    """Open Slack workspace in headed browser, extract xoxc + d cookie."""
    workspace_url = _normalize_workspace_url(env.get("SLACK_WORKSPACE_URL", ""))
    if not workspace_url or "yourcompany" in workspace_url:
        prefix = env.get("SSO_ACCOUNT_PREFIX", "")
        workspace_key = f"{prefix}_SLACK_WORKSPACE_URL" if prefix else "SLACK_WORKSPACE_URL"
        raise RuntimeError(
            f"{workspace_key} not set in .env. "
            f"Add {workspace_key}=https://yourcompany.slack.com/ and retry."
        )

    print(f"  Opening Slack ({workspace_url}) — SSO should auto-complete...")
    with sync_playwright() as p:
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        launch_kwargs = dict(
            headless=False,
            args=["--window-size=900,600", "--window-position=100,100"],
        )
        if os.path.exists(chrome_path):
            launch_kwargs["executable_path"] = chrome_path
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(workspace_url, wait_until="commit", timeout=30_000)
        print("    Waiting for Slack login to complete (up to 3 min — Ctrl+C to abort)...", flush=True)

        xoxc = None
        deadline = time.time() + 180
        next_heartbeat = time.time() + 15
        try:
            while time.time() < deadline:
                time.sleep(2)
                if time.time() >= next_heartbeat:
                    remaining = max(0, int(deadline - time.time()))
                    print(f"    Still waiting... ({remaining}s remaining — Ctrl+C to abort)", flush=True)
                    next_heartbeat = time.time() + 15
                try:
                    xoxc = page.evaluate("""(workspaceUrl) => {
                        const requestedHost = new URL(workspaceUrl).hostname.toLowerCase();
                        const requestedDomain = requestedHost.split('.')[0];

                        function tokenFromTeam(team) {
                            if (!team || typeof team !== 'object') return null;
                            const token = team.token || team.xoxc || team.client_token;
                            if (!token || !token.startsWith('xoxc')) return null;
                            const markers = [
                                team.domain,
                                team.url,
                                team.team_url,
                                team.teamUrl,
                                team.name,
                                team.team_name,
                                team.enterprise_url,
                            ].filter(Boolean).map(String).join(' ').toLowerCase();
                            if (markers.includes(requestedHost) || markers.includes(requestedDomain)) {
                                return token;
                            }
                            return null;
                        }

                        try {
                            const cfg = JSON.parse(localStorage.getItem('localConfig_v2') || 'null');
                            if (cfg && cfg.teams) {
                                for (const team of Object.values(cfg.teams)) {
                                    const token = tokenFromTeam(team);
                                    if (token) return token;
                                }

                                const tokens = Object.values(cfg.teams)
                                    .map(team => team && team.token)
                                    .filter(token => token && token.startsWith('xoxc'));
                                if (tokens.length === 1) return tokens[0];
                            }
                        } catch(e) {}
                        return null;
                    }""", workspace_url)
                except Exception:
                    continue
                if xoxc:
                    print("    Login detected!", flush=True)
                    break
        except KeyboardInterrupt:
            ctx.close()
            browser.close()
            raise RuntimeError("Aborted by user — Slack login did not complete.")

        if not xoxc:
            raise RuntimeError(
                "No xoxc token found for the requested workspace — login may not "
                "have completed, or multiple teams are present and none matched "
                f"{workspace_url}."
            )

        all_cookies = ctx.cookies(["https://slack.com", "https://app.slack.com", workspace_url])
        d_cookie = {c["name"]: c["value"] for c in all_cookies}.get("d", "")
        if not d_cookie:
            raise RuntimeError("No 'd' cookie found after Slack SSO.")

        ctx.close()
        browser.close()

    print(f"    Slack xoxc captured ({len(xoxc)} chars)")
    return {"SLACK_XOXC": xoxc, "SLACK_D_COOKIE": d_cookie}


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))
    from shared_utils.browser import DEFAULT_ENV_FILE

    ENV_FILE = DEFAULT_ENV_FILE

    def _clean_env_value(value: str) -> str:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value

    def _load_env():
        if not ENV_FILE.exists():
            return {}
        return {k.strip(): _clean_env_value(v) for line in ENV_FILE.read_text().splitlines()
                if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

    def _write_env(tokens):
        import re
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
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
    parser.add_argument("--account", help="Account/workspace name for scoped .env keys, e.g. SLACK_ACME_XOXC")
    parser.add_argument("--workspace-url", help="Override SLACK_WORKSPACE_URL from .env")
    args = parser.parse_args()

    env = _load_env()
    workspace_override = {}
    if args.workspace_url:
        key = _scoped_env_key(args.account, "SLACK_WORKSPACE_URL") if args.account else "SLACK_WORKSPACE_URL"
        workspace_override[key] = _normalize_workspace_url(args.workspace_url)
        env[key] = workspace_override[key]

    plugin_env = _env_for_account(env, args.account)
    if not args.force and check(plugin_env):
        key = _scoped_env_key(args.account, "SLACK_XOXC") if args.account else "SLACK_XOXC"
        print(f"{key}: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    raw = capture(plugin_env)
    tokens = {**workspace_override, **_tokens_for_account(raw, args.account)}
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
