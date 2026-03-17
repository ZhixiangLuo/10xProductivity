#!/usr/bin/env python3
"""
SSO session refresher via Playwright.

Opens a headed Chromium window, completes SSO login (auto-completes on managed
machines via enterprise SSO extensions), and captures session tokens/cookies for:

  - Grafana session cookie (~8h TTL)          → GRAFANA_SESSION in .env
  - Slack session token (~8h TTL)             → SLACK_XOXC + SLACK_D_COOKIE in .env
  - Google Drive session (days/weeks)         → ~/.browser_automation/gdrive_auth.json

By default, existing tokens are validated first — the browser only opens if one
or more have expired. Use --force to always refresh.

Usage (CLI):
    python3 playwright_sso.py [--env-file PATH] [--force]
    python3 playwright_sso.py --slack-only    # refresh only Slack credentials
    python3 playwright_sso.py --gdrive-only   # refresh only Google Drive session
    python3 playwright_sso.py --grafana-only  # refresh only Grafana session

Usage (library):
    from playwright_sso import check_tokens, get_grafana_session, get_slack_session
    status = check_tokens(grafana_session=..., slack_xoxc=...)
    tokens = get_grafana_session()   # {"grafana_session": "..."}
    tokens = get_slack_session()     # {"slack_xoxc": "...", "slack_d_cookie": "..."}

Configuration:
    Set these in your .env file (see env.sample):
      GRAFANA_BASE_URL    — your Grafana instance URL
      SLACK_WORKSPACE_URL — your Slack workspace URL (e.g. https://yourcompany.slack.com/)
    Or override the constants below directly.

Requirements:
    pip install playwright && playwright install chromium
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Installing playwright...")
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ---------------------------------------------------------------------------
# Configuration — set these or override via .env
# ---------------------------------------------------------------------------

def _load_env_var(key: str, default: str) -> str:
    """Load a var from .env file or environment, falling back to default."""
    env_file = Path(__file__).parents[2] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, default)

GRAFANA_BASE_URL    = _load_env_var("GRAFANA_BASE_URL", "https://grafana.yourcompany.com")
SLACK_WORKSPACE_URL = _load_env_var("SLACK_WORKSPACE_URL", "https://yourcompany.slack.com/")
GDRIVE_URL          = "https://drive.google.com/drive/my-drive"
GDRIVE_AUTH_FILE    = Path.home() / ".browser_automation" / "gdrive_auth.json"
DEFAULT_ENV_FILE    = Path(__file__).parents[2] / ".env"


# ---------------------------------------------------------------------------
# Token validation (no browser needed)
# ---------------------------------------------------------------------------

def _http_get(url: str, headers: dict) -> int:
    """Make a GET request and return the HTTP status code."""
    try:
        import ssl
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def _http_get_no_redirect(url: str, headers: dict) -> int:
    """GET without following redirects — returns 302 for expired sessions."""
    import ssl

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    try:
        opener = urllib.request.build_opener(_NoRedirect())
        req = urllib.request.Request(url, headers=headers)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        with opener.open(req, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def check_tokens(
    grafana_session: str | None = None,
    slack_xoxc: str | None = None,
    gdrive_sapisid: str | None = None,
    gdrive_cookies: str | None = None,
) -> dict[str, bool]:
    """
    Validate existing tokens with lightweight API calls (no browser).
    Returns validity flags: {"grafana_session": bool, "slack_xoxc": bool, "gdrive": bool}
    """
    result = {
        "grafana_session": False,
        "slack_xoxc": False,
        "gdrive": False,
    }

    if grafana_session:
        status = _http_get(
            f"{GRAFANA_BASE_URL}/api/user",
            {"Cookie": f"grafana_session={grafana_session}"},
        )
        result["grafana_session"] = status == 200

    if slack_xoxc and not slack_xoxc.startswith("xoxc-your-"):
        try:
            import ssl, json as _json
            req = urllib.request.Request(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {slack_xoxc}"},
            )
            ctx2 = ssl.create_default_context()
            ctx2.check_hostname = False
            ctx2.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx2, timeout=8) as resp:
                body = _json.loads(resp.read())
                result["slack_xoxc"] = body.get("ok") is True
        except Exception:
            result["slack_xoxc"] = False

    if gdrive_sapisid and gdrive_cookies:
        import hashlib
        ts = str(int(time.time()))
        sha1 = hashlib.sha1(f"{ts} {gdrive_sapisid} https://drive.google.com".encode()).hexdigest()
        auth = f"SAPISIDHASH {ts}_{sha1}"
        status = _http_get(
            "https://drive.google.com/drive/v2internal/about?fields=user",
            {"Authorization": auth, "Cookie": gdrive_cookies, "X-Goog-AuthUser": "0"},
        )
        result["gdrive"] = status == 200

    return result


def load_tokens_from_env(env_path: Path) -> dict[str, str | None]:
    """Read session tokens/cookies from a .env file."""
    tokens: dict[str, str | None] = {
        "grafana_session": None,
        "slack_xoxc": None,
        "slack_d_cookie": None,
        "gdrive_cookies": None,
        "gdrive_sapisid": None,
    }
    if not env_path.exists():
        return tokens
    for line in env_path.read_text().splitlines():
        if line.startswith("GRAFANA_SESSION="):
            tokens["grafana_session"] = line.split("=", 1)[1].strip()
        elif line.startswith("SLACK_XOXC="):
            tokens["slack_xoxc"] = line.split("=", 1)[1].strip()
        elif line.startswith("SLACK_D_COOKIE="):
            tokens["slack_d_cookie"] = line.split("=", 1)[1].strip()
        elif line.startswith("GDRIVE_COOKIES="):
            tokens["gdrive_cookies"] = line.split("=", 1)[1].strip()
        elif line.startswith("GDRIVE_SAPISID="):
            tokens["gdrive_sapisid"] = line.split("=", 1)[1].strip()
    return tokens


# ---------------------------------------------------------------------------
# Grafana session
# ---------------------------------------------------------------------------

def get_grafana_session() -> dict[str, str]:
    """
    Navigate to Grafana in a headed browser, complete SSO login, and return
    {"grafana_session": "<cookie value>"}.

    On managed machines with enterprise SSO, this completes automatically.
    On personal machines, the login page opens — complete it manually once.
    """
    print(f"  [1/1] Getting Grafana session (navigating to {GRAFANA_BASE_URL})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        page.goto(GRAFANA_BASE_URL, wait_until="networkidle", timeout=60_000)
        time.sleep(2)

        grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([GRAFANA_BASE_URL])}
        grafana_session = grafana_cookies.get("grafana_session")

        if not grafana_session:
            # Wait for manual login if needed
            print("  Waiting for manual login (3 min timeout)...", flush=True)
            for _ in range(90):
                time.sleep(2)
                grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([GRAFANA_BASE_URL])}
                grafana_session = grafana_cookies.get("grafana_session")
                if grafana_session:
                    break

        browser.close()

    if not grafana_session:
        raise RuntimeError("No grafana_session cookie captured.")

    print(f"    Grafana session captured ({len(grafana_session)} chars)")
    return {"grafana_session": grafana_session}


# ---------------------------------------------------------------------------
# Slack session
# ---------------------------------------------------------------------------

def _extract_slack_session(page, ctx) -> tuple[str, str]:
    """Navigate to Slack workspace and extract the xoxc client token + d cookie."""
    page.goto(SLACK_WORKSPACE_URL, wait_until="commit", timeout=30_000)
    # Wait for the Slack app to fully load — indicated by the xoxc token appearing
    # in localStorage. This handles SSO (auto), manual login, and CAPTCHA flows.
    # Polls every 2s for up to 3 minutes.
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
            # Page navigated mid-evaluate — normal during login redirects, just retry
            continue
        if xoxc:
            break
    if "slack.com" not in page.url:
        raise RuntimeError(f"Slack login timed out — ended up on: {page.url}")

    print(f"    Page after login: {page.url}", flush=True)

    if not xoxc:
        raise RuntimeError("No xoxc token found — login may not have completed within 3 minutes.")

    all_cookies = ctx.cookies(["https://slack.com", "https://app.slack.com"])
    d_cookie = {c["name"]: c["value"] for c in all_cookies}.get("d", "")
    if not d_cookie:
        raise RuntimeError("No 'd' cookie found after Slack SSO.")

    return xoxc, d_cookie


def get_slack_session() -> dict[str, str]:
    """
    Open Slack workspace in a headed browser, complete SSO login, and return
    {"slack_xoxc": "...", "slack_d_cookie": "..."}.

    On managed machines, SSO auto-completes. On personal machines, complete login manually.
    Session lifetime: ~8h.
    """
    print(f"  [1/1] Getting Slack session (navigating to {SLACK_WORKSPACE_URL})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=900,600", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        xoxc, d_cookie = _extract_slack_session(page, ctx)
        browser.close()
    print(f"    Slack xoxc captured ({len(xoxc)} chars)")
    return {"slack_xoxc": xoxc, "slack_d_cookie": d_cookie}


# ---------------------------------------------------------------------------
# Google Drive session
# ---------------------------------------------------------------------------

def _extract_gdrive_session(page, ctx) -> dict[str, str]:
    """
    Navigate to Google Drive, complete Google Workspace SSO, and save storage_state.

    IMPORTANT: Raw cookie injection (ctx.add_cookies) triggers Google's CookieMismatch
    security check. Playwright's storage_state correctly replays the full browser
    session (cookies + fingerprint) and is the only approach that works.

    Returns {"gdrive_cookies": "...", "gdrive_sapisid": "..."} and saves the full
    session to GDRIVE_AUTH_FILE — that file is what google-drive.md uses for all
    subsequent Drive access.
    """
    page.goto(GDRIVE_URL, wait_until="commit", timeout=30_000)

    try:
        page.wait_for_url("https://drive.google.com/**", timeout=60_000)
    except PlaywrightTimeout:
        if "accounts.google.com" in page.url or "google.com/signin" in page.url:
            print("  Google sign-in page — complete login manually (3 min timeout)...", flush=True)
            page.wait_for_url("https://drive.google.com/**", timeout=180_000)
        else:
            raise RuntimeError(f"Unexpected URL after Google Drive navigation: {page.url}")

    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except PlaywrightTimeout:
        pass
    time.sleep(3)

    GDRIVE_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    ctx.storage_state(path=str(GDRIVE_AUTH_FILE))
    print(f"    storage_state saved to {GDRIVE_AUTH_FILE} ({GDRIVE_AUTH_FILE.stat().st_size} bytes)")

    google_cookies = ctx.cookies([
        "https://google.com", "https://www.google.com",
        "https://drive.google.com", "https://accounts.google.com",
    ])
    cookie_dict = {c["name"]: c["value"] for c in google_cookies}
    sapisid = cookie_dict.get("SAPISID", "")

    cookie_keys = [
        "SID", "HSID", "SSID", "APISID", "SAPISID",
        "__Secure-1PSID", "__Secure-3PSID",
        "__Secure-1PAPISID", "__Secure-3PAPISID",
        "__Secure-1PSIDTS", "__Secure-3PSIDTS",
        "__Secure-1PSIDCC", "__Secure-3PSIDCC",
        "NID", "ACCOUNT_CHOOSER",
    ]
    cookie_str = "; ".join(
        f"{k}={cookie_dict[k]}" for k in cookie_keys
        if k in cookie_dict and cookie_dict[k]
    )
    return {"gdrive_cookies": cookie_str, "gdrive_sapisid": sapisid}


def get_gdrive_session() -> dict[str, str]:
    """
    Open Google Drive in a headed browser, complete Google Workspace SSO (~30s),
    save full browser session to ~/.browser_automation/gdrive_auth.json, and return
    cookie info for .env.

    The storage_state file is what the google-drive skill uses to authenticate.
    Raw cookie injection does not work for Google (triggers CookieMismatch).
    Session lifetime: days to weeks.
    """
    print("  [1/1] Getting Google Drive session (Google Workspace SSO, ~30s)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        result = _extract_gdrive_session(page, ctx)
        browser.close()
    print(f"    SAPISID captured ({len(result['gdrive_sapisid'])} chars)")
    return result


# ---------------------------------------------------------------------------
# .env writer
# ---------------------------------------------------------------------------

def update_env_file(env_path: Path, tokens: dict[str, str]) -> None:
    """Write / update token values in .env file."""
    if not env_path.exists():
        env_path.write_text("")
    content = env_path.read_text()

    def _upsert(text: str, key: str, value: str, section_hint: str) -> str:
        pattern = rf"^({re.escape(key)}=).*$"
        new_line = f"{key}={value}"
        if re.search(pattern, text, flags=re.MULTILINE):
            return re.sub(pattern, new_line, text, flags=re.MULTILINE)
        if section_hint and section_hint in text:
            return re.sub(
                rf"({re.escape(section_hint)}[^\n]*\n)",
                r"\1" + new_line + "\n",
                text,
            )
        return text + f"\n{new_line}\n"

    if "grafana_session" in tokens:
        content = _upsert(content, "GRAFANA_SESSION", tokens["grafana_session"], "# --- Grafana")
    if "slack_xoxc" in tokens:
        content = _upsert(content, "SLACK_XOXC", tokens["slack_xoxc"], "# --- Slack")
    if "slack_d_cookie" in tokens:
        content = _upsert(content, "SLACK_D_COOKIE", tokens["slack_d_cookie"], "# --- Slack")
    if "gdrive_cookies" in tokens:
        content = _upsert(content, "GDRIVE_COOKIES", tokens["gdrive_cookies"], "# --- Google Drive")
    if "gdrive_sapisid" in tokens:
        content = _upsert(content, "GDRIVE_SAPISID", tokens["gdrive_sapisid"], "# --- Google Drive")

    env_path.write_text(content)
    print(f"  Updated {env_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--env-file", type=Path, default=DEFAULT_ENV_FILE, metavar="PATH",
        help=f"Path to .env file (default: {DEFAULT_ENV_FILE})",
    )
    parser.add_argument("--force", action="store_true", help="Always refresh, even if tokens are valid")
    parser.add_argument("--slack-only", action="store_true", help="Refresh Slack session only")
    parser.add_argument("--gdrive-only", action="store_true", help="Refresh Google Drive session only")
    parser.add_argument("--grafana-only", action="store_true", help="Refresh Grafana session only")
    args = parser.parse_args()

    print("SSO token refresher (Playwright)")
    print(f"  .env: {args.env_file}")
    print()

    # Check that required base URLs are configured before opening any browser
    issues = []
    if not args.slack_only and not args.gdrive_only:
        if "yourcompany" in GRAFANA_BASE_URL or GRAFANA_BASE_URL == "https://grafana.yourcompany.com":
            issues.append(f"  GRAFANA_BASE_URL is not set (currently: {GRAFANA_BASE_URL})\n"
                          f"  → Add GRAFANA_BASE_URL=https://grafana.yourcompany.com to .env first")
    if not args.grafana_only and not args.gdrive_only:
        if "yourcompany" in SLACK_WORKSPACE_URL or SLACK_WORKSPACE_URL == "https://yourcompany.slack.com/":
            issues.append(f"  SLACK_WORKSPACE_URL is not set (currently: {SLACK_WORKSPACE_URL})\n"
                          f"  → Add SLACK_WORKSPACE_URL=https://yourcompany.slack.com/ to .env first")
    if issues:
        print("⚠ Configuration required before running SSO:\n")
        for issue in issues:
            print(issue)
        print("\nEdit .env, then re-run this script.")
        sys.exit(1)

    # --- Slack-only ---
    if args.slack_only:
        if not args.force:
            existing = load_tokens_from_env(args.env_file)
            validity = check_tokens(slack_xoxc=existing["slack_xoxc"])
            if validity["slack_xoxc"]:
                print("  SLACK_XOXC: ok — nothing to do.")
                return
            print("  SLACK_XOXC: expired or missing")
            print()
        tokens = get_slack_session()
        update_env_file(args.env_file, tokens)
        print("\nDone.")
        for k, v in tokens.items():
            print(f"  {k}: {v[:50]}...")
        return

    # --- Google Drive only ---
    if args.gdrive_only:
        if not args.force:
            existing = load_tokens_from_env(args.env_file)
            validity = check_tokens(gdrive_sapisid=existing["gdrive_sapisid"], gdrive_cookies=existing["gdrive_cookies"])
            if validity["gdrive"]:
                print("  GDRIVE: ok — nothing to do.")
                return
            print("  GDRIVE: expired or missing")
            print()
        tokens = get_gdrive_session()
        update_env_file(args.env_file, tokens)
        print("\nDone.")
        return

    # --- Grafana only ---
    if args.grafana_only:
        if not args.force:
            existing = load_tokens_from_env(args.env_file)
            validity = check_tokens(grafana_session=existing["grafana_session"])
            if validity["grafana_session"]:
                print("  GRAFANA_SESSION: ok — nothing to do.")
                return
            print("  GRAFANA_SESSION: expired or missing")
            print()
        tokens = get_grafana_session()
        update_env_file(args.env_file, tokens)
        print("\nDone.")
        for k, v in tokens.items():
            print(f"  {k}: {v[:50]}...")
        return

    # --- Default: refresh all (Grafana + Slack) ---
    if not args.force:
        existing = load_tokens_from_env(args.env_file)
        print("Checking existing tokens...")
        validity = check_tokens(
            grafana_session=existing["grafana_session"],
            slack_xoxc=existing["slack_xoxc"],
        )
        grafana_ok = validity["grafana_session"]
        slack_ok   = validity["slack_xoxc"]

        print(f"  GRAFANA_SESSION: {'ok' if grafana_ok else 'expired or missing'}")
        print(f"  SLACK_XOXC:      {'ok' if slack_ok else 'expired or missing'}")
        print()

        if grafana_ok and slack_ok:
            print("  All tokens valid — nothing to do.")
            return

    all_tokens = {}
    if not args.force:
        if not grafana_ok:
            all_tokens.update(get_grafana_session())
        if not slack_ok:
            all_tokens.update(get_slack_session())
    else:
        all_tokens.update(get_grafana_session())
        all_tokens.update(get_slack_session())

    update_env_file(args.env_file, all_tokens)
    print("\nDone.")
    for k, v in all_tokens.items():
        print(f"  {k}: {v[:50]}...")


if __name__ == "__main__":
    main()
