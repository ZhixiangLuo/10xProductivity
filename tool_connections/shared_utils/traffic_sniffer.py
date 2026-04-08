#!/usr/bin/env python3
"""
Generic Playwright traffic sniffer.

Part of the add-new-tool workflow (see add-new-tool.md, Step 0 / Step 2).
Use this when official API docs are missing or incomplete — run it, perform
the target action in the browser, and read the JSONL output to find exact
endpoint URLs, headers, and request payloads to replay via REST.

How it works:
  - Opens a persistent browser profile (reuses saved session — no re-login)
  - Attaches ctx.on("request"/"response") at CONTEXT level before any page
    loads — catches service workers and background frames that page.on misses
  - Navigates to start_url, then waits while you perform actions manually
  - On exit (Ctrl+C or browser close), the JSONL file is complete

Workflow:
  1. Run sso.py for the tool to capture auth tokens (if not already done)
  2. Run this sniffer (with --tool <name> or explicit --profile/--url/--filter)
  3. Perform target actions in the browser (see connection file for suggestions)
  4. Close the browser or Ctrl+C
  5. Inspect the JSONL output — every URL, header, and body is there
  6. Replay interesting calls via REST; document verified ones in
     personal/{tool}/connection-{auth}.md

--tool shortcut:
  If the tool's connection file has a sniffer: block in its frontmatter,
  --tool <name> pre-fills --profile, --url, and --filter automatically.
  Connection file location: personal/{tool}/connection-*.md

  Example frontmatter:
    sniffer:
      profile: ~/.browser_automation/linkedin_profile
      url: https://www.linkedin.com/feed/
      filter: /voyager/api

Usage:
    # Shortcut — reads defaults from personal/linkedin/connection-*.md:
    source .venv/bin/activate
    python3 tool_connections/shared_utils/traffic_sniffer.py --tool linkedin

    # Explicit — full control:
    python3 tool_connections/shared_utils/traffic_sniffer.py \\
        --profile ~/.browser_automation/linkedin_profile \\
        --url https://www.linkedin.com/feed/ \\
        --filter /voyager/api \\
        --output /tmp/linkedin_traffic.jsonl

    # Quick analysis after capture:
    python3 -c "
    import json
    for e in (json.loads(l) for l in open('/tmp/linkedin_traffic.jsonl')):
        if e['type'] == 'request':
            print(e['method'], e['url'])
            if e.get('post_data'): print(' body:', e['post_data'][:200])
    "

Usage (as a library):
    from tool_connections.shared_utils.traffic_sniffer import sniff

    sniff(
        profile_dir=Path.home() / ".browser_automation" / "linkedin_profile",
        start_url="https://www.linkedin.com/feed/",
        filters=["/voyager/api"],
        output_path=Path("/tmp/linkedin_traffic.jsonl"),
    )

Output format (one JSON object per line):
    {
        "ts": "2026-04-08T19:05:00.123Z",
        "type": "request" | "response",
        "method": "GET" | "POST" | ...,
        "url": "https://...",
        "status": 200,                    // response only
        "request_headers": {...},
        "response_headers": {...},        // response only
        "post_data": "...",               // request only, if present
        "response_body": "...",           // response only, truncated at 8 KB
    }
"""

import argparse
import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parents[2]))
from tool_connections.shared_utils.browser import sync_playwright, BROWSER_AUTOMATION_DIR

_REPO_ROOT = Path(__file__).parents[2]


def _load_tool_config(tool_name: str) -> dict:
    """
    Read sniffer defaults from personal/{tool}/connection-*.md frontmatter.

    Returns a dict with keys: profile, url, filters (list).
    Raises FileNotFoundError if no connection file found for the tool.
    """
    tool_dir = _REPO_ROOT / "personal" / tool_name
    candidates = list(tool_dir.glob("connection-*.md"))
    if not candidates:
        raise FileNotFoundError(
            f"No connection file found at personal/{tool_name}/connection-*.md\n"
            f"Run setup.md to connect {tool_name} first."
        )
    conn_file = candidates[0]
    text = conn_file.read_text()

    # Extract YAML frontmatter between --- delimiters
    fm_match = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"No frontmatter found in {conn_file}")
    fm = fm_match.group(1)

    # Parse sniffer: block (simple key: value, no full YAML parser needed)
    sniffer_match = re.search(r"^sniffer:\s*\n((?:  .+\n)*)", fm, re.MULTILINE)
    if not sniffer_match:
        raise ValueError(
            f"No sniffer: block in {conn_file} frontmatter.\n"
            "Add a sniffer: block with profile:, url:, and filter: fields."
        )
    sniffer_block = sniffer_match.group(1)
    cfg: dict = {}
    for line in sniffer_block.splitlines():
        m = re.match(r"  (\w+):\s*(.+)", line)
        if m:
            cfg[m.group(1)] = m.group(2).strip()

    profile_str = cfg.get("profile", "")
    # Expand ~ in profile path
    profile = Path(profile_str.replace("~", str(Path.home())))
    url = cfg.get("url", "")
    filters_raw = cfg.get("filter", "")
    filters = [f.strip() for f in filters_raw.split(",") if f.strip()] if filters_raw else []

    if not profile_str or not url:
        raise ValueError(f"sniffer: block in {conn_file} must have both profile: and url: fields.")

    return {"profile": profile, "url": url, "filters": filters, "tool": tool_name, "conn_file": conn_file}


_RESPONSE_BODY_LIMIT = 8 * 1024  # 8 KB — enough to see payload shapes


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _matches(url: str, filters: list[str]) -> bool:
    """Return True if url contains at least one of the filter substrings (or no filters set)."""
    if not filters:
        return True
    return any(f in url for f in filters)


def sniff(
    profile_dir: Path,
    start_url: str,
    filters: Optional[list[str]] = None,
    output_path: Optional[Path] = None,
    capture_bodies: bool = True,
    headless: bool = False,
) -> list[dict]:
    """
    Open the persistent profile, navigate to start_url, and record matching traffic.

    Blocks until the browser window is closed by the user.

    Args:
        profile_dir:    Persistent Chromium profile directory.
        start_url:      URL to open on launch.
        filters:        List of URL substrings to match. Empty = capture everything.
        output_path:    If set, append captured entries as JSONL to this file.
        capture_bodies: Whether to capture response bodies (adds latency on large pages).
        headless:       Run without a visible window (useful for automated tests).

    Returns:
        List of captured event dicts.
    """
    filters = filters or []
    captured: list[dict] = []
    lock = threading.Lock()

    profile_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale SingletonLock that prevents re-launch after a crash
    stale_lock = profile_dir / "SingletonLock"
    if stale_lock.exists():
        stale_lock.unlink()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            args=["--window-size=1280,900", "--window-position=100,50"],
        )

        # ── Context-level listener — attached before any page loads ──────────
        # Using ctx.on (not page.on) catches service workers and background
        # frames that page-level listeners miss entirely.

        def on_request(request):
            if not _matches(request.url, filters):
                return
            entry = {
                "ts": _now_iso(),
                "type": "request",
                "method": request.method,
                "url": request.url,
                "request_headers": dict(request.headers),
            }
            post = request.post_data
            if post:
                entry["post_data"] = post[:_RESPONSE_BODY_LIMIT]
            with lock:
                captured.append(entry)
                _maybe_write(entry, output_path)
                _print_entry(entry)

        def on_response(response):
            if not _matches(response.url, filters):
                return
            entry = {
                "ts": _now_iso(),
                "type": "response",
                "method": response.request.method,
                "url": response.url,
                "status": response.status,
                "request_headers": dict(response.request.headers),
                "response_headers": dict(response.headers),
            }
            if capture_bodies:
                try:
                    body = response.body()
                    entry["response_body"] = body[:_RESPONSE_BODY_LIMIT].decode("utf-8", errors="replace")
                except Exception:
                    pass
            with lock:
                captured.append(entry)
                _maybe_write(entry, output_path)
                _print_entry(entry)

        ctx.on("request", on_request)
        ctx.on("response", on_response)
        # ─────────────────────────────────────────────────────────────────────

        page = ctx.new_page()
        page.goto(start_url, wait_until="domcontentloaded", timeout=30_000)

        print(f"\n  Sniffer active — performing actions in the browser window.")
        print(f"  Filtering: {filters if filters else '(all requests)'}")
        if output_path:
            print(f"  Output:    {output_path}")
        print("  Press Ctrl+C or close the browser window to stop.\n")

        # Block until the browser window is closed
        try:
            while ctx.pages:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

        ctx.close()

    print(f"\n  Captured {len(captured)} events.")
    return captured


def _maybe_write(entry: dict, output_path: Optional[Path]) -> None:
    if output_path is None:
        return
    with output_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _print_entry(entry: dict) -> None:
    if entry["type"] == "request":
        print(f"  → {entry['method']:6s} {entry['url'][:120]}")
    else:
        status = entry.get("status", "?")
        symbol = "✓" if str(status).startswith("2") else "✗"
        print(f"  {symbol} {status} {entry['method']:6s} {entry['url'][:110]}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tool", default=None,
                        help="Tool name (e.g. 'linkedin') — reads profile/url/filter from "
                             "personal/{tool}/connection-*.md frontmatter. "
                             "Overridden by explicit --profile/--url/--filter if provided.")
    parser.add_argument("--profile", type=Path, default=None,
                        help="Path to persistent Chromium profile directory")
    parser.add_argument("--url", default=None,
                        help="Start URL to open in the browser")
    parser.add_argument("--filter", dest="filters", action="append", default=[],
                        metavar="SUBSTRING",
                        help="URL substring to capture (repeatable; default: everything)")
    parser.add_argument("--output", type=Path, default=None,
                        help="JSONL output file (appended, created if missing)")
    parser.add_argument("--no-bodies", action="store_true",
                        help="Skip capturing response bodies (faster for high-traffic pages)")
    parser.add_argument("--headless", action="store_true",
                        help="Run without a visible browser window")
    args = parser.parse_args()

    # Resolve defaults from tool config, then let explicit args override
    profile = args.profile
    url = args.url
    filters = args.filters  # explicit --filter flags

    if args.tool:
        try:
            cfg = _load_tool_config(args.tool)
        except (FileNotFoundError, ValueError) as e:
            print(f"  ✗ {e}", file=sys.stderr)
            sys.exit(1)
        if profile is None:
            profile = cfg["profile"]
        if url is None:
            url = cfg["url"]
        if not filters:
            filters = cfg["filters"]
        print(f"  Tool:    {args.tool}  ({cfg['conn_file'].relative_to(_REPO_ROOT)})")

    if profile is None or url is None:
        parser.error("--profile and --url are required unless --tool is specified.")

    sniff(
        profile_dir=profile,
        start_url=url,
        filters=filters,
        output_path=args.output,
        capture_bodies=not args.no_bodies,
        headless=args.headless,
    )


if __name__ == "__main__":
    _main()
