#!/usr/bin/env python3
"""Post a comment on a LinkedIn /feed/update/ URL using the same session as search_posts.

Uses ``pacing.delays.pause_uniform`` and ``pacing.typing_human``: focuses the **top**
comment composer, then **human** typing or **Quill ``fill``** on the editor locator
(not raw ``page.keyboard`` paste, which misses focus).

Also: ``--probe-comments`` detects posts that disallow comments, and
``--verify-substring`` checks whether text appears in the thread after posting.

Flow (aligned with observer trace — sduiid: fetchFeedUpdateActionPrompt → createComment):
  1. goto permalink
  2. reveal_comments_thread (expands thread so composer shell paints before we look for it)
  3. detect locked
  4. prepare editor (scroll into view, activate chrome, click Quill)
  5. type / paste
  6. click Post (scoped inside composer to avoid page-wide artdeco false-positive)
  7. network confirm: wait for createComment RSC-action response, then DOM text verify
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_LINKEDIN_AUTO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(_LINKEDIN_AUTO))

from pacing.delays import pause_uniform  # noqa: E402
from pacing.typing_human import (  # noqa: E402
    comment_input_mode,
    human_type_rich_editor,
    paste_like_editor,
)
from tool_connections.shared_utils.browser import DEFAULT_ENV_FILE, load_env_file, sync_playwright  # noqa: E402

PROFILE_DIR = Path.home() / ".browser_automation" / "linkedin_profile"

# Substrings in visible post / comments chrome (lowercase) → blocked or restricted.
_COMMENTS_LOCKED_SIGNALS: tuple[tuple[str, str], ...] = (
    ("comments are turned off", "comments_turned_off"),
    ("comments have been turned off", "comments_turned_off"),
    ("commenting has been turned off", "comments_turned_off"),
    ("turned off comments", "comments_turned_off"),
    ("comments on this post are limited", "comments_limited"),
    ("commenting is limited", "comments_limited"),
    ("only group members can comment", "group_members_only"),
    ("can't comment on this post", "cannot_comment"),
    ("cannot comment on this post", "cannot_comment"),
    ("restricted from commenting", "restricted"),
    ("sign in to join the conversation", "login_required"),
)


def _linkedin_page(pw):
    load_env_file(DEFAULT_ENV_FILE)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ctx = pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,
        args=["--window-size=1280,900", "--window-position=100,50"],
        ignore_https_errors=True,
    )
    try:
        Stealth = importlib.import_module("playwright_stealth").Stealth
        Stealth().apply_stealth_sync(ctx)
    except ImportError:
        pass
    return ctx, ctx.new_page()


def _dismiss_noise(page) -> None:
    for _ in range(2):
        page.keyboard.press("Escape")
        pause_uniform(0.1, 0.14)


def _body_text_lower(page) -> str:
    try:
        return (page.inner_text("body") or "").lower()
    except Exception:
        return ""


def detect_comments_locked(body_lower: str) -> tuple[bool, str | None]:
    """Return (is_locked, reason_code) using visible page copy."""
    for phrase, code in _COMMENTS_LOCKED_SIGNALS:
        if phrase in body_lower:
            return True, code
    return False, None


def _find_comment_editor(page):
    for sel in (
        '[aria-label="Text editor for commenting"]',
        '[aria-label="Add a comment…"]',
        "div.comments-comment-texteditor div.ql-editor",
        ".comments-comment-box--cr div.ql-editor",
    ):
        loc = page.locator(sel).first
        try:
            if loc.is_visible(timeout=800):
                return loc
        except Exception:
            continue
    try:
        loc = page.get_by_role("textbox", name="Text editor for commenting").first
        if loc.is_visible(timeout=800):
            return loc
    except Exception:
        pass
    return None


def reveal_comments_thread(page) -> None:
    """Expand the comments thread and wait for LinkedIn to paint the composer.

    Observer trace shows fetchFeedUpdateActionPrompt fires when the thread opens —
    that is the real signal that the composer shell is ready. We nudge once, wait
    for that response (up to ~5 s), then stop. No more blind 8x800px scroll loop.
    """
    # Arm listener before any nudge.
    _thread_responses: list[str] = []

    def _on_thread_response(resp):
        try:
            url = resp.url or ""
            if "fetchFeedUpdateActionPrompt" in url or "fetchComment" in url:
                _thread_responses.append(url)
        except Exception:
            pass

    page.on("response", _on_thread_response)
    try:
        # Try explicit "Comments" / "Load more" buttons first.
        for name in ("Load more comments", "View comments", "Comments"):
            try:
                page.get_by_role("button", name=re.compile(name, re.I)).first.click(timeout=1200)
                pause_uniform(0.4, 0.7)
            except Exception:
                pass
        # One scroll nudge to trigger lazy hydration.
        page.mouse.wheel(0, 600)
        pause_uniform(0.3, 0.5)
        # Wait for network signal (up to ~5 s in 500ms steps).
        for _ in range(10):
            if _thread_responses:
                break
            page.wait_for_timeout(500)
        if not _thread_responses:
            # Fallback: one more scroll if network signal never arrived.
            page.mouse.wheel(0, 600)
            pause_uniform(0.5, 0.9)
    finally:
        page.remove_listener("response", _on_thread_response)
    pause_uniform(0.5, 0.9)


def probe_exit_code(info: dict) -> int:
    """Map ``probe_comment_access`` result to CLI exit codes (0 open, 2 locked, 3 unknown)."""
    if info.get("comments_locked"):
        return 2
    if info.get("status") == "open":
        return 0
    return 3


def probe_comment_access(page, url: str) -> dict:
    """Load a post permalink and report whether commenting looks allowed."""
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    pause_uniform(2.2, 3.5)
    _dismiss_noise(page)
    reveal_comments_thread(page)
    body = _body_text_lower(page)
    locked, reason = detect_comments_locked(body)
    editor = _find_comment_editor(page)
    editor_visible = editor is not None
    if locked:
        status = "disabled"
    elif editor_visible:
        status = "open"
    else:
        status = "unknown"
    return {
        "url": url,
        "status": status,
        "comments_locked": locked,
        "lock_reason": reason,
        "editor_visible": editor_visible,
    }


def _goto_post_ready(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    pause_uniform(2.2, 3.8)
    _dismiss_noise(page)


def _nudge_main_composer_visible(page) -> None:
    """Scroll the top-level comment form into view — avoid long blind wheel loops."""
    try:
        page.locator("form.comments-comment-box__form").first.scroll_into_view_if_needed(timeout=12_000)
        pause_uniform(0.35, 0.65)
        return
    except Exception:
        pass
    try:
        page.locator(".comments-comment-box--cr").first.scroll_into_view_if_needed(timeout=8000)
    except Exception:
        for _ in range(2):
            page.keyboard.press("End")
            pause_uniform(0.35, 0.55)


def _top_comment_composer(page):
    """Main post composer (not inline reply boxes deeper in the thread)."""
    form = page.locator("form.comments-comment-box__form").first
    try:
        form.wait_for(state="attached", timeout=15_000)
        return form
    except Exception:
        pass
    cr = page.locator(".comments-comment-box--cr").first
    cr.wait_for(state="attached", timeout=12_000)
    return cr


def _prepare_top_comment_editor(page):
    """Scroll composer into view, click to activate, return ``(editor, composer)`` locators."""
    composer = _top_comment_composer(page)
    composer.scroll_into_view_if_needed(timeout=12_000)
    pause_uniform(0.45, 0.85)
    print("Scrolled main comment composer into view.", flush=True)

    for loc in (
        composer.locator('[aria-label="Add a comment…"]'),
        composer.locator('[aria-label="Add a comment..."]'),
    ):
        try:
            el = loc.first
            if el.is_visible(timeout=800):
                el.click(timeout=5000)
                print('Clicked "Add a comment" chrome to activate composer.', flush=True)
                pause_uniform(0.35, 0.7)
                break
        except Exception:
            continue

    editor = composer.locator("div.ql-editor").first
    editor.wait_for(state="visible", timeout=15_000)
    editor.scroll_into_view_if_needed(timeout=10_000)
    editor.click(timeout=5000)
    print("Clicked top-level Quill comment editor (focus for typing).", flush=True)
    pause_uniform(0.4, 0.75)
    return editor, composer


def _comments_thread_text_lower(page) -> str:
    """Prefer comment list + composer text (reduces false verify hits from side rails)."""
    parts: list[str] = []
    for sel in (
        "form.comments-comment-box__form",
        ".comments-comments-list",
        ".comments-comment-list",
        "ul.comments-thread-entity",
    ):
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1200):
                parts.append(loc.inner_text() or "")
        except Exception:
            continue
    if parts:
        return "\n".join(parts).lower()
    return _body_text_lower(page)


def _thread_text_contains(page, substring: str) -> bool:
    """Check thread text without re-scrolling (thread already expanded)."""
    return substring.lower() in _comments_thread_text_lower(page)


def page_contains_in_thread(page, substring: str) -> bool:
    """Expand thread then check. For standalone verify; posting path uses _thread_text_contains."""
    reveal_comments_thread(page)
    return _thread_text_contains(page, substring)


def submit_comment_on_page(
    page,
    url: str,
    text: str,
    *,
    human_only: bool = False,
    paste_only: bool = False,
    verify_substring: str | None = None,
) -> int:
    """Post a comment using an existing ``page`` (same session as probe). Returns CLI-style exit code."""
    _goto_post_ready(page, url)

    reveal_comments_thread(page)

    pre = _body_text_lower(page)
    locked, lock_reason = detect_comments_locked(pre)
    if locked:
        print(
            f"ERROR: Comments look disabled on this post ({lock_reason}). Not posting.",
            file=sys.stderr,
        )
        return 2

    try:
        editor, composer = _prepare_top_comment_editor(page)
    except Exception as e:
        print(f"ERROR: Could not focus top-level comment composer: {e}", file=sys.stderr)
        return 1

    if human_only:
        mode = "human"
    elif paste_only:
        mode = "paste"
    else:
        mode = comment_input_mode(text)
    if mode == "human":
        human_type_rich_editor(editor, text)
    else:
        paste_like_editor(editor, text)
    print(f"Comment body input mode: {mode} (bound to composer editor)", flush=True)
    pause_uniform(1.0, 2.0)

    _create_comment_responses: list[str] = []

    def _on_response(resp):
        try:
            if "createComment" in (resp.url or ""):
                _create_comment_responses.append(resp.url)
        except Exception:
            pass

    page.on("response", _on_response)

    posted = False
    for btn_sel in (
        "button.comments-comment-box__submit-button",
        ".comments-comment-box__submit-button--cr",
        "button.artdeco-button--primary",
    ):
        btn = composer.locator(btn_sel).first
        try:
            if btn.is_enabled(timeout=2500):
                btn.scroll_into_view_if_needed()
                btn.click(timeout=5000)
                posted = True
                print("Clicked Post in main comment composer.", flush=True)
                break
        except Exception:
            continue
    if not posted:
        try:
            btn = composer.get_by_role("button", name=re.compile("^post$", re.I)).first
            if btn.is_enabled(timeout=2500):
                btn.scroll_into_view_if_needed()
                btn.click(timeout=5000)
                posted = True
                print("Clicked Post (role) in main comment composer.", flush=True)
        except Exception:
            pass

    if not posted:
        print("ERROR: Could not find submit button.", file=sys.stderr)
        page.remove_listener("response", _on_response)
        return 1

    _network_confirmed = False
    for _ in range(16):
        pause_uniform(0.45, 0.6)
        if _create_comment_responses:
            _network_confirmed = True
            print(
                f"Network confirm: createComment RSC-action fired ({len(_create_comment_responses)} response(s)).",
                flush=True,
            )
            break
    page.remove_listener("response", _on_response)

    pause_uniform(2.0, 3.5)
    print("Comment submit clicked.", flush=True)

    # Always verify by checking thread text — this is the ground truth.
    # Build a verify needle from the comment text itself (last ~80 chars, no URLs).
    verify_needle = verify_substring
    if not verify_needle:
        # Pick a distinctive slice from the middle/end of the comment (not a URL).
        for candidate in (text[-80:].strip(), text.strip()[-60:], text.strip()[:60]):
            has_url = "http://" in candidate or "https://" in candidate
            if not has_url and len(candidate) > 20:
                verify_needle = candidate
                break
        if not verify_needle:
            # Fallback: any non-URL token from end
            for token in reversed(text.replace("\n", " ").split()):
                if not token.startswith("http") and len(token) > 6:
                    verify_needle = token
                    break

    if not _network_confirmed:
        print(
            "WARNING: createComment network response not seen — verifying via DOM thread text.",
            file=sys.stderr,
        )

    if verify_needle:
        pause_uniform(1.5, 2.5)
        if _thread_text_contains(page, verify_needle):
            print(f"Verify OK — found in thread: {verify_needle[:100]!r}", flush=True)
        else:
            print(
                f"ERROR: Comment not found in thread after posting — likely failed silently. "
                f"Needle: {verify_needle[:100]!r}",
                file=sys.stderr,
            )
            return 4
    elif not _network_confirmed:
        # No needle and no network confirm — cannot verify, treat as failure.
        print("ERROR: Cannot verify comment — no network confirm and no verify needle.", file=sys.stderr)
        return 4

    print("Done.", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Post a LinkedIn comment (logged-in persistent profile)")
    parser.add_argument("--url", required=True, help="Post permalink, e.g. https://www.linkedin.com/feed/update/urn:li:activity:…/")
    parser.add_argument(
        "--text",
        help="Comment body (plain text). Not required with --probe-comments or --verify-substring-only.",
    )
    parser.add_argument(
        "--probe-comments",
        action="store_true",
        help="Do not post — load the URL and print whether comments look allowed or disabled.",
    )
    parser.add_argument(
        "--verify-substring-only",
        metavar="S",
        help="Do not post — load the URL and exit 0 if S appears in page text (after expanding comments).",
    )
    parser.add_argument(
        "--verify-substring",
        metavar="S",
        help="After a successful Post click, wait and fail if S is not found in the thread (catch silent failures).",
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--human-only", action="store_true", help="Always use human-like keystrokes")
    g.add_argument("--paste-only", action="store_true", help="Always use paste-like bulk insert")
    args = parser.parse_args()

    if args.probe_comments:
        with sync_playwright() as pw:
            ctx, page = _linkedin_page(pw)
            try:
                info = probe_comment_access(page, args.url)
                locked = info["comments_locked"]
                print(
                    f"status={info['status']} "
                    f"editor_visible={info['editor_visible']} "
                    f"locked={locked} "
                    f"lock_reason={info['lock_reason']!r}",
                    flush=True,
                )
                return probe_exit_code(info)
            finally:
                ctx.close()

    if args.verify_substring_only is not None:
        needle = args.verify_substring_only
        with sync_playwright() as pw:
            ctx, page = _linkedin_page(pw)
            try:
                _goto_post_ready(page, args.url)
                ok = page_contains_in_thread(page, needle)
                print("verify:", "found" if ok else "not_found", repr(needle[:120]), flush=True)
                return 0 if ok else 3
            finally:
                ctx.close()

    if not args.text:
        print("ERROR: --text is required unless using --probe-comments or --verify-substring-only.", file=sys.stderr)
        return 1

    with sync_playwright() as pw:
        ctx, page = _linkedin_page(pw)
        try:
            return submit_comment_on_page(
                page,
                args.url,
                args.text,
                human_only=args.human_only,
                paste_only=args.paste_only,
                verify_substring=args.verify_substring,
            )
        finally:
            ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
