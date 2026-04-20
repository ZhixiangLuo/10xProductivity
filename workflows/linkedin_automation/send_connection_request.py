#!/usr/bin/env python3
"""Send a LinkedIn connection request from a profile URL. DOM + bounded retries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_LINKEDIN_AUTO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(_LINKEDIN_AUTO))

from pacing.delays import pause_uniform  # noqa: E402
from post_comment import _dismiss_noise, _linkedin_page  # noqa: E402
from tool_connections.shared_utils.browser import sync_playwright  # noqa: E402

MAX_UI_ATTEMPTS = 4


def _goto_profile(page, url: str) -> None:
    page.goto(url.split("?", 1)[0], wait_until="domcontentloaded", timeout=45_000)
    pause_uniform(2.0, 3.2)
    _dismiss_noise(page)


def _click_connect(page) -> bool:
    """Primary Connect on profile hero; fallback More → Connect."""
    connect = page.get_by_role("button", name=re.compile(r"^connect$", re.I)).first
    try:
        if connect.is_visible(timeout=2000):
            connect.scroll_into_view_if_needed(timeout=8000)
            connect.click(timeout=8000)
            pause_uniform(0.6, 1.0)
            return True
    except Exception:
        pass
    try:
        more = page.get_by_role("button", name=re.compile(r"^more\b", re.I)).first
        if more.is_visible(timeout=2000):
            more.scroll_into_view_if_needed(timeout=8000)
            more.click(timeout=8000)
            pause_uniform(0.5, 0.85)
            inner = page.get_by_role("button", name=re.compile(r"^connect$", re.I)).first
            if inner.is_visible(timeout=2500):
                inner.click(timeout=8000)
                pause_uniform(0.6, 1.0)
                return True
    except Exception:
        pass
    return False


def _dismiss_invite_modal_optional(page) -> None:
    """If LinkedIn opens 'Add a note', prefer send without note when available."""
    for label in (
        "Send without a note",
        "Send",
    ):
        try:
            b = page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first
            if b.is_visible(timeout=2000):
                b.click(timeout=8000)
                pause_uniform(1.0, 1.6)
                return
        except Exception:
            continue


def send_connection_request(page, profile_url: str) -> dict:
    _goto_profile(page, profile_url)

    # Arm network listener before any click.
    # handlePostInteropConnection / relationshipbuilding RSC actions are the real
    # confirmation signals (sduiid from observer trace).
    _connect_responses: list[str] = []

    def _on_response(resp):
        try:
            url = resp.url or ""
            if (
                "handlePostInteropConnection" in url
                or "relationshipbuilding" in url
                or "relationships/invitations" in url
            ):
                _connect_responses.append(url)
        except Exception:
            pass

    page.on("response", _on_response)

    try:
        for attempt in range(1, MAX_UI_ATTEMPTS + 1):
            if _click_connect(page):
                _dismiss_invite_modal_optional(page)
                # Wait for network confirmation (up to ~5 s).
                for _ in range(10):
                    pause_uniform(0.4, 0.6)
                    if _connect_responses:
                        break
                network_confirmed = bool(_connect_responses)
                if not network_confirmed:
                    print(
                        "WARNING: connection network response not seen — invite may not have sent.",
                        flush=True,
                    )
                # Also check DOM for pending state as secondary signal.
                body = ""
                try:
                    body = (page.inner_text("body") or "").lower()
                except Exception:
                    pass
                note = "connect_clicked"
                if "withdraw" in body and "invitation" in body:
                    note = "invite_pending_ui_detected"
                elif "pending" in body:
                    note = "pending_mentioned"
                elif network_confirmed:
                    note = "network_confirmed"
                return {
                    "ok": True,
                    "attempt": attempt,
                    "network_confirmed": network_confirmed,
                    "note": note,
                }

            pause_uniform(0.5, 0.9)
            page.mouse.wheel(0, 300)
    finally:
        page.remove_listener("response", _on_response)

    return {
        "ok": False,
        "network_confirmed": False,
        "error": f"connect_not_found_after_{MAX_UI_ATTEMPTS}_attempts",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send connection request from a LinkedIn /in/… profile URL"
    )
    parser.add_argument("--profile-url", required=True, help="e.g. https://www.linkedin.com/in/someone/")
    parser.add_argument("--json", action="store_true", help="Print result JSON")
    args = parser.parse_args()

    with sync_playwright() as pw:
        ctx, page = _linkedin_page(pw)
        try:
            out = send_connection_request(page, args.profile_url)
            if args.json:
                print(json.dumps(out, ensure_ascii=False), flush=True)
            else:
                print(
                    f"ok={out.get('ok')} attempt={out.get('attempt')} "
                    f"network_confirmed={out.get('network_confirmed')} "
                    f"note={out.get('note')!r} error={out.get('error')!r}",
                    flush=True,
                )
            return 0 if out.get("ok") else 1
        finally:
            ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
