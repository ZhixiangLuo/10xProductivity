#!/usr/bin/env python3
"""Building block: fetch_next_post — stateless single-post iterator for agent-driven loops.

The coding agent owns the loop. This module provides three primitives:

    session = open_session()
    post, cursor = fetch_next_post(keyword, session=session)
    # agent decides: post is relevant?
    post, cursor = fetch_next_post(keyword, cursor=cursor, session=session)  # advance
    post, cursor = fetch_next_post("new keyword", session=session)           # switch keyword
    close_session(session)

``fetch_next_post`` returns one post dict + an opaque cursor the agent stores and
passes back to advance the iterator. Returns ``(None, cursor)`` when the current
keyword is exhausted.

Post dict keys: ``urn``, ``author``, ``author_url``, ``text``, ``url``.

Cursor keys (treat as opaque — subject to change):
    keyword, sort, seen_urns (list), batch (list of cached post dicts), batch_offset (int)

CLI (dry-run / test):
    python fetch_next_post.py --keyword "AI agents" [--sort recent|relevance] [--max-fetched N]
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
_AUTO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(_AUTO))

from search_posts import search_posts_on_page  # noqa: E402
from tool_connections.shared_utils.browser import DEFAULT_ENV_FILE, load_env_file, sync_playwright  # noqa: E402

PROFILE_DIR = Path.home() / ".browser_automation" / "linkedin_profile"

# How many posts to fetch per search batch (internal; agent never sees the batch directly).
_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def open_session() -> dict:
    """Open a persistent LinkedIn browser session. Returns a session handle.

    The caller is responsible for calling ``close_session(session)`` when done.
    The handle is a plain dict so it can be inspected for debugging, but treat
    it as opaque — keys may change.
    """
    load_env_file(DEFAULT_ENV_FILE)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    pw_instance = sync_playwright().start()
    try:
        Stealth = importlib.import_module("playwright_stealth").Stealth
        _stealth = Stealth()
    except ImportError:
        _stealth = None

    ctx = pw_instance.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,
        args=["--window-size=1280,900", "--window-position=100,50"],
        ignore_https_errors=True,
    )
    if _stealth is not None:
        _stealth.apply_stealth_sync(ctx)

    page = ctx.new_page()
    return {"_pw": pw_instance, "_ctx": ctx, "_page": page, "_warmed_up": False}


def close_session(session: dict) -> None:
    """Close the browser session opened by ``open_session``."""
    try:
        session["_ctx"].close()
    except Exception:
        pass
    try:
        session["_pw"].stop()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def _empty_cursor(keyword: str, sort: str = "recent") -> dict:
    return {
        "keyword": keyword,
        "sort": sort,
        "seen_urns": [],
        "batch": [],
        "batch_offset": 0,
    }


def _cursor_is_compatible(cursor: dict, keyword: str, sort: str) -> bool:
    return cursor.get("keyword") == keyword and cursor.get("sort") == sort


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_next_post(
    keyword: str,
    *,
    cursor: dict | None = None,
    session: dict,
    sort: str = "recent",
    max_fetched: int = 20,
) -> tuple[dict | None, dict]:
    """Return the next unseen post for ``keyword`` and an updated cursor.

    Args:
        keyword:     LinkedIn content search keyword or hashtag.
        cursor:      Cursor returned by the previous call (or None for a fresh start).
                     Pass None (or omit) to start from the beginning.
                     Pass a cursor from a different keyword to start that keyword fresh.
        session:     Session handle from ``open_session()``.
        sort:        "recent" (default) or "relevance".
        max_fetched: Hard cap on total posts fetched for this keyword across all batches.
                     Prevents runaway scrolling. Default 20.

    Returns:
        (post, cursor) where post is a dict with urn/author/author_url/text/url,
        or (None, cursor) when no more unseen posts are available for this keyword.
    """
    page = session["_page"]

    # Fresh start or keyword/sort changed → reset cursor.
    if cursor is None or not _cursor_is_compatible(cursor, keyword, sort):
        cursor = _empty_cursor(keyword, sort)

    seen: list[str] = cursor["seen_urns"]
    batch: list[dict] = cursor["batch"]
    offset: int = cursor["batch_offset"]

    # Walk the cached batch first (no network needed).
    while offset < len(batch):
        post = batch[offset]
        offset += 1
        urn = post.get("urn", "")
        if urn in seen:
            continue
        seen = [*seen, urn]
        new_cursor = {**cursor, "seen_urns": seen, "batch": batch, "batch_offset": offset}
        return post, new_cursor

    # Batch exhausted — fetch another page if we haven't hit the cap.
    total_seen = len(seen)
    if total_seen >= max_fetched:
        # Keyword exhausted under this cap.
        return None, {**cursor, "batch": batch, "batch_offset": offset}

    # Warm up the feed session on the very first search across all keywords.
    warmup = not session.get("_warmed_up", False)
    session["_warmed_up"] = True

    fetch_count = min(_BATCH_SIZE, max_fetched - total_seen)
    # search_posts_on_page returns up to fetch_count posts but may return fewer.
    # We request seen_count + fetch_count so LinkedIn gives us new content beyond
    # the already-seen URNs (search results don't support a page offset param directly,
    # so we over-fetch and filter locally).
    target = total_seen + fetch_count
    raw_posts: list[dict] = search_posts_on_page(
        page,
        keyword,
        max_results=target,
        sort=sort,  # type: ignore[arg-type]
        detail_fetch=False,  # skip per-permalink fetches — search page text is enough to decide relevance
        session_warmup=warmup,
    )

    # Filter to posts not yet seen.
    new_posts = [p for p in raw_posts if p.get("urn", "") not in seen]

    if not new_posts:
        return None, {**cursor, "batch": batch, "batch_offset": offset}

    # Serve the first new post, cache the rest in the cursor for subsequent calls.
    post = new_posts[0]
    remaining = new_posts[1:]
    urn = post.get("urn", "")
    seen = [*seen, urn]
    new_cursor = {
        "keyword": keyword,
        "sort": sort,
        "seen_urns": seen,
        "batch": remaining,
        "batch_offset": 0,
    }
    return post, new_cursor


# ---------------------------------------------------------------------------
# CLI — useful for quick manual testing / agent dry-runs
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Fetch LinkedIn posts one at a time via cursor. "
            "Iterates through --max-fetched posts, printing each."
        )
    )
    ap.add_argument("--keyword", required=True, help="Search keyword or hashtag")
    ap.add_argument(
        "--sort",
        choices=("recent", "relevance"),
        default="recent",
        help="Sort order (default: recent)",
    )
    ap.add_argument(
        "--max-fetched",
        type=int,
        default=5,
        help="Maximum posts to iterate over in this CLI run (default 5)",
    )
    ap.add_argument("--json", action="store_true", help="Print each post as JSON")
    args = ap.parse_args()

    session = open_session()
    try:
        cursor: dict | None = None
        count = 0
        while True:
            post, cursor = fetch_next_post(
                args.keyword,
                cursor=cursor,
                session=session,
                sort=args.sort,
                max_fetched=args.max_fetched,
            )
            if post is None:
                print(f"\nExhausted — {count} post(s) fetched for {args.keyword!r}.", flush=True)
                break
            count += 1
            if args.json:
                print(json.dumps(post, indent=2, ensure_ascii=False), flush=True)
            else:
                print(f"\n[{count}] {post.get('author') or '(unknown)'}", flush=True)
                print(f"    URL : {post.get('url', '')}", flush=True)
                snippet = (post.get("text") or "")[:200].replace("\n", " ")
                if snippet:
                    print(f"    Text: {snippet}…", flush=True)
    finally:
        close_session(session)

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
