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

CHROME_APP = "Google Chrome"
CDP_PORT = 9236
PROFILE_DIR = Path.home() / ".browser_automation" / "google_ai_mode_cdp_profile"
AI_MODE_URL = "https://www.google.com/aimode"

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


def launch_chrome(
    port: int = CDP_PORT,
    profile_dir: Path = PROFILE_DIR,
    url: str = AI_MODE_URL,
    profile_directory: str | None = None,
) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    if profile_directory is None:
        profile_directory = resolve_profile_directory(profile_dir)
    # Only remove locks for this dedicated automation profile.
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try:
            (profile_dir / name).unlink()
        except FileNotFoundError:
            pass

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
            "--new-window",
            "--window-size=1400,900",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(60):
        time.sleep(0.25)
        if cdp_ready(port):
            return
    raise RuntimeError(f"Chrome CDP did not start on port {port}")


def ensure_chrome(
    port: int = CDP_PORT,
    profile_dir: Path = PROFILE_DIR,
    profile_directory: str | None = None,
) -> None:
    if not cdp_ready(port):
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


def extract_answer_lines(page) -> list[str]:
    text = page.locator("body").inner_text(timeout=10_000)
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


def _run_turns(playwright, port: int, query: str, followups: list[str], url: str) -> dict:
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    wait_for_ai_mode(page)

    turns = [{"query": query, "lines": extract_answer_lines(page), "url": page.url}]

    for followup in followups:
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
    def _open(playwright):
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=40_000)
        time.sleep(5)
        # Intentionally do NOT close the browser: keep it open for reuse.
        return page.locator("body").inner_text(timeout=8_000), page.url

    ensure_chrome(port)
    with sync_playwright() as playwright:
        try:
            body, final_url = _open(playwright)
        except Exception:
            # Stuck/unattachable session — reset only our Chrome and retry once.
            reset_chrome(port)
            body, final_url = _open(playwright)

    signed_out = "sign in" in body.lower()[:400]
    turns = []
    parts = body.split("You said:")
    for chunk in parts[1:]:
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        # First line is the user message; the rest is the assistant answer.
        turns.append({"user": lines[0], "assistant": lines[1:]})
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
        print(json.dumps(read_thread(args.url, port=args.port), indent=2))
        return

    if not args.query:
        parser.error("one of query, --url, or --setup is required")

    print(json.dumps(ask_google_ai_mode(args.query, args.followup, port=args.port), indent=2))


if __name__ == "__main__":
    main()
