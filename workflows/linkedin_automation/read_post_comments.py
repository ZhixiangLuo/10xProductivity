#!/usr/bin/env python3
"""Read visible comments on a LinkedIn post permalink. DOM + bounded scroll/parse retries."""

from __future__ import annotations

import argparse
import json
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
    reveal_comments_thread,
)
from tool_connections.shared_utils.browser import sync_playwright  # noqa: E402

MAX_SCROLL_ROUNDS = 4
# Cap rows returned and inner parse work per run.
DEFAULT_MAX_COMMENTS = 30


def _comment_root_locator(page):
    return page.locator(
        "article.comments-comment-entity, "
        "li.comments-comment-entity, "
        "div.comments-comment-item"
    )


def _extract_row(article) -> dict | None:
    """Best-effort author + text + profile URL from one comment root."""
    try:
        if not article.is_visible(timeout=600):
            return None
    except Exception:
        return None
    author_url = ""
    author = ""
    text = ""
    try:
        link = article.locator("a.comments-comment-meta__description-container, a[href*='/in/']").first
        if link.is_visible(timeout=400):
            author_url = (link.get_attribute("href") or "").split("?", 1)[0]
            author = (link.inner_text() or "").strip()
    except Exception:
        pass
    for sel in (
        ".comments-comment-item__main-content",
        ".update-components-text",
        ".comments-comment-item__body",
    ):
        try:
            tloc = article.locator(sel).first
            if tloc.is_visible(timeout=400):
                text = (tloc.inner_text() or "").strip()
                if len(text) > 2:
                    break
        except Exception:
            continue
    if not text and not author_url:
        return None
    return {"author": author, "author_url": author_url, "text": text}


def read_post_comments(page, url: str, max_comments: int) -> list[dict]:
    _goto_post_ready(page, url)
    _dismiss_noise(page)
    reveal_comments_thread(page)

    seen: set[str] = set()
    rows: list[dict] = []

    for round_i in range(MAX_SCROLL_ROUNDS):
        articles = _comment_root_locator(page)
        try:
            n = articles.count()
        except Exception:
            n = 0
        for i in range(min(n, 80)):
            if len(rows) >= max_comments:
                return rows
            art = articles.nth(i)
            row = _extract_row(art)
            if not row:
                continue
            key = (row.get("author_url") or "") + "\0" + (row.get("text") or "")[:200]
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

        if len(rows) >= max_comments:
            break
        page.mouse.wheel(0, 700)
        pause_uniform(0.45, 0.85)

    return rows[:max_comments]


def main() -> int:
    parser = argparse.ArgumentParser(description="List visible comments on a LinkedIn post")
    parser.add_argument("--url", required=True, help="Post permalink")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_COMMENTS, metavar="N", help="Max comments")
    parser.add_argument("--json", action="store_true", help="JSON array on stdout")
    args = parser.parse_args()

    with sync_playwright() as pw:
        ctx, page = _linkedin_page(pw)
        try:
            rows = read_post_comments(page, args.url, max(1, min(args.max, 200)))
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2), flush=True)
            else:
                for i, r in enumerate(rows, 1):
                    print(f"[{i}] {r.get('author')!r} {r.get('author_url')}", flush=True)
                    snippet = (r.get("text") or "")[:240].replace("\n", " ")
                    print(f"    {snippet}", flush=True)
            return 0
        finally:
            ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
