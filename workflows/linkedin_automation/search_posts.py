"""
Building block: search_posts — LinkedIn content search by keyword/hashtag.

CLI: ``python search_posts.py --keyword "…" [--max N] [--sort recent|relevance] [--json] [--preview]``

Returns dicts: ``urn``, ``author``, ``author_url``, ``text``, ``url``.

Approach: default sort **recent** (``date_posted``); dismiss blocking modals
(Escape + common close buttons); scroll the real main column (``#workspace`` /
``.scaffold-layout__main``) with mixed smooth scroll, mouse wheel, and large jumps;
on content search, the serialized HTML is often only a few hundred KB; post copy
is commonly in ``[data-testid="expandable-text-box"]`` while activity URNs may
only appear inside encoded query params (e.g. ``highlightedUpdateUrn``) until
permalink anchors hydrate;
2–3s pause after each action (human-like; use fewer ``--max`` if you want a
shorter run); cap RSC network URNs so the scroll loop still runs; parse
``contentSearchResults`` responses for commentary + actor when JSON shape
allows; merge visible DOM into those rows; scrolling stops once there are
``max_results`` unique activity URNs (not once body ``text`` is extracted for
that many — search DOM often lags RSC). Rows still missing ``text`` can get an
in-session ``page.goto`` to the post permalink (``detail_fetch``; same cookies —
not bare ``requests``). Returned list still prefers rows with body ``text``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import random
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pacing.delays import pause_uniform  # noqa: E402
from tool_connections.shared_utils.browser import sync_playwright, DEFAULT_ENV_FILE, load_env_file  # noqa: E402

PROFILE_DIR = Path.home() / ".browser_automation" / "linkedin_profile"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ``--preview``: URL + body snippet only (full ``text`` is still in JSON / dicts).
_CLI_PREVIEW_TEXT_CHARS = 900


def _print_post_link_previews(posts: list[dict], stream) -> None:
    """One block per post: permalink, then first N characters of body (ellipsis if truncated)."""
    for i, post in enumerate(posts, 1):
        url = (post.get("url") or "").strip()
        body = (post.get("text") or "").strip()
        cap = _CLI_PREVIEW_TEXT_CHARS
        snippet = body[:cap]
        if len(body) > cap:
            snippet += "…"
        stream.write(f"[{i}] {url}\n")
        stream.write(f"    {snippet}\n\n")
    try:
        stream.flush()
    except Exception:
        pass

# --- Timing (human-like) ---
_PAUSE_AFTER_ACTION_MIN_S = 2.0
_PAUSE_AFTER_ACTION_MAX_S = 3.2

# Fine steps (most actions)
_SCROLL_FINE_MIN_PX = 100
_SCROLL_FINE_MAX_PX = 280

# Occasional larger chunks (500–800px)
_SCROLL_CHUNK_MIN_PX = 500
_SCROLL_CHUNK_MAX_PX = 800

# Mouse wheel deltas (physical wheel)
_WHEEL_DELTA_MIN = 350
_WHEEL_DELTA_MAX = 700

# How many scroll actions before a DOM harvest (wide batch — used for large ``max_results``)
_ACTIONS_PER_HARVEST = (2, 5)
# Tighter batch when you only need a few rows — less “scroll past the whole page” per cycle
_ACTIONS_PER_HARVEST_SMALL = (1, 2)


def _actions_per_harvest_bounds(max_results: int) -> tuple[int, int]:
    return _ACTIONS_PER_HARVEST_SMALL if max_results <= 10 else _ACTIONS_PER_HARVEST

# Weights for scroll mode: fine, chunk, wheel, pagejump (large smooth scroll; no click)
_SCROLL_MODE_WEIGHTS = (
    ("fine", 0.38),
    ("chunk", 0.22),
    ("wheel", 0.28),
    ("pagejump", 0.12),
)


def _pause_after_action() -> None:
    pause_uniform(_PAUSE_AFTER_ACTION_MIN_S, _PAUSE_AFTER_ACTION_MAX_S)


def _pick_scroll_mode() -> str:
    r = random.random()
    acc = 0.0
    for name, w in _SCROLL_MODE_WEIGHTS:
        acc += w
        if r <= acc:
            return name
    return "fine"


# Resolve the element LinkedIn actually scrolls (nested layout).
_SCROLL_TARGET_JS = """() => {
    const candidates = [
        document.getElementById('workspace'),
        document.querySelector('.scaffold-layout__main'),
        document.querySelector('main.scaffold-layout__main'),
        document.querySelector('[class*="scaffold-layout__main"]'),
        document.querySelector('main[id]'),
        document.querySelector('main'),
    ].filter(Boolean);

    for (const el of candidates) {
        const st = window.getComputedStyle(el);
        const oy = st.overflowY;
        if ((oy === 'auto' || oy === 'scroll' || oy === 'overlay') &&
            el.scrollHeight > el.clientHeight + 40) {
            return el;
        }
    }
    return document.getElementById('workspace') || document.documentElement;
}"""


_SMOOTH_SCROLL_EXPR = f"""
    (delta) => {{
        const el = ({_SCROLL_TARGET_JS})();
        if (!el) return;
        el.scrollBy({{ top: delta, behavior: 'smooth' }});
    }}
"""


def _scroll_fine(page) -> None:
    d = random.randint(_SCROLL_FINE_MIN_PX, _SCROLL_FINE_MAX_PX)
    page.evaluate(_SMOOTH_SCROLL_EXPR, d)
    _pause_after_action()


def _scroll_chunk(page) -> None:
    d = random.randint(_SCROLL_CHUNK_MIN_PX, _SCROLL_CHUNK_MAX_PX)
    page.evaluate(_SMOOTH_SCROLL_EXPR, d)
    _pause_after_action()


def _scroll_wheel(page) -> None:
    """Physical mouse wheel — targets center of main column."""
    box = page.evaluate(
        """() => {
            const el = document.querySelector('.scaffold-layout__main')
                || document.getElementById('workspace')
                || document.querySelector('main');
            if (!el) return { x: 640, y: 450, w: 0, h: 0 };
            const r = el.getBoundingClientRect();
            return {
                x: r.left + r.width * 0.5,
                y: r.top + Math.min(r.height * 0.45, 400),
                w: r.width,
                h: r.height,
            };
        }"""
    )
    x = max(200, min(float(box["x"]), 1180))
    y = max(120, min(float(box["y"]), 820))
    page.mouse.move(x, y)
    dy = random.randint(_WHEEL_DELTA_MIN, _WHEEL_DELTA_MAX)
    page.mouse.wheel(0, dy)
    _pause_after_action()


def _scroll_page_jump(page) -> None:
    # Large smooth scroll on the real scroll container — avoids clicking the feed
    # (fixed coords often hit reactions / “see who reacted” and open that sheet).
    d = random.randint(650, 950)
    page.evaluate(_SMOOTH_SCROLL_EXPR, d)
    _pause_after_action()


def _apply_one_scroll_action(page) -> None:
    mode = _pick_scroll_mode()
    if mode == "fine":
        _scroll_fine(page)
    elif mode == "chunk":
        _scroll_chunk(page)
    elif mode == "wheel":
        _scroll_wheel(page)
    else:
        _scroll_page_jump(page)


def _dismiss_search_overlays(page) -> None:
    """Close onboarding / promo / cookie-style modals that block the search page."""
    for _ in range(2):
        page.keyboard.press("Escape")
        time.sleep(0.15)

    selectors = (
        'button.artdeco-modal__dismiss',
        'button[aria-label="Dismiss"]',
        'button[aria-label="Close"]',
        '[data-test-modal-close-btn]',
        'button.msg-overlay-bubble-header__control--close',
    )
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=900, force=True)
            log.info("Closed overlay (%s)", sel)
            time.sleep(0.25)
        except Exception:
            continue

    for name in ("Not now", "No thanks", "Skip", "Dismiss"):
        try:
            page.get_by_role("button", name=name, exact=True).first.click(timeout=900)
            log.info('Closed overlay (button "%s")', name)
            time.sleep(0.25)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Browser setup + optional stealth
# ---------------------------------------------------------------------------

def _linkedin_context(p):
    load_env_file(DEFAULT_ENV_FILE)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,
        args=[
            "--window-size=1280,900",
            "--window-position=100,50",
        ],
        ignore_https_errors=True,
    )
    try:
        Stealth = importlib.import_module("playwright_stealth").Stealth
        Stealth().apply_stealth_sync(ctx)
        log.debug("playwright-stealth applied")
    except ImportError:
        log.warning(
            "playwright-stealth not installed (pip install playwright-stealth) — optional for bot avoidance"
        )

    page = ctx.new_page()
    log.info("Loading LinkedIn feed to establish session...")
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30_000)
    pause_uniform(1.2, 2.0)
    return ctx, page


# ---------------------------------------------------------------------------
# Network: RSC bodies contain many activity URNs (survives virtual DOM)
# ---------------------------------------------------------------------------

_ACTIVITY_URN_RE = re.compile(r"urn:li:activity:([0-9]+)")

# Body text captured from ``contentSearchResults`` RSC/JSON (keep in sync with ``_DETAIL_TEXT_CAP``).
_NETWORK_TEXT_CAP = 10_000


def _strip_linkedin_xssi_prefix(raw: str) -> str:
    s = raw.lstrip()
    if s.startswith(")]}',"):
        s = s.split("\n", 1)[-1] if "\n" in s else ""
    return s


def _commentary_text_from_obj(obj: object) -> str:
    """Pull primary post body from a Voyager/Dash-style object (best-effort)."""
    if not isinstance(obj, dict):
        return ""
    c = obj.get("commentary")
    if isinstance(c, dict):
        t = c.get("text")
        if isinstance(t, dict) and isinstance(t.get("text"), str):
            return (t.get("text") or "").strip()[:_NETWORK_TEXT_CAP]
        if isinstance(t, str):
            return t.strip()[:_NETWORK_TEXT_CAP]
    for key in ("title", "subtitle", "headline"):
        v = obj.get(key)
        if isinstance(v, dict):
            t = v.get("text")
            if isinstance(t, dict) and isinstance(t.get("text"), str):
                s = (t.get("text") or "").strip()
                if len(s) > 12:
                    return s[:_NETWORK_TEXT_CAP]
    at = obj.get("attributedText")
    if isinstance(at, dict):
        t = at.get("text")
        if isinstance(t, str) and len(t.strip()) > 12:
            return t.strip()[:_NETWORK_TEXT_CAP]
    return ""


def _actor_fields_from_obj(obj: object) -> tuple[str, str]:
    if not isinstance(obj, dict):
        return "", ""
    act = obj.get("actor") or obj.get("author") or obj.get("header")
    if not isinstance(act, dict):
        return "", ""
    name = ""
    url = ""
    nm = act.get("name") or act.get("title")
    if isinstance(nm, dict):
        t = nm.get("text")
        if isinstance(t, dict) and isinstance(t.get("text"), str):
            name = (t.get("text") or "").strip()
        elif isinstance(t, str):
            name = t.strip()
    nav = act.get("navigationContext") or act.get("navigationUrl")
    if isinstance(nav, dict):
        u = nav.get("url")
        if isinstance(u, str) and "/in/" in u:
            url = u.split("?", 1)[0]
    if not url:
        for lk in ("urn:li:fsd_profile", "miniProfile", "profileUrn"):
            v = act.get(lk)
            if isinstance(v, str) and "fsd_profile" in v:
                # ``urn:li:fsd_profile:ACoAA...`` — no public URL without another field
                break
    return name[:200], url


def _activity_urn_from_obj(obj: object) -> str | None:
    if not isinstance(obj, dict):
        return None
    for k, v in obj.items():
        if not isinstance(v, str):
            continue
        if "urn:li:activity:" not in v:
            continue
        m = _ACTIVITY_URN_RE.search(v)
        if m:
            return f"urn:li:activity:{m.group(1)}"
    return None


def _walk_json_for_search_hits(obj: object, acc: dict[str, dict], depth: int = 0) -> None:
    if depth > 48:
        return
    if isinstance(obj, dict):
        urn = _activity_urn_from_obj(obj)
        body = _commentary_text_from_obj(obj)
        if urn and body:
            row = acc.setdefault(urn, {"text": "", "author": "", "author_url": ""})
            if len(body) > len((row.get("text") or "")):
                row["text"] = body
            an, au = _actor_fields_from_obj(obj)
            if an and not (row.get("author") or "").strip():
                row["author"] = an
            if au and not (row.get("author_url") or "").strip():
                row["author_url"] = au
        for v in obj.values():
            _walk_json_for_search_hits(v, acc, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk_json_for_search_hits(v, acc, depth + 1)


def _json_load_loose(raw: str) -> object | None:
    s = _strip_linkedin_xssi_prefix(raw)
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    for line in s.splitlines():
        line = line.strip()
        if not line or line[0] not in "{[":
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _fallback_text_by_urn_from_raw(raw: str) -> dict[str, str]:
    """
    When the payload is not valid single JSON, grab long ``"text"`` strings in a
    window after each activity URN (RSC often interleaves chunks).
    """
    out: dict[str, str] = {}
    for m in _ACTIVITY_URN_RE.finditer(raw):
        urn = f"urn:li:activity:{m.group(1)}"
        chunk = raw[m.start() : m.start() + 30_000]
        focus = chunk
        if "commentary" in chunk:
            focus = chunk[chunk.find("commentary") :][:25_000]
        found: list[str] = []
        for mm in re.finditer(r'"text"\s*:\s*"((?:\\.|[^"\\])*)"', focus):
            try:
                decoded = json.loads('"' + mm.group(1) + '"')
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, str) and 25 < len(decoded) < _NETWORK_TEXT_CAP:
                found.append(decoded)
        if not found:
            continue
        best = max(found, key=len)
        prev = (out.get(urn) or "")
        if len(best) > len(prev):
            out[urn] = best[:_NETWORK_TEXT_CAP]
    return out


def _parse_content_search_response_body(raw: str) -> dict[str, dict]:
    """urn -> partial row updates from one ``contentSearchResults`` response."""
    acc: dict[str, dict] = {}
    parsed = _json_load_loose(raw)
    if parsed is not None:
        _walk_json_for_search_hits(parsed, acc)
    if not acc:
        for urn, txt in _fallback_text_by_urn_from_raw(raw).items():
            acc[urn] = {"text": txt, "author": "", "author_url": ""}
    return acc


_CK_FROM_COMMENT_BOX_RE = re.compile(
    r'commentBoxMode-[A-Za-z0-9+/=_\-]+-([A-Za-z0-9+/=_\-]{20,})FeedType_FLAGSHIP_SEARCH'
)
_REACTION_URN_RE = re.compile(r'reactionState-urn:li:activity:([0-9]+)')


def _parse_ck_to_urn_from_html(raw: str) -> dict[str, str]:
    """Extract componentKey → activity URN mapping from the SDUI HTML payload.

    LinkedIn's server-rendered HTML embeds state keys of the form:
        reactionState-urn:li:activity:NNN          ← the numeric URN
        commentBoxMode-{b64}-{componentKey}FeedType_FLAGSHIP_SEARCH

    Both appear together for each post card. We find the nearest preceding
    reactionState URN for every commentBoxMode componentKey (within 5 KB) to
    build a reliable ck→urn map without any positional guessing.
    """
    urn_positions = [
        (m.start(), f"urn:li:activity:{m.group(1)}")
        for m in _REACTION_URN_RE.finditer(raw)
    ]
    ck_to_urn: dict[str, str] = {}
    for m in _CK_FROM_COMMENT_BOX_RE.finditer(raw):
        ck = m.group(1)
        if ck in ck_to_urn:
            continue
        preceding = [(pos, urn) for pos, urn in urn_positions if pos < m.start()]
        if not preceding:
            continue
        nearest_pos, nearest_urn = max(preceding, key=lambda x: x[0])
        if m.start() - nearest_pos < 5000:
            ck_to_urn[ck] = nearest_urn
    return ck_to_urn


def _make_network_handler(
    posts_by_urn: OrderedDict[str, dict],
    state: dict,
    *,
    network_urn_cap: int,
):
    """Intercept responses to collect URNs and build the componentKey→URN map.

    Two response types matter:
    - text/html (the initial search page): parse reactionState+commentBoxMode
      pairs to build a reliable ck→urn map stored in ``state['ck_to_urn']``.
    - contentSearchResults (Voyager/RSC JSON): extract text/author when available.
    """

    def on_response(response) -> None:
        if not state.get("active", True):
            return
        try:
            url = response.url
            status = response.status
            ct = response.headers.get("content-type", "")
            if status != 200:
                return

            # HTML page response — parse componentKey→URN map.
            if "search/results/content" in url and "text/html" in ct:
                raw = response.text()
                ck_map = _parse_ck_to_urn_from_html(raw)
                if ck_map:
                    state.setdefault("ck_to_urn", {}).update(ck_map)
                    log.info("  [ck-map] built %d componentKey→URN pairs from HTML", len(ck_map))
                # Also collect URNs from the HTML for posts_by_urn.
                for m in _ACTIVITY_URN_RE.finditer(raw):
                    if len(posts_by_urn) >= network_urn_cap:
                        break
                    urn = f"urn:li:activity:{m.group(1)}"
                    if urn not in posts_by_urn:
                        posts_by_urn[urn] = {
                            "urn": urn,
                            "author": "",
                            "author_url": "",
                            "text": "",
                            "url": f"https://www.linkedin.com/feed/update/{urn}/",
                            "_from_network": True,
                        }
                return

            # Voyager/RSC JSON — extract text and author when present.
            if "contentSearchResults" not in url:
                return
            raw = response.text()
        except Exception:
            return

        if len(posts_by_urn) >= network_urn_cap:
            return

        parsed_rows = _parse_content_search_response_body(raw)
        for m in _ACTIVITY_URN_RE.finditer(raw):
            if len(posts_by_urn) >= network_urn_cap:
                return
            aid = m.group(1)
            urn = f"urn:li:activity:{aid}"
            if urn not in posts_by_urn:
                posts_by_urn[urn] = {
                    "urn": urn,
                    "author": "",
                    "author_url": "",
                    "text": "",
                    "url": f"https://www.linkedin.com/feed/update/{urn}/",
                    "_from_network": True,
                }
        for urn, fields in parsed_rows.items():
            if len(posts_by_urn) >= network_urn_cap and urn not in posts_by_urn:
                continue
            if urn not in posts_by_urn:
                posts_by_urn[urn] = {
                    "urn": urn,
                    "author": "",
                    "author_url": "",
                    "text": "",
                    "url": f"https://www.linkedin.com/feed/update/{urn}/",
                    "_from_network": True,
                }
            cur = posts_by_urn[urn]
            t = (fields.get("text") or "").strip()
            if t and len(t) > len((cur.get("text") or "").strip()):
                cur["text"] = t
            an = (fields.get("author") or "").strip()
            if an and not (cur.get("author") or "").strip():
                cur["author"] = an
            au = (fields.get("author_url") or "").strip()
            if au and not (cur.get("author_url") or "").strip():
                cur["author_url"] = au

    return on_response


def _count_with_body_text(posts_by_urn: OrderedDict[str, dict]) -> int:
    return sum(1 for p in posts_by_urn.values() if (p.get("text") or "").strip())


def _finalize_post_list(posts_by_urn: OrderedDict[str, dict], max_results: int) -> list[dict]:
    """Prefer rows with post text (DOM-enriched); pad with network-only URNs if needed."""
    items = list(posts_by_urn.values())
    with_text = [p for p in items if (p.get("text") or "").strip()]
    without = [p for p in items if not (p.get("text") or "").strip()]
    merged = with_text + without
    out: list[dict] = []
    seen: set[str] = set()
    for p in merged:
        u = p.get("urn", "")
        if not u or u in seen:
            continue
        seen.add(u)
        # Keep _text_unverified so callers can decide whether to permalink-verify.
        # Strip all other private _ keys.
        row = {k: v for k, v in p.items() if not str(k).startswith("_")}
        if p.get("_text_unverified"):
            row["_text_unverified"] = True
        out.append(row)
        if len(out) >= max_results:
            break
    return out


def _merge_dom_into_posts(posts_by_urn: OrderedDict[str, dict], batch: list[dict]) -> None:
    for item in batch:
        u = item["urn"]
        if u not in posts_by_urn:
            posts_by_urn[u] = {**item}
            continue
        cur = posts_by_urn[u]
        for key in ("author", "author_url", "text"):
            v = (item.get(key) or "").strip()
            if v and not (cur.get(key) or "").strip():
                cur[key] = v


def _merge_expandable_orphans_by_order(
    posts_by_urn: OrderedDict[str, dict], orphans: list[dict]
) -> None:
    """
    Pair orphan text boxes (no URN anchor in their DOM subtree) to URNs that
    still have no body text, by position order.

    On LinkedIn's SDUI search layout there are *zero* activity URN anchors in
    the DOM — every URN comes from RSC network responses. Positional pairing is
    a best-effort heuristic: RSC order and DOM render order don't always match,
    so paired posts are flagged ``_text_unverified=True``. Callers must open
    the post permalink to confirm text before trusting it.

    We pair as many (orphan, gap-urn) pairs as possible in order, stopping when
    either list runs out. Surplus orphans or surplus gap-URNs are left alone.
    """
    if not orphans:
        return
    need = [urn for urn, p in posts_by_urn.items() if not (p.get("text") or "").strip()]
    if not need:
        return

    pairs = min(len(orphans), len(need))
    log.info(
        "  [dom+orphan-order] pairing %d orphan box(es) → %d gap URN(s) by position order (UNVERIFIED)",
        pairs,
        len(need),
    )
    for i in range(pairs):
        urn = need[i]
        o = orphans[i]
        t = (o.get("text") or "").strip()
        if not t:
            continue
        cur = posts_by_urn[urn]
        cur["text"] = t
        cur["_text_unverified"] = True  # must confirm via permalink before trusting
        an = (o.get("author") or "").strip()
        if an and not (cur.get("author") or "").strip():
            cur["author"] = an
        au = (o.get("author_url") or "").strip()
        if au and not (cur.get("author_url") or "").strip():
            cur["author_url"] = au
        log.info("  [dom+orphan-order] %s — %d chars (UNVERIFIED)", urn, len(t))


# ---------------------------------------------------------------------------
# DOM extraction (visible cards only — merged into map for recycling)
# ---------------------------------------------------------------------------

_EXTRACT_JS = f"""() => {{
    const TEXT_CAP = {_NETWORK_TEXT_CAP};

    const activityUrnFromHref = (href) => {{
        if (!href) return null;
        let decoded = href;
        try {{ decoded = decodeURIComponent(href.replace(/\\+/g, '%20')); }} catch (e) {{}}
        let m = decoded.match(/urn:li:activity:([0-9]+)/);
        if (m) return 'urn:li:activity:' + m[1];
        m = href.match(/highlightedUpdateUrn=([^&"']+)/);
        if (m) {{
            try {{
                const inner = decodeURIComponent(m[1].replace(/\\+/g, '%20'));
                const m2 = inner.match(/urn:li:activity:([0-9]+)/);
                if (m2) return 'urn:li:activity:' + m2[1];
            }} catch (e) {{}}
        }}
        return null;
    }};

    const findCardRoot = (el) => {{
        let e = el;
        for (let i = 0; i < 28 && e; i++) {{
            if (e.getAttribute && e.getAttribute('role') === 'listitem') return e;
            if (e.tagName === 'ARTICLE') return e;
            e = e.parentElement;
        }}
        e = el;
        for (let i = 0; i < 14 && e; i++) e = e.parentElement;
        return e;
    }};

    const urnFromCard = (root) => {{
        if (!root || !root.querySelectorAll) return null;
        for (const a of root.querySelectorAll('a[href]')) {{
            const urn = activityUrnFromHref(a.getAttribute('href') || '');
            if (urn) return urn;
        }}
        return null;
    }};

    const authorFromContainer = (container) => {{
        let author = '';
        let authorUrl = '';
        if (!container) return {{ author, author_url: authorUrl }};
        const authorLinks = container.querySelectorAll('a[href*="/in/"]');
        for (const al of authorLinks) {{
            const h = al.href || '';
            if (!h.includes('/in/')) continue;
            authorUrl = h.split('?')[0];
            const label = al.getAttribute('aria-label') || '';
            const labelMatch = label.match(/^View (.+?)(?:'s| profile)/i);
            if (labelMatch) {{ author = labelMatch[1].trim(); break; }}
            const spans = al.querySelectorAll('span');
            for (const s of spans) {{
                const t = (s.innerText || s.textContent || '').trim();
                if (t && t.length > 1 && t.length < 60 && !t.includes('•') && !t.match(/^[0-9]/)) {{
                    author = t; break;
                }}
            }}
            if (author) break;
        }}
        return {{ author, author_url: authorUrl }};
    }};

    const byUrn = new Map();

    const upsert = (urn, author, authorUrl, text) => {{
        if (!urn || !text) return;
        const url = 'https://www.linkedin.com/feed/update/' + urn + '/';
        const prev = byUrn.get(urn);
        const t = text.trim().slice(0, TEXT_CAP);
        const bestText =
            !prev || !prev.text || t.length > prev.text.length ? t : prev.text;
        const mergedAuthor =
            (author && author.trim()) || (prev && prev.author) || '';
        const mergedUrl =
            (authorUrl && authorUrl.trim()) || (prev && prev.author_url) || '';
        byUrn.set(urn, {{
            urn,
            author: mergedAuthor,
            author_url: mergedUrl,
            text: bestText,
            url,
        }});
    }};

    // 1) Classic permalink anchors (feed still uses these on some surfaces).
    for (const link of document.querySelectorAll('a[href*="/feed/update/urn:li:activity:"]')) {{
        const href = link.href || '';
        const match = href.match(/urn:li:activity:([0-9]+)/);
        if (!match) continue;
        const urn = 'urn:li:activity:' + match[1];
        let container = link.parentElement;
        for (let i = 0; i < 20; i++) {{
            if (!container) break;
            const tag = container.tagName;
            if (tag === 'LI' || tag === 'ARTICLE') break;
            if (tag === 'DIV' && container.parentElement &&
                (container.parentElement.tagName === 'UL' || container.parentElement.tagName === 'OL')) break;
            container = container.parentElement;
        }}
        const {{ author, author_url }} = authorFromContainer(container);
        let text = '';
        if (container) {{
            for (const sel of [
                '[class*="update-components-text"]',
                '[class*="feed-shared-text"]',
                '[class*="attributed-text"]',
                '[class*="commentary"]',
            ]) {{
                const el = container.querySelector(sel);
                if (el) {{ text = el.innerText.trim().slice(0, TEXT_CAP); break; }}
            }}
            if (!text) {{
                let best = '';
                for (const p of container.querySelectorAll('p')) {{
                    const t = (p.innerText || '').trim();
                    if (t.length > best.length) best = t;
                }}
                text = best.slice(0, TEXT_CAP);
            }}
        }}
        upsert(urn, author, author_url, text);
    }}

    // 2) URN-first pairing: start from every activity URN anchor, walk UP to card root,
    //    then look DOWN for the expandable text box. More reliable than text-box-first
    //    on SDUI search layouts where the URN anchor is a sibling, not a parent.
    const pairedUrns = new Set();
    for (const link of document.querySelectorAll('a[href]')) {{
        const urn = activityUrnFromHref(link.getAttribute('href') || '');
        if (!urn || pairedUrns.has(urn)) continue;
        // Walk up to card root
        const root = findCardRoot(link);
        if (!root) continue;
        // Look for expandable text box inside this card
        const box = root.querySelector('[data-testid="expandable-text-box"]');
        if (!box) continue;
        let raw = (box.innerText || box.textContent || '').trim();
        raw = raw.replace(/\\s*…\\s*more\\s*$/i, '').replace(/\\s*\\.\\.\\.\\s*more\\s*$/i, '').trim();
        if (raw.length < 24) continue;
        const {{ author, author_url }} = authorFromContainer(root);
        upsert(urn, author, author_url, raw.slice(0, TEXT_CAP));
        pairedUrns.add(urn);
    }}

    // 3) Text-box-first fallback for any boxes not yet paired (classic feed layout).
    const expandable_orphans = [];
    for (const box of document.querySelectorAll('[data-testid="expandable-text-box"]')) {{
        let raw = (box.innerText || box.textContent || '').trim();
        raw = raw.replace(/\\s*…\\s*more\\s*$/i, '').replace(/\\s*\\.\\.\\.\\s*more\\s*$/i, '').trim();
        if (raw.length < 24) continue;
        const root = findCardRoot(box);
        let urn = urnFromCard(root);
        // Skip if already paired by URN-first pass
        if (urn && pairedUrns.has(urn)) continue;
        let {{ author, author_url }} = authorFromContainer(root);
        if (!urn && root && root.parentElement) {{
            urn = urnFromCard(root.parentElement);
            if (!author) {{ const a2 = authorFromContainer(root.parentElement); author = a2.author; author_url = a2.author_url; }}
        }}
        if (!urn) {{
            expandable_orphans.push({{
                text: raw.slice(0, TEXT_CAP),
                author: author || '',
                author_url: author_url || '',
            }});
            continue;
        }}
        upsert(urn, author, author_url, raw.slice(0, TEXT_CAP));
        pairedUrns.add(urn);
    }}

    // 4) componentKey→card map for the reliable keyed join.
    // The DOM [role="listitem"][componentkey] element wraps each post card.
    // The componentkey has the form "expanded{{CK}}FeedType_FLAGSHIP_SEARCH".
    // We strip the prefix/suffix to get the bare CK matching the HTML ck_to_urn map.
    const ckToCard = {{}};
    for (const el of document.querySelectorAll('[role="listitem"][componentkey]')) {{
        let ck = el.getAttribute('componentkey') || '';
        // Strip "expanded" prefix and "FeedType_FLAGSHIP_SEARCH" suffix.
        ck = ck.replace(/^expanded/, '').replace(/FeedType_FLAGSHIP_SEARCH$/, '');
        if (!ck) continue;
        const box = el.querySelector('[data-testid="expandable-text-box"]');
        if (!box) continue;
        let raw = (box.innerText || box.textContent || '').trim();
        raw = raw.replace(/\\s*…\\s*more\\s*$/i, '').replace(/\\s*\\.\\.\\.\\s*more\\s*$/i, '').trim();
        if (raw.length < 24) continue;
        const {{ author, author_url }} = authorFromContainer(el);
        ckToCard[ck] = {{
            text: raw.slice(0, TEXT_CAP),
            author: author || '',
            author_url: author_url || '',
        }};
    }}

    return {{
        posts: Array.from(byUrn.values()),
        expandable_orphans,
        ck_to_card: ckToCard,
    }};
}}"""


_FIND_EXPAND_BUTTONS_JS = """() => {
    // Return bounding boxes of collapsed "… more" buttons that are INSIDE the
    // visible viewport. Buttons scrolled above or below the fold are excluded —
    // their getBoundingClientRect().top is < 100 or > viewportHeight-60, and
    // clicking them at clamped coordinates lands on the nav bar or footer.
    // Already-clicked buttons are removed from the DOM by LinkedIn, so they
    // never re-appear here.
    const vh = window.innerHeight || 800;
    const Y_MIN = 100;   // stay clear of top nav / filter bar
    const Y_MAX = vh - 60;
    const boxes = [];
    const seen = new Set();

    const addBtn = (btn) => {
        if (seen.has(btn)) return;
        seen.add(btn);
        try {
            const r = btn.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) return;          // not rendered
            const cy = r.top + r.height * 0.5;
            if (cy < Y_MIN || cy > Y_MAX) return;             // outside viewport
            boxes.push({ x: r.left + r.width * 0.5, y: cy });
        } catch (e) {}
    };

    for (const btn of document.querySelectorAll('[data-testid="expandable-text-button"]')) {
        addBtn(btn);
    }
    // Fallback: any button whose visible text is a "see more" variant
    if (boxes.length === 0) {
        for (const btn of document.querySelectorAll('button')) {
            const label = (btn.innerText || btn.textContent || '').trim().toLowerCase();
            if (label === '… more' || label === '…more' || label === 'see more' || label === '...more') {
                addBtn(btn);
            }
        }
    }
    return boxes;
}"""

_COUNT_EXPAND_CHARS_JS = """() => {
    // Return total visible characters across all expandable text boxes (post-expand measure).
    let total = 0;
    for (const box of document.querySelectorAll('[data-testid="expandable-text-box"]')) {
        total += (box.innerText || box.textContent || '').length;
    }
    return total;
}"""


def _expand_see_more(page, *, dwell: bool = True) -> None:
    """Click 'see more' buttons one at a time, mimicking human reading behaviour.

    Only clicks buttons currently visible inside the safe viewport zone (y: 100–vh-60).
    LinkedIn removes the button from the DOM once expanded, so already-expanded
    buttons never re-appear.

    Args:
        dwell: When True (first harvest after page load) pause 0.5–1.2 s before clicking
               to mimic a human scanning the page. Set False for mid-scroll harvests
               so we don't add a full dwell on every scroll cycle.
    """
    try:
        if dwell:
            # Human scans the page briefly before reaching for the button.
            pause_uniform(0.5, 1.2)

        buttons = page.evaluate(_FIND_EXPAND_BUTTONS_JS)
        if not buttons:
            return

        log.info("  [expand-more] found %d 'see more' button(s) in viewport — clicking one by one", len(buttons))

        for i, btn in enumerate(buttons):
            x, y = float(btn["x"]), float(btn["y"])
            # Move mouse naturally to the button before clicking.
            page.mouse.move(x, y)
            pause_uniform(0.3, 0.7)  # hover pause before click

            page.mouse.click(x, y)
            log.info("  [expand-more] clicked button %d/%d at (%.0f, %.0f)", i + 1, len(buttons), x, y)

            # Short settle after click — LinkedIn can't observe how long we "read"
            # expanded text, so a fixed 0.4–0.7s is enough for the DOM to update.
            pause_uniform(0.4, 0.7)

    except Exception as e:
        log.debug("expand_see_more error (non-fatal): %s", e)


def _merge_text_via_ck_map(
    posts_by_urn: OrderedDict[str, dict],
    ck_to_urn: dict[str, str],
    ck_to_card: dict[str, dict],
) -> int:
    """Assign text from DOM cards to URNs using the componentKey→URN map.

    This is the reliable keyed join that replaces positional orphan pairing.
    Returns the number of posts successfully filled.
    """
    filled = 0
    for ck, card in ck_to_card.items():
        urn = ck_to_urn.get(ck)
        if not urn:
            continue
        text = (card.get("text") or "").strip()
        if not text:
            continue
        if urn not in posts_by_urn:
            posts_by_urn[urn] = {
                "urn": urn,
                "author": "",
                "author_url": "",
                "text": "",
                "url": f"https://www.linkedin.com/feed/update/{urn}/",
            }
        cur = posts_by_urn[urn]
        if len(text) > len((cur.get("text") or "").strip()):
            cur["text"] = text
            cur.pop("_text_unverified", None)
            filled += 1
        an = (card.get("author") or "").strip()
        if an and not (cur.get("author") or "").strip():
            cur["author"] = an
        au = (card.get("author_url") or "").strip()
        if au and not (cur.get("author_url") or "").strip():
            cur["author_url"] = au
    return filled


def _harvest_dom(page, posts_by_urn: OrderedDict[str, dict], *, first_harvest: bool = False, state: dict | None = None) -> None:
    # Only do the human-like expand on the first harvest after page load.
    # Subsequent harvests (mid-scroll) just expand whatever buttons are newly in viewport.
    _expand_see_more(page, dwell=first_harvest)
    evaluated = page.evaluate(_EXTRACT_JS)
    if isinstance(evaluated, dict):
        batch = evaluated.get("posts") or []
        orphans = evaluated.get("expandable_orphans") or []
        ck_to_card = evaluated.get("ck_to_card") or {}
    else:
        batch = evaluated
        orphans = []
        ck_to_card = {}
    before_keys = set(posts_by_urn.keys())
    _merge_dom_into_posts(posts_by_urn, batch)

    # Preferred: keyed join via componentKey→URN map built from HTML.
    ck_to_urn = (state or {}).get("ck_to_urn", {})
    if ck_to_urn and ck_to_card:
        filled = _merge_text_via_ck_map(posts_by_urn, ck_to_urn, ck_to_card)
        log.info("  [ck-join] filled %d post(s) via componentKey→URN join", filled)
    elif orphans:
        # Fallback: positional pairing (unreliable — only used when ck_to_urn map unavailable).
        log.warning("  [ck-join] no ck_to_urn map — falling back to positional orphan pairing (MAY MISMATCH)")
        _merge_expandable_orphans_by_order(posts_by_urn, orphans)

    for item in batch:
        u = item["urn"]
        if u not in before_keys:
            log.info("  [dom+new] %s — %s", posts_by_urn[u].get("author") or "(unknown)", u)


# Max characters stored from a permalink detail view (long hashtag dumps, etc.)
_DETAIL_TEXT_CAP = _NETWORK_TEXT_CAP

# Rows whose body text from RSC ``commentary`` (or co-located DOM card) is at
# least this long are considered "have text" and skipped by the per-permalink
# enrichment pass — RSC commentary is already URN-co-located (no orphan-pair
# risk), so re-opening the permalink is wasted N×goto when callers (e.g.
# ``engage_once.py``) only need URLs + a short snippet.
_ENRICH_SKIP_TEXT_CHARS = 60

_DETAIL_EXTRACT_JS = f"""() => {{
    const CAP = {_DETAIL_TEXT_CAP};
    const textSels = [
        '.update-components-text',
        '.feed-shared-update-v2__commentary',
        '[class*="feed-shared-update-v2__commentary"]',
        '.feed-shared-inline-show-more-text',
        '[class*="update-components-update-v2__commentary"]',
        '[class*="feed-shared-text"]',
        '[class*="attributed-text"]',
    ];
    let text = '';
    for (const sel of textSels) {{
        const el = document.querySelector(sel);
        if (!el) continue;
        const t = (el.innerText || '').trim();
        if (t.length > 20) {{ text = t.slice(0, CAP); break; }}
    }}
    if (!text) {{
        const art = document.querySelector('main article') || document.querySelector('article');
        if (art) {{
            const t = (art.innerText || '').trim();
            if (t.length > 40) text = t.slice(0, CAP);
        }}
    }}
    let author = '';
    let authorUrl = '';
    for (const al of document.querySelectorAll('a[href*="/in/"]')) {{
        const h = al.href || '';
        if (!h.includes('/in/')) continue;
        if (h.includes('/feed/')) continue;
        authorUrl = h.split('?')[0];
        const label = al.getAttribute('aria-label') || '';
        const m = label.match(/^View (.+?)(?:'s| profile)/i);
        if (m) author = m[1].trim();
        if (!author) {{
            for (const s of al.querySelectorAll('span')) {{
                const t = (s.innerText || s.textContent || '').trim();
                if (t && t.length > 1 && t.length < 80 && !t.includes('•') && !t.match(/^[0-9]+$/)) {{
                    author = t;
                    break;
                }}
            }}
        }}
        if (author || authorUrl) break;
    }}
    return {{ text, author, author_url: authorUrl }};
}}"""


def _enrich_posts_from_permalinks(page, posts: list[dict]) -> None:
    """Set canonical ``text`` (and author when safe) by opening each post URL.

    Search-page DOM/RSC merge can attach the wrong snippet to an activity URN
    in the **orphan-pairing** path. Rows whose ``text`` came from RSC
    ``commentary`` (URN-co-located) or from a DOM card with the URN inside
    its own subtree are already correct — opening their permalink is wasted
    N×goto, so we skip those and only enrich rows that are empty / very short.
    """
    n = len(posts)
    if not n:
        return
    needs_fetch = [
        p for p in posts
        if len((p.get("text") or "").strip()) < _ENRICH_SKIP_TEXT_CHARS
    ]
    skipped = n - len(needs_fetch)
    if skipped:
        log.info(
            "Detail fetch: skipping %d/%d permalink(s) — body text already present "
            "from RSC commentary / co-located DOM (>=%d chars)",
            skipped,
            n,
            _ENRICH_SKIP_TEXT_CHARS,
        )
    if not needs_fetch:
        return
    log.info("Detail fetch: opening %d permalink(s) for canonical body text", len(needs_fetch))
    for idx, post in enumerate(needs_fetch):
        url = (post.get("url") or "").strip()
        if "/feed/update/" not in url or "urn:li:activity:" not in url:
            continue
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25_000)
            pause_uniform(0.35, 0.7)
            _dismiss_search_overlays(page)
            data = page.evaluate(_DETAIL_EXTRACT_JS)
            t = (data.get("text") or "").strip()
            if t:
                post["text"] = t
            au = (data.get("author") or "").strip()
            # Detail page sometimes resolves the first chrome link ("Premium", etc.)
            if au and au.lower() not in {"premium", "sponsored", "promoted"}:
                if not (post.get("author") or "").strip():
                    post["author"] = au
            uu = (data.get("author_url") or "").strip()
            if uu and not (post.get("author_url") or "").strip():
                post["author_url"] = uu
            if t:
                log.info("Detail fetch OK — %d chars — %s", len(t), url[:72])
            else:
                log.warning("Detail fetch got no body text: %s", url[:80])
        except Exception as e:
            log.warning("Detail fetch failed for %s: %s", url[:80], e)
        if idx < len(needs_fetch) - 1:
            pause_uniform(0.35, 0.75)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SortMode = Literal["recent", "relevance"]


def search_posts_on_page(
    page,
    keyword: str,
    max_results: int = 10,
    *,
    sort: SortMode = "recent",
    detail_fetch: bool = True,
    session_warmup: bool = True,
) -> list[dict]:
    """
    Run content search on an **existing** Playwright ``page`` (same persistent
    profile session). Use this when chaining probe/comment in one browser
    (e.g. ``engage_once.py``) instead of spawning multiple subprocesses.

    When ``session_warmup`` is true, loads the home feed once before search —
    mirrors standalone ``search_posts`` (which uses ``_linkedin_context``).
    Set false if the caller already navigated (e.g. feed was just loaded).
    """
    sort_by = '["date_posted"]' if sort == "recent" else '["relevance"]'
    params = urlencode(
        {
            "keywords": keyword,
            "origin": "GLOBAL_SEARCH_HEADER",
            "sortBy": sort_by,
        }
    )
    search_url = f"https://www.linkedin.com/search/results/content/?{params}"

    posts_by_urn: OrderedDict[str, dict] = OrderedDict()
    _net_state = {"active": True}
    _network_cap = max(24, max_results * 6)
    _on_network_response = _make_network_handler(
        posts_by_urn, _net_state, network_urn_cap=_network_cap
    )
    page.on("response", _on_network_response)
    out: list[dict] = []

    try:
        if session_warmup:
            log.info("Loading LinkedIn feed to establish session...")
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30_000)
            pause_uniform(1.2, 2.0)

        total_actions = 0
        log.info("Navigating to content search (sort=%s): %s", sort, keyword)
        page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_url(
                lambda u: "/search/results/content/" in unquote(u),
                timeout=10_000,
            )
        except Exception:
            log.warning("URL confirmation timed out — continuing")

        # Wait for content to appear (up to 2s), then act — mirrors a human who
        # starts interacting ~2-3s after the page renders, not after separate
        # settle + selector + second pause stacked on top of each other.
        _dismiss_search_overlays(page)
        post_anchor_wait_ms = 2_000 if max_results <= 5 else 3_000
        log.info(
            "Waiting up to %.1fs for first classic post link (optional; URNs also come from RSC)...",
            post_anchor_wait_ms / 1000,
        )
        try:
            page.wait_for_selector(
                'a[href*="/feed/update/urn:li:activity:"]',
                timeout=post_anchor_wait_ms,
            )
        except Exception:
            log.warning(
                "No post links in DOM within %.1fs — continuing (network may still populate)",
                post_anchor_wait_ms / 1000,
            )

        _dismiss_search_overlays(page)
        # No extra pause here — wait_for_selector already spent time on the page;
        # _expand_see_more's dwell handles the pre-click human scan pause.
        _harvest_dom(page, posts_by_urn, first_harvest=True, state=_net_state)

        log.info(
            "Scroll mix: fine %d–%d px, chunk %d–%d px, wheel, pagejump; pause %.1f–%.1f s each",
            _SCROLL_FINE_MIN_PX,
            _SCROLL_FINE_MAX_PX,
            _SCROLL_CHUNK_MIN_PX,
            _SCROLL_CHUNK_MAX_PX,
            _PAUSE_AFTER_ACTION_MIN_S,
            _PAUSE_AFTER_ACTION_MAX_S,
        )

        stall_cycles = 0
        max_actions = max(32, max_results * 8)

        while total_actions < max_actions:
            if len(posts_by_urn) >= max_results:
                log.info("Already have %d unique posts — skipping further scroll", max_results)
                break

            count_before = len(posts_by_urn)
            text_before = _count_with_body_text(posts_by_urn)

            lo, hi = _actions_per_harvest_bounds(max_results)
            n_actions = random.randint(lo, hi)
            for _ in range(n_actions):
                _apply_one_scroll_action(page)
                total_actions += 1
                if len(posts_by_urn) >= max_results:
                    break
                if total_actions >= max_actions:
                    break

            _harvest_dom(page, posts_by_urn, first_harvest=False, state=_net_state)

            if len(posts_by_urn) >= max_results:
                log.info("Collected %d unique posts (URNs); stopping scroll", max_results)
                break

            if len(posts_by_urn) == count_before and _count_with_body_text(posts_by_urn) == text_before:
                stall_cycles += 1
                if stall_cycles >= 12:
                    log.info("Stalled after %d cycles — stopping", stall_cycles)
                    break
                _dismiss_search_overlays(page)
                _pause_after_action()
            else:
                stall_cycles = 0

        log.info("Scroll actions used during search: %d", total_actions)

        out = _finalize_post_list(posts_by_urn, max_results)
        if detail_fetch:
            _enrich_posts_from_permalinks(page, out)

    finally:
        _net_state["active"] = False
        try:
            page.remove_listener("response", _on_network_response)
        except Exception:
            pass

    if not out:
        out = _finalize_post_list(posts_by_urn, max_results)

    log.info("Done — %d posts (network + DOM merged)", len(out))
    return out


def search_posts(
    keyword: str,
    max_results: int = 10,
    *,
    sort: SortMode = "recent",
    detail_fetch: bool = True,
) -> list[dict]:
    """
    Search LinkedIn content. Default **sort** is ``recent`` (``date_posted``)
    to encourage fuller result batches vs ``relevance`` alone.

    When ``detail_fetch`` is true, **each** returned post is opened at its
    permalink so ``text`` matches that URL (session cookies — not raw HTTP).
    """
    with sync_playwright() as p:
        ctx, page = _linkedin_context(p)
        try:
            # ``_linkedin_context`` already hit the feed — skip duplicate warmup.
            return search_posts_on_page(
                page,
                keyword,
                max_results,
                sort=sort,
                detail_fetch=detail_fetch,
                session_warmup=False,
            )
        finally:
            ctx.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search LinkedIn posts by keyword")
    parser.add_argument("--keyword", required=True, help="Search keyword or hashtag")
    parser.add_argument("--max", type=int, default=10, help="Max posts (default: 10)")
    parser.add_argument(
        "--sort",
        choices=("recent", "relevance"),
        default="recent",
        help="Sort order: recent = date_posted (default), relevance = top match",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--no-detail-fetch",
        action="store_true",
        help="Skip opening each post URL to fill missing body text (faster)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=(
            "After results, print each post's URL plus the first "
            f"{_CLI_PREVIEW_TEXT_CHARS} characters of body (not the full text). "
            "With --json, previews go to stderr so stdout stays valid JSON."
        ),
    )
    args = parser.parse_args()
    log.info(
        "CLI: post list (and --preview snippets) print only after the browser session finishes — "
        "nothing is emitted while scrolling."
    )

    posts = search_posts(
        keyword=args.keyword,
        max_results=args.max,
        sort=args.sort,
        detail_fetch=not args.no_detail_fetch,
    )

    preview_stream = sys.stderr if args.json else sys.stdout

    if args.json:
        print(json.dumps(posts, indent=2, ensure_ascii=False), flush=True)
        if args.preview:
            preview_stream.write("\n--- URL + text preview ---\n")
            _print_post_link_previews(posts, preview_stream)
            preview_stream.flush()
    else:
        print(f"\n{'='*60}", flush=True)
        print(f"Found {len(posts)} posts for '{args.keyword}' (sort={args.sort}):", flush=True)
        print(f"{'='*60}\n", flush=True)
        for i, post in enumerate(posts, 1):
            print(f"[{i}] {post['author'] or '(unknown author)'}", flush=True)
            print(f"    URN  : {post['urn']}", flush=True)
            print(f"    URL  : {post['url']}", flush=True)
            if post.get("text"):
                print(f"    Text : {post['text'][:120]}...", flush=True)
            print(flush=True)
        if args.preview:
            preview_stream.write("--- URL + text preview ---\n")
            _print_post_link_previews(posts, preview_stream)
            preview_stream.flush()
