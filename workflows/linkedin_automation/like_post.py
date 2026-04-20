#!/usr/bin/env python3
"""Like a LinkedIn post (permalink). DOM + persistent profile; bounded UI retries."""

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
from post_comment import (  # noqa: E402
    _dismiss_noise,
    _goto_post_ready,
    _linkedin_page,
)
from tool_connections.shared_utils.browser import sync_playwright  # noqa: E402

# Bounded retries for flaky LinkedIn UI (scroll, visibility, click).
MAX_UI_ATTEMPTS = 4


def _like_locator_candidates(page):
    """Ordered list of (description, locator) for the post-level Like control."""
    return (
        ("react-button--like", page.locator("button.react-button--like").first),
        ("data-testid like", page.locator('[data-testid="social-actions__reaction-like"]').first),
        (
            "aria-label Like reaction",
            page.locator('button[aria-label*="Like"][aria-label*="Reaction"]').first,
        ),
        (
            "role button Like",
            page.get_by_role("button", name=re.compile(r"^like\b", re.I)).first,
        ),
    )


def _already_liked(loc) -> bool:
    try:
        aria = loc.get_attribute("aria-pressed") or ""
        if aria.lower() == "true":
            return True
    except Exception:
        pass
    try:
        cls = loc.get_attribute("class") or ""
        if "react-button--active" in cls or "react-button--pressed" in cls:
            return True
    except Exception:
        pass
    return False


def like_post(page, url: str) -> dict:
    """Return {ok, already_liked, network_confirmed, error}."""
    _goto_post_ready(page, url)
    pause_uniform(0.8, 1.4)
    _dismiss_noise(page)

    # Arm network listener before any click — reactions.create is the real confirmation signal.
    _reaction_responses: list[str] = []

    def _on_response(resp):
        try:
            if "reactions.create" in (resp.url or "") or "reactions/create" in (resp.url or ""):
                _reaction_responses.append(resp.url)
        except Exception:
            pass

    page.on("response", _on_response)

    try:
        for attempt in range(1, MAX_UI_ATTEMPTS + 1):
            for name, loc in _like_locator_candidates(page):
                try:
                    if not loc.is_visible(timeout=1500):
                        continue
                    if _already_liked(loc):
                        return {
                            "ok": True,
                            "already_liked": True,
                            "network_confirmed": None,
                            "selector": name,
                            "attempt": attempt,
                        }
                    loc.scroll_into_view_if_needed(timeout=8000)
                    pause_uniform(0.35, 0.65)
                    loc.click(timeout=8000)
                    # Wait for network confirmation (reactions.create RSC response).
                    for _ in range(10):
                        pause_uniform(0.35, 0.5)
                        if _reaction_responses:
                            break
                    network_confirmed = bool(_reaction_responses)
                    if not network_confirmed:
                        print(
                            "WARNING: reactions.create network response not seen — Like may not have registered.",
                            flush=True,
                        )
                    if _already_liked(loc) or network_confirmed:
                        return {
                            "ok": True,
                            "already_liked": False,
                            "network_confirmed": network_confirmed,
                            "selector": name,
                            "attempt": attempt,
                        }
                    # DOM not yet updated — one short re-check
                    pause_uniform(0.6, 1.0)
                    if _already_liked(loc):
                        return {
                            "ok": True,
                            "already_liked": False,
                            "network_confirmed": network_confirmed,
                            "selector": name,
                            "attempt": attempt,
                        }
                except Exception:
                    continue
            # Nudge layout then retry (bounded)
            page.mouse.wheel(0, 400)
            pause_uniform(0.4, 0.7)
            page.keyboard.press("Home")
            pause_uniform(0.35, 0.55)
    finally:
        page.remove_listener("response", _on_response)

    return {
        "ok": False,
        "already_liked": False,
        "network_confirmed": False,
        "error": f"no_like_control_after_{MAX_UI_ATTEMPTS}_attempts",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Like a LinkedIn post (persistent browser session)")
    parser.add_argument("--url", required=True, help="Post permalink, e.g. …/feed/update/urn:li:activity:…/")
    parser.add_argument("--json", action="store_true", help="Print result as JSON on stdout")
    args = parser.parse_args()

    with sync_playwright() as pw:
        ctx, page = _linkedin_page(pw)
        try:
            out = like_post(page, args.url)
            if args.json:
                print(json.dumps(out, ensure_ascii=False), flush=True)
            else:
                print(
                    f"ok={out.get('ok')} already_liked={out.get('already_liked')} "
                    f"network_confirmed={out.get('network_confirmed')} "
                    f"selector={out.get('selector')!r} attempt={out.get('attempt')} "
                    f"error={out.get('error')!r}",
                    flush=True,
                )
            return 0 if out.get("ok") else 1
        finally:
            ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
