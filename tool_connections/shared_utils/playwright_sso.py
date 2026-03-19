#!/usr/bin/env python3
"""
SSO session refresher via Playwright.

Opens a headed Chromium window, completes SSO login (auto-completes on managed
machines via enterprise SSO extensions), and captures session tokens/cookies for:

  - Grafana session cookie (~8h TTL)          → GRAFANA_SESSION in .env
  - Slack session token (~8h TTL)             → SLACK_XOXC + SLACK_D_COOKIE in .env
  - Google Drive session (days/weeks)         → ~/.browser_automation/gdrive_auth.json
  - Microsoft Teams (personal) session (~24h TTL)   → TEAMS_SKYPETOKEN + TEAMS_SESSION_ID in .env
  - Outlook / Microsoft 365 work (~1h TTL)    → GRAPH_ACCESS_TOKEN + OWA_ACCESS_TOKEN in .env

By default, existing tokens are validated first — the browser only opens if one
or more have expired. Use --force to always refresh.

Usage (CLI):
    python3 playwright_sso.py [--env-file PATH] [--force]
    python3 playwright_sso.py --slack-only    # refresh only Slack credentials
    python3 playwright_sso.py --gdrive-only   # refresh only Google Drive session
    python3 playwright_sso.py --grafana-only  # refresh only Grafana session
    python3 playwright_sso.py --teams-only    # refresh only Microsoft Teams (personal) session
    python3 playwright_sso.py --outlook-only  # refresh only Outlook / Microsoft 365 tokens

Usage (library):
    from playwright_sso import check_tokens, get_grafana_session, get_slack_session, get_teams_session, get_outlook_session
    status = check_tokens(grafana_session=..., slack_xoxc=...)
    tokens = get_grafana_session()    # {"grafana_session": "..."}
    tokens = get_slack_session()      # {"slack_xoxc": "...", "slack_d_cookie": "..."}
    tokens = get_teams_session()      # {"teams_skypetoken": "...", "teams_session_id": "..."}
    tokens = get_outlook_session()    # {"graph_access_token": "...", "owa_access_token": "..."}

Configuration:
    Set these in your .env file (see the relevant tool's setup.md under `.env` entries):
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
TEAMS_URL           = "https://teams.live.com/v2/"
GDRIVE_URL          = "https://drive.google.com/drive/my-drive"
OUTLOOK_URL         = "https://outlook.office.com/mail/"
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
    teams_skypetoken: str | None = None,
    graph_access_token: str | None = None,
    owa_access_token: str | None = None,
) -> dict[str, bool]:
    """
    Validate existing tokens with lightweight API calls (no browser).
    Returns validity flags: {"grafana_session": bool, "slack_xoxc": bool, "gdrive": bool,
                             "teams": bool, "outlook_graph": bool, "outlook_owa": bool}
    """
    result = {
        "grafana_session": False,
        "slack_xoxc": False,
        "gdrive": False,
        "teams": False,
        "outlook_graph": False,
        "outlook_owa": False,
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

    if teams_skypetoken and not teams_skypetoken.startswith("your-"):
        status = _http_get(
            "https://teams.live.com/api/csa/api/v1/teams/users/me",
            {"x-skypetoken": teams_skypetoken},
        )
        result["teams"] = status == 200

    if graph_access_token and not graph_access_token.startswith("your-"):
        status = _http_get(
            "https://graph.microsoft.com/v1.0/me",
            {"Authorization": f"Bearer {graph_access_token}"},
        )
        result["outlook_graph"] = status == 200

    if owa_access_token and not owa_access_token.startswith("your-"):
        status = _http_get(
            "https://outlook.office.com/api/v2.0/me/MailFolders/Inbox?$select=DisplayName",
            {"Authorization": f"Bearer {owa_access_token}"},
        )
        result["outlook_owa"] = status == 200

    return result


def load_tokens_from_env(env_path: Path) -> dict[str, str | None]:
    """Read session tokens/cookies from a .env file."""
    tokens: dict[str, str | None] = {
        "grafana_session": None,
        "slack_xoxc": None,
        "slack_d_cookie": None,
        "gdrive_cookies": None,
        "gdrive_sapisid": None,
        "teams_skypetoken": None,
        "teams_session_id": None,
        "graph_access_token": None,
        "owa_access_token": None,
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
        elif line.startswith("TEAMS_SKYPETOKEN="):
            tokens["teams_skypetoken"] = line.split("=", 1)[1].strip()
        elif line.startswith("TEAMS_SESSION_ID="):
            tokens["teams_session_id"] = line.split("=", 1)[1].strip()
        elif line.startswith("GRAPH_ACCESS_TOKEN="):
            tokens["graph_access_token"] = line.split("=", 1)[1].strip()
        elif line.startswith("OWA_ACCESS_TOKEN="):
            tokens["owa_access_token"] = line.split("=", 1)[1].strip()
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
# Microsoft Teams (personal) session (teams.live.com)
# ---------------------------------------------------------------------------

def _extract_teams_session(page, ctx) -> tuple[str, str]:
    """
    Navigate to Teams (personal), complete Microsoft account login, and extract
    the skypetoken (from localStorage/network request headers) + x-ms-session-id.

    Teams (personal) uses a private API at teams.live.com/api/ authenticated via
    x-skypetoken (not a standard Bearer token). Both tokens are short-lived (~24h).
    """
    page.goto(TEAMS_URL, wait_until="commit", timeout=30_000)
    print("    Waiting for Teams login to complete (up to 3 min)...", flush=True)

    skypetoken = None
    session_id = None
    deadline = time.time() + 180

    captured_headers: list[dict] = []

    def _on_request(req):
        hdrs = req.headers
        if "x-skypetoken" in hdrs:
            captured_headers.append(hdrs)

    page.on("request", _on_request)

    while time.time() < deadline:
        time.sleep(2)

        # Try extracting from captured network headers first
        for hdrs in captured_headers:
            t = hdrs.get("x-skypetoken", "")
            s = hdrs.get("x-ms-session-id", "")
            if t and not t.startswith("your-"):
                skypetoken = t
                session_id = s or session_id
                break

        if skypetoken:
            break

        # Fallback: check localStorage for skypetoken
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

    if not skypetoken:
        raise RuntimeError("No x-skypetoken captured — login may not have completed within 3 minutes.")

    if not session_id:
        # Generate a UUID as session ID if not captured from headers
        import uuid
        session_id = str(uuid.uuid4())
        print("    x-ms-session-id not captured from headers — generated a new UUID.")

    return skypetoken, session_id


def get_teams_session() -> dict[str, str]:
    """
    Open Microsoft Teams (personal) (teams.live.com) in a headed browser, complete
    Microsoft account login, and return {"teams_skypetoken": "...", "teams_session_id": "..."}.

    On managed machines with Azure AD SSO, this completes automatically.
    On personal machines, complete Microsoft login once through the browser.
    Token lifetime: ~24h.
    """
    print(f"  [1/1] Getting Microsoft Teams session (navigating to {TEAMS_URL})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        skypetoken, session_id = _extract_teams_session(page, ctx)
        browser.close()
    print(f"    Teams skypetoken captured ({len(skypetoken)} chars)")
    return {"teams_skypetoken": skypetoken, "teams_session_id": session_id}


# ---------------------------------------------------------------------------
# Outlook / Microsoft 365 work account session
# ---------------------------------------------------------------------------

def _extract_outlook_session(page, ctx) -> tuple[str, str]:
    """
    Navigate to Outlook web (outlook.office.com), complete Azure AD SSO, and
    capture two Bearer tokens from network request headers:

      - graph_token: from the first graph.microsoft.com request (user photo)
      - owa_token:   from outlook.office.com/owa/startupdata.ashx (app startup)

    On managed machines with macOS Enterprise SSO (Microsoft Intune / Company Portal),
    Azure AD login auto-completes in ~30s. On unmanaged machines, the user completes
    login once through the browser (~60s).

    Token lifetime: ~1h. Both tokens expire together (same Azure AD session).
    """
    def _is_jwt(t: str) -> bool:
        return isinstance(t, str) and t.count(".") in (2, 4) and len(t) > 100

    captured: dict[str, str] = {}

    def _on_request(req):
        auth = req.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return
        t = auth[7:]
        if not _is_jwt(t):
            return
        if "graph.microsoft.com" in req.url and "graph" not in captured:
            captured["graph"] = t
        elif "outlook.office.com" in req.url and "owa" not in captured:
            captured["owa"] = t

    page.on("request", _on_request)
    page.goto(OUTLOOK_URL, wait_until="commit", timeout=30_000)
    print("    Waiting for Outlook login to complete (up to 3 min)...", flush=True)

    deadline = time.time() + 180
    while time.time() < deadline:
        if "graph" in captured and "owa" in captured:
            break
        time.sleep(1)

    if not captured:
        raise RuntimeError("No Outlook tokens captured — login may not have completed within 3 minutes.")

    graph_token = captured.get("graph", "")
    owa_token   = captured.get("owa", "")

    if not graph_token:
        raise RuntimeError("Graph token not captured — Outlook page may not have loaded.")
    if not owa_token:
        # OWA token fires slightly later; log what we got but don't fail
        print("    Warning: OWA token not captured — only Graph token available.")

    return graph_token, owa_token


def get_outlook_session() -> dict[str, str]:
    """
    Open Outlook web (outlook.office.com) in a headed browser, complete Azure AD SSO,
    and return {"graph_access_token": "...", "owa_access_token": "..."}.

    - graph_access_token: for graph.microsoft.com endpoints (user profile, people)
    - owa_access_token:   for outlook.office.com/api/v2.0 endpoints (mail, calendar, contacts)

    On managed machines with macOS Enterprise SSO, this completes automatically (~30s).
    On personal/unmanaged machines, complete Microsoft 365 login once through the browser.
    Token lifetime: ~1h.
    """
    print(f"  [1/1] Getting Outlook/M365 session (navigating to {OUTLOOK_URL})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        graph_token, owa_token = _extract_outlook_session(page, ctx)
        browser.close()

    print(f"    Graph token captured ({len(graph_token)} chars)")
    if owa_token:
        print(f"    OWA token captured ({len(owa_token)} chars)")
    return {"graph_access_token": graph_token, "owa_access_token": owa_token}


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
    if "teams_skypetoken" in tokens:
        content = _upsert(content, "TEAMS_SKYPETOKEN", tokens["teams_skypetoken"], "# --- Microsoft Teams (personal)")
    if "teams_session_id" in tokens:
        content = _upsert(content, "TEAMS_SESSION_ID", tokens["teams_session_id"], "# --- Microsoft Teams (personal)")
    if "graph_access_token" in tokens and tokens["graph_access_token"]:
        content = _upsert(content, "GRAPH_ACCESS_TOKEN", tokens["graph_access_token"], "# --- Outlook / Microsoft 365")
    if "owa_access_token" in tokens and tokens["owa_access_token"]:
        content = _upsert(content, "OWA_ACCESS_TOKEN", tokens["owa_access_token"], "# --- Outlook / Microsoft 365")

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
    parser.add_argument("--teams-only", action="store_true", help="Refresh Microsoft Teams (personal) session only")
    parser.add_argument("--outlook-only", action="store_true", help="Refresh Outlook / Microsoft 365 tokens only")
    args = parser.parse_args()

    print("SSO token refresher (Playwright)")
    print(f"  .env: {args.env_file}")
    print()

    # Check that required base URLs are configured before opening any browser
    issues = []
    if not args.slack_only and not args.gdrive_only and not args.teams_only and not args.outlook_only:
        if "yourcompany" in GRAFANA_BASE_URL or GRAFANA_BASE_URL == "https://grafana.yourcompany.com":
            issues.append(f"  GRAFANA_BASE_URL is not set (currently: {GRAFANA_BASE_URL})\n"
                          f"  → Add GRAFANA_BASE_URL=https://grafana.yourcompany.com to .env first")
    if not args.grafana_only and not args.gdrive_only and not args.teams_only and not args.outlook_only:
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

    # --- Teams only ---
    if args.teams_only:
        if not args.force:
            existing = load_tokens_from_env(args.env_file)
            validity = check_tokens(teams_skypetoken=existing["teams_skypetoken"])
            if validity["teams"]:
                print("  TEAMS_SKYPETOKEN: ok — nothing to do.")
                return
            print("  TEAMS_SKYPETOKEN: expired or missing")
            print()
        tokens = get_teams_session()
        update_env_file(args.env_file, tokens)
        print("\nDone.")
        for k, v in tokens.items():
            print(f"  {k}: {v[:50]}...")
        return

    # --- Outlook only ---
    if args.outlook_only:
        if not args.force:
            existing = load_tokens_from_env(args.env_file)
            validity = check_tokens(
                graph_access_token=existing["graph_access_token"],
                owa_access_token=existing["owa_access_token"],
            )
            if validity["outlook_graph"] and validity["outlook_owa"]:
                print("  GRAPH_ACCESS_TOKEN: ok\n  OWA_ACCESS_TOKEN: ok — nothing to do.")
                return
            print(f"  GRAPH_ACCESS_TOKEN: {'ok' if validity['outlook_graph'] else 'expired or missing'}")
            print(f"  OWA_ACCESS_TOKEN:   {'ok' if validity['outlook_owa'] else 'expired or missing'}")
            print()
        tokens = get_outlook_session()
        update_env_file(args.env_file, tokens)
        print("\nDone.")
        for k, v in tokens.items():
            if v:
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
