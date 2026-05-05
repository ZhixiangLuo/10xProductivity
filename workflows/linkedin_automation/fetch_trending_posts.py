#!/usr/bin/env python3
"""
Fetch trending LinkedIn posts from your home feed, ranked by engagement.

Pulls posts from your home feed via the Voyager Dash API in a single request.
Each post comes with real engagement counts (comments, likes, shares) from the
same response. Returns posts sorted by engagement score (comments weighted 3x).

No keyword search — this surfaces what's actually generating conversation in
your network right now.

CLI:
    python fetch_trending_posts.py --max 10
    python fetch_trending_posts.py --max 20 --min-comments 5
    python fetch_trending_posts.py --max 10 --min-comments 10 --json
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tool_connections.shared_utils.browser import DEFAULT_ENV_FILE, load_env_file  # noqa: E402

_SSL = ssl.create_default_context()
_ACTIVITY_URN_RE = re.compile(r"urn:li:activity:(\d+)")
def _creds() -> tuple[str, str]:
    env = load_env_file(DEFAULT_ENV_FILE)
    return env["LINKEDIN_LI_AT"], env["LINKEDIN_JSESSIONID"].strip('"')


def _get(path: str, li_at: str, csrf: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"https://www.linkedin.com{path}",
        headers={
            "cookie": f'li_at={li_at}; JSESSIONID="{csrf}"',
            "csrf-token": csrf,
            "x-restli-protocol-version": "2.0.0",
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "x-li-lang": "en_US",
        },
    )
    with urllib.request.urlopen(req, context=_SSL, timeout=15) as r:
        return r.status, json.loads(r.read())


def fetch_trending_posts(
    max_results: int = 10,
    min_comments: int = 0,
    feed_count: int = 40,
) -> list[dict]:
    """
    Fetch trending posts from your LinkedIn home feed, ranked by engagement.

    Args:
        max_results:  Max posts to return after ranking (default 10).
        min_comments: Only include posts with at least this many comments (default 0).
        feed_count:   How many feed items to fetch before ranking (default 40).

    Returns:
        List of post dicts sorted by engagement score descending.
        Each dict: urn, author, author_url, text, permalink,
                   num_comments, num_likes, num_shares, engagement_score.
    """
    li_at, csrf = _creds()

    path = (
        f"/voyager/api/voyagerFeedDashMainFeed"
        f"?count={feed_count}&start=0&moduleKey=home-feed&q=mainFeed"
    )
    status, body = _get(path, li_at, csrf)
    if status != 200:
        raise RuntimeError(f"Feed API returned HTTP {status}")

    included = body.get("included") or []

    # Build engagement counts map: activity_urn → counts
    counts_by_urn: dict[str, dict] = {}
    for obj in included:
        if "SocialActivityCounts" not in (obj.get("$type") or ""):
            continue
        urn_raw = obj.get("urn") or ""
        m = _ACTIVITY_URN_RE.search(urn_raw)
        if not m:
            continue
        activity_urn = f"urn:li:activity:{m.group(1)}"
        counts_by_urn[activity_urn] = {
            "num_comments": obj.get("numComments") or 0,
            "num_likes": obj.get("numLikes") or 0,
            "num_shares": obj.get("numShares") or 0,
        }

    # Build post text/author map: activity_urn → post fields
    # entityUrn format: urn:li:fsd_update:(urn:li:activity:ID,...) — extract inner activity URN
    posts_by_urn: dict[str, dict] = {}
    for obj in included:
        if not (obj.get("$type") or "").endswith("Update"):
            continue
        urn_raw = obj.get("entityUrn") or ""
        m = _ACTIVITY_URN_RE.search(urn_raw)
        if not m:
            continue
        activity_urn = f"urn:li:activity:{m.group(1)}"

        # Commentary text (nested: commentary.text.text)
        commentary = obj.get("commentary") or {}
        text_obj = (commentary.get("text") or {}) if isinstance(commentary, dict) else {}
        text = (text_obj.get("text") or "") if isinstance(text_obj, dict) else ""

        # Author name + profile URL
        actor = obj.get("actor") or {}
        name_obj = (actor.get("name") or {}) if isinstance(actor, dict) else {}
        author = (name_obj.get("text") or "") if isinstance(name_obj, dict) else ""
        nav = (actor.get("navigationContext") or {}) if isinstance(actor, dict) else {}
        author_url = (nav.get("url") or "") if isinstance(nav, dict) else ""
        if author_url:
            author_url = author_url.split("?")[0]

        posts_by_urn[activity_urn] = {
            "text": text,
            "author": author,
            "author_url": author_url,
        }

    # Get ordered URNs from feed elements
    elements = (body.get("data") or {}).get("*elements") or []
    ordered_urns: list[str] = []
    for elem in elements:
        if not isinstance(elem, str):
            continue
        m = _ACTIVITY_URN_RE.search(elem)
        if m:
            urn = f"urn:li:activity:{m.group(1)}"
            if urn not in ordered_urns:
                ordered_urns.append(urn)

    # Merge and apply filters
    posts = []
    for urn in ordered_urns:
        c = counts_by_urn.get(urn, {})
        d = posts_by_urn.get(urn, {})
        num_comments = c.get("num_comments", 0)
        num_likes = c.get("num_likes", 0)
        text = d.get("text", "")
        author = d.get("author", "")

        if num_comments < min_comments:
            continue
        if not text and not author:
            continue

        # Engagement score: comments weighted 3x (stronger signal than passive likes)
        engagement_score = num_comments * 3 + num_likes

        posts.append({
            "urn": urn,
            "author": author,
            "author_url": d.get("author_url", ""),
            "text": text,
            "permalink": f"https://www.linkedin.com/feed/update/{urn}/",
            "num_comments": num_comments,
            "num_likes": num_likes,
            "num_shares": c.get("num_shares", 0),
            "engagement_score": engagement_score,
        })

    posts.sort(key=lambda p: p["engagement_score"], reverse=True)
    return posts[:max_results]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--max", type=int, default=10, help="Max posts to return (default: 10)")
    parser.add_argument(
        "--min-comments", type=int, default=0, dest="min_comments",
        help="Minimum comment count to include a post (default: 0)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON array")
    args = parser.parse_args()

    posts = fetch_trending_posts(max_results=args.max, min_comments=args.min_comments)

    if args.json:
        print(json.dumps(posts, indent=2, ensure_ascii=False))
    else:
        print(f"\nTop {len(posts)} trending posts in your feed (ranked by engagement):\n")
        for i, p in enumerate(posts, 1):
            score = p["engagement_score"]
            print(f"[{i}] {p['author'] or '(unknown)'} — {p['num_comments']} comments, {p['num_likes']} likes  (score={score})")
            print(f"    {p['permalink']}")
            snippet = (p.get("text") or "")[:200].replace("\n", " ")
            if snippet:
                print(f"    {snippet}…")
            print()
