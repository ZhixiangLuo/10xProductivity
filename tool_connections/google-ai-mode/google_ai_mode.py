#!/usr/bin/env python3
"""
Google AI Mode through a dedicated real-Chrome CDP profile.

This is browser automation, not a stable Google API. It mirrors the Google Drive
CDP pattern: launch real Chrome with a dedicated profile, attach with Playwright,
submit the query, and extract the rendered AI Mode answer text.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

import sys

# The shared browser helpers live in the `tool_connections` namespace package,
# which only exists in the git_repos 10xProductivity checkout — not under
# ~/.10xProductivity, where this script is deployed. Add every candidate root
# that contains `tool_connections/shared_utils` to sys.path so the import
# resolves regardless of which tree this file is run from.
_CANDIDATE_ROOTS = [
    Path(__file__).resolve().parents[2],  # if ever run from inside the git_repos tree
    Path.home() / "git_repos" / "10xProductivity",  # deployed-copy fallback
]
for _root in _CANDIDATE_ROOTS:
    if (_root / "tool_connections" / "shared_utils" / "browser.py").is_file():
        sys.path.insert(0, str(_root))
        break

from tool_connections.shared_utils.browser import sync_playwright


def _load_runtime_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for env_path in (
        Path.home() / ".10xProductivity" / ".env",
        Path.home() / "git_repos" / "10xProductivity" / ".env",
    ):
        if env_path.is_file():
            load_dotenv(env_path, override=False)


_load_runtime_env()

CHROME_APP = "Google Chrome"
CDP_PORT = 9236
PROFILE_DIR = Path.home() / ".browser_automation" / "google_ai_mode_cdp_profile"
AI_MODE_URL = "https://www.google.com/aimode"
EXISTING_CHAT_TIMEOUT_MS = 25_000

# The signed-in Google account whose AI Mode history we want to use.
# Chrome stores each signed-in account as its own sub-profile inside PROFILE_DIR
# (e.g. "Default", "Profile 2"). We pin to the sub-profile for this account so
# automation never falls back to a different (e.g. managed/work) account.
# Set via the GOOGLE_AI_MODE_EMAIL env var (e.g. in your gitignored .env) — not
# hard-coded, so no personal address lives in this shared repo. When unset, the
# profile resolver falls back to DEFAULT_PROFILE_DIRECTORY.
SIGNED_IN_EMAIL = os.environ.get("GOOGLE_AI_MODE_EMAIL", "")
DEFAULT_PROFILE_DIRECTORY = "Default"


def resolve_profile_directory(profile_dir: Path = PROFILE_DIR, email: str = SIGNED_IN_EMAIL) -> str:
    """Return the Chrome sub-profile directory signed in as ``email``.

    Reads ``Local State`` -> profile.info_cache to map sub-profile dirs to
    account emails. Falls back to DEFAULT_PROFILE_DIRECTORY if not found.
    """
    if not email:
        return DEFAULT_PROFILE_DIRECTORY
    try:
        cache = json.loads((profile_dir / "Local State").read_text())
        info = cache.get("profile", {}).get("info_cache", {})
        for sub_dir, meta in info.items():
            if meta.get("user_name", "").lower() == email.lower():
                return sub_dir
    except Exception:
        pass
    return DEFAULT_PROFILE_DIRECTORY


def cdp_ready(port: int = CDP_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def profile_chrome_main_pids(
    profile_dir: Path = PROFILE_DIR,
    port: int = CDP_PORT,
) -> list[int]:
    """Return PIDs of main Chrome processes for this automation profile."""
    profile_str = str(profile_dir)
    result = subprocess.run(["pgrep", "-f", profile_str], capture_output=True, text=True)
    main_prefix = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
    pids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        ps = subprocess.run(
            ["ps", "-o", "args=", "-p", str(pid)],
            capture_output=True,
            text=True,
        )
        cmd = ps.stdout.strip()
        if not cmd.startswith(main_prefix):
            continue
        if profile_str not in cmd:
            continue
        if f"--remote-debugging-port={port}" not in cmd:
            continue
        pids.append(pid)
    return sorted(set(pids))


def cdp_owner_pid(port: int = CDP_PORT) -> int | None:
    """Return the PID listening on the CDP port, if any."""
    result = subprocess.run(
        ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.strip().splitlines():
        try:
            return int(line.strip())
        except ValueError:
            continue
    return None


def close_duplicate_profile_chrome(
    profile_dir: Path = PROFILE_DIR,
    port: int = CDP_PORT,
) -> int:
    """Kill extra Chrome main processes for this profile; keep the CDP listener."""
    pids = profile_chrome_main_pids(profile_dir, port)
    if len(pids) <= 1:
        return len(pids)

    keep = cdp_owner_pid(port)
    if keep is None:
        keep = pids[0]

    for pid in pids:
        if pid == keep:
            continue
        subprocess.run(["kill", str(pid)], check=False)

    time.sleep(1)
    return len(profile_chrome_main_pids(profile_dir, port))


def wait_for_cdp(port: int = CDP_PORT, attempts: int = 60) -> bool:
    for _ in range(attempts):
        if cdp_ready(port):
            return True
        time.sleep(0.25)
    return False


def launch_chrome(
    port: int = CDP_PORT,
    profile_dir: Path = PROFILE_DIR,
    url: str = AI_MODE_URL,
    profile_directory: str | None = None,
) -> None:
    """Launch Chrome only when no CDP session exists for this profile."""
    if cdp_ready(port):
        close_duplicate_profile_chrome(profile_dir, port)
        return

    existing = profile_chrome_main_pids(profile_dir, port)
    if existing:
        if wait_for_cdp(port):
            close_duplicate_profile_chrome(profile_dir, port)
            return
        raise RuntimeError(
            f"Chrome is already running for {profile_dir} but CDP port {port} "
            "is not ready. Close the extra AI Mode Chrome windows and retry."
        )

    profile_dir.mkdir(parents=True, exist_ok=True)
    if profile_directory is None:
        profile_directory = resolve_profile_directory(profile_dir)
    # Only remove locks for this dedicated automation profile.
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try:
            (profile_dir / name).unlink()
        except FileNotFoundError:
            pass

    # Fresh launch: `-na` is required on macOS for a separate user-data-dir when
    # the user's daily Chrome is already running. Never reach here if CDP or a
    # profile Chrome process is already up (see checks above).
    subprocess.Popen(
        [
            "open",
            "-na",
            CHROME_APP,
            "--args",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            f"--profile-directory={profile_directory}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1400,900",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    if not wait_for_cdp(port, attempts=80):
        raise RuntimeError(f"Chrome CDP did not start on port {port}")


def ensure_chrome(
    port: int = CDP_PORT,
    profile_dir: Path = PROFILE_DIR,
    profile_directory: str | None = None,
) -> None:
    if cdp_ready(port):
        close_duplicate_profile_chrome(profile_dir, port)
        return

    existing = profile_chrome_main_pids(profile_dir, port)
    if existing:
        if wait_for_cdp(port):
            close_duplicate_profile_chrome(profile_dir, port)
            return
        subprocess.run(["pkill", "-f", str(profile_dir)], check=False)
        time.sleep(2)

    launch_chrome(port=port, profile_dir=profile_dir, profile_directory=profile_directory)


def reset_chrome(
    port: int = CDP_PORT,
    profile_dir: Path = PROFILE_DIR,
    profile_directory: str | None = None,
) -> None:
    """Force a clean relaunch of the dedicated Chrome.

    Only kills Chrome processes for *this* automation profile (matched by the
    profile path), never the user's main browser or other CDP browsers. Used as
    a self-heal when an existing session is stuck and can't be attached to.
    Account pinning is preserved via launch_chrome's profile-directory resolution.
    """
    subprocess.run(["pkill", "-f", str(profile_dir)], check=False)
    time.sleep(2)
    launch_chrome(port=port, profile_dir=profile_dir, profile_directory=profile_directory)


def extract_answer_lines_from_text(text: str) -> list[str]:
    lines: list[str] = []
    skip_fragments = (
        "google apps",
        "settings",
        "privacy",
        "terms",
        "skip to main content",
        "accessibility help",
        "ai can make mistakes",
    )
    for line in text.splitlines():
        value = line.strip()
        if not value or len(value) < 18:
            continue
        lower = value.lower()
        if any(fragment in lower for fragment in skip_fragments):
            continue
        if value not in lines:
            lines.append(value)
    return lines


def extract_answer_lines(page) -> list[str]:
    return extract_answer_lines_from_text(page.locator("body").inner_text(timeout=10_000))


def wait_for_ai_mode(page, timeout_ms: int = 25_000) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        try:
            text = page.locator("body").inner_text(timeout=2_000)
            if "AI Mode response is ready" in text:
                return
        except Exception:
            pass
        time.sleep(1)


def _parse_existing_chat(text: str) -> list[dict]:
    turns: list[dict] = []
    for block in text.split("You said:")[1:]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        user = lines.pop(0)
        if lines and (
            lines[0].endswith("AM")
            or lines[0].endswith("PM")
            or lines[0].endswith("a.m.")
            or lines[0].endswith("p.m.")
        ):
            lines.pop(0)
        turns.append({"user": user, "assistant": lines})
    return turns


def _evaluate_webview(browser, target_id: str, expression: str) -> str:
    session = browser.new_browser_cdp_session()
    session_id = session.send(
        "Target.attachToTarget", {"targetId": target_id, "flatten": False}
    )["sessionId"]
    responses: list[dict] = []
    session.on("Target.receivedMessageFromTarget", lambda event: responses.append(event))
    session.send(
        "Target.sendMessageToTarget",
        {
            "sessionId": session_id,
            "message": json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            ),
        },
    )

    deadline = time.time() + 5
    while time.time() < deadline:
        # A CDP command pumps pending Target events in Playwright's sync API.
        session.send("Target.getTargets")
        for response in responses:
            message = json.loads(response["message"])
            if message.get("id") == 1:
                return message["result"]["result"].get("value", "")
        time.sleep(0.1)
    raise RuntimeError("Timed out reading the Google AI Mode webview")


def _recover_query_webview(browser, query: str, timeout_ms: int = EXISTING_CHAT_TIMEOUT_MS) -> dict:
    """Recover a new query that Chrome routed into an embedded contextual-task webview."""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        session = browser.new_browser_cdp_session()
        targets = session.send("Target.getTargets")["targetInfos"]
        for target in targets:
            if target.get("type") != "webview":
                continue
            url = target.get("url", "")
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            if params.get("udm") != ["50"] or params.get("q") != [query]:
                continue
            text = _evaluate_webview(browser, target["targetId"], "document.body.innerText")
            if "AI Mode response is ready" not in text:
                continue
            turns = _parse_existing_chat(text)
            answer = turns[-1]["assistant"] if turns else extract_answer_lines_from_text(text)
            return {"query": query, "lines": answer, "url": url}
        time.sleep(0.5)
    raise RuntimeError("Could not recover the new Google AI Mode query from its webview")


def _run_turns(playwright, port: int, query: str, followups: list[str], url: str) -> dict:
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    recovered_webview = False
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        wait_for_ai_mode(page)
        turns = [{"query": query, "lines": extract_answer_lines(page), "url": page.url}]
    except Exception:
        turns = [_recover_query_webview(browser, query)]
        recovered_webview = True

    for followup in followups:
        if recovered_webview:
            raise RuntimeError(
                "Google routed this query into a contextual-task webview. "
                "Initial-query recovery succeeded, but follow-ups are not supported "
                "through that webview until a live run verifies the submission path."
            )
        textbox = page.locator("textarea").last
        textbox.click(timeout=5_000)
        page.keyboard.press("Meta+A")
        page.keyboard.type(followup, delay=10)
        page.keyboard.press("Enter")
        wait_for_ai_mode(page)
        turns.append({"query": followup, "lines": extract_answer_lines(page), "url": page.url})

    # Intentionally do NOT close the browser: keep the dedicated Chrome open so
    # the next query reuses this session instead of relaunching from scratch.
    return {"turns": turns}


def ask_google_ai_mode(query: str, followups: list[str] | None = None, port: int = CDP_PORT) -> dict:
    followups = followups or []
    url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": query, "udm": "50"})

    # Reuse an already-open dedicated Chrome if present; only launch if none.
    ensure_chrome(port)

    with sync_playwright() as playwright:
        try:
            return _run_turns(playwright, port, query, followups, url)
        except Exception:
            # The existing session is stuck or unattachable — self-heal by
            # resetting only our dedicated Chrome, then retry once.
            reset_chrome(port)
            return _run_turns(playwright, port, query, followups, url)


def read_thread(url: str, port: int = CDP_PORT) -> dict:
    """Open a saved AI Mode thread URL and extract its conversation turns.

    A thread URL is the full ``/search?udm=50...&mtid=...&mstk=...`` link that
    Google AI Mode shows for a saved conversation. The ``mtid``/``mstk`` params
    only resolve when the dedicated profile is signed in as the SAME account
    that created the thread (see SIGNED_IN_EMAIL). The rendered transcript marks
    each user message with a "You said:" line; everything between two such
    markers is the assistant's answer for that turn.
    """
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if params.get("udm") != ["50"] or not params.get("mtid"):
        raise ValueError("Saved AI Mode thread URL must contain udm=50 and mtid")
    mtid = params["mtid"][0]

    def _open(playwright):
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0]
        page = context.new_page()
        try:
            page.goto(url, wait_until="commit", timeout=40_000)
        except Exception:
            # Chrome may route saved AI Mode chats through chrome://contextual-tasks.
            pass

        deadline = time.time() + (EXISTING_CHAT_TIMEOUT_MS / 1000)
        body = ""
        final_url = url
        while time.time() < deadline:
            session = browser.new_browser_cdp_session()
            targets = session.send("Target.getTargets")["targetInfos"]
            target = next(
                (
                    item
                    for item in targets
                    if item.get("type") == "webview" and mtid in item.get("url", "")
                ),
                None,
            )
            if target:
                final_url = target["url"]
                body = _evaluate_webview(browser, target["targetId"], "document.body.innerText")
                if "You said:" in body:
                    break
            elif page.url.startswith("http"):
                body = page.locator("body").inner_text(timeout=5_000)
                final_url = page.url
                if "You said:" in body:
                    break
            time.sleep(0.5)
        # Intentionally do NOT close the browser: keep it open for reuse.
        page.close()
        return body, final_url

    ensure_chrome(port)
    with sync_playwright() as playwright:
        try:
            body, final_url = _open(playwright)
        except Exception:
            # Stuck/unattachable session — reset only our Chrome and retry once.
            reset_chrome(port)
            body, final_url = _open(playwright)

    signed_out = "sign in" in body.lower()[:400]
    if "You said:" not in body:
        raise RuntimeError(
            "Existing AI Mode chat recovery failed. "
            "The signed-in account may not match the saved chat, or the session may be expired."
        )
    turns = _parse_existing_chat(body)
    return {"url": final_url, "signed_out": signed_out, "turns": turns}


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Google AI Mode through a signed-in Chrome CDP profile.")
    parser.add_argument("query", nargs="?", help="Initial AI Mode query")
    parser.add_argument("--followup", action="append", default=[], help="Follow-up query; repeat for multi-turn")
    parser.add_argument("--url", help="Read a saved AI Mode thread URL (history) instead of asking a new query")
    parser.add_argument("--setup", action="store_true", help="Open Google AI Mode for manual Google sign-in")
    parser.add_argument("--port", type=int, default=CDP_PORT)
    args = parser.parse_args()

    if args.setup:
        launch_chrome(port=args.port)
        print(f"Opened Google AI Mode in {PROFILE_DIR} (account: {SIGNED_IN_EMAIL})")
        print("Sign in manually, then rerun this script without --setup.")
        return

    if args.url:
        if args.query or args.followup:
            parser.error("--url cannot be combined with a query or --followup")
        print(json.dumps(read_thread(args.url, port=args.port), indent=2))
        return

    if not args.query:
        parser.error("one of query, --url, or --setup is required")

    print(json.dumps(ask_google_ai_mode(args.query, args.followup, port=args.port), indent=2))


if __name__ == "__main__":
    main()
