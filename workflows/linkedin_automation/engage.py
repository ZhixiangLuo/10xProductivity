#!/usr/bin/env python3
"""10x Engage — find the next relevant LinkedIn post and optionally post a comment.

Daemon mode (recommended — browser stays open between fetch and post):

  Start the daemon once (keeps browser alive):
    python workflows/linkedin_automation/engage.py --serve

  Fetch (agent reviews, then calls --post-comment):
    python workflows/linkedin_automation/engage.py --keyword "Agentic AI"

  Post (after human approves — reuses the running browser):
    python workflows/linkedin_automation/engage.py \\
        --post-url "https://www.linkedin.com/feed/update/urn:li:activity:.../" \\
        --post-comment "Your approved comment text here."

  Stop the daemon:
    python workflows/linkedin_automation/engage.py --stop

Output (stdout, JSON):
    {"urn": "...", "url": "...", "author": "...", "author_url": "...", "text": "..."}
    {"posted": true, "code": 0}

Exit codes:
    0  — success
    1  — no relevant post found for this keyword (try another)
    2  — post failed (comment not posted)

Legacy single-invocation mode (no daemon) still works when --serve is not running.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import tempfile
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_AUTO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(_AUTO))

from fetch_next_post import open_session, close_session, fetch_next_post  # noqa: E402
from post_comment import submit_comment_on_page  # noqa: E402

MAX_TRIES = 8

# Daemon coordination files (per-user temp dir so no permissions issues)
_TMPDIR = Path(tempfile.gettempdir()) / "10x_engage"
_SOCK_FILE = _TMPDIR / "engage.sock"
_PID_FILE = _TMPDIR / "engage.pid"


# ---------------------------------------------------------------------------
# Relevance filter
# ---------------------------------------------------------------------------

def _is_relevant(text: str) -> bool:
    """Heuristic filter — must touch an AI/coding signal, no strong off-topic signals."""
    t = text.lower()
    off_topic = [
        "governance act", "e-governance", "legislation",
        "government agenc", "public service", "grief", "condolence",
        "election", "political", "obituary", "passed away", "rest in peace",
        "senate", "congress", "ministry", "department of",
    ]
    if any(s in t for s in off_topic):
        return False
    signals = [
        "agent", "cursor", "claude", "codex", "windsurf", "copilot",
        "rag", "llm", "ai tool", "agentic", "mcp", "tool_connection",
        "vibe cod", "coding agent", "autonomous agent", "multi-agent",
        "ai workflow", "ai automation", "ai productivity",
    ]
    return any(s in t for s in signals) and len(text) > 80


# ---------------------------------------------------------------------------
# Daemon — server side
# ---------------------------------------------------------------------------

def _handle_client(conn: socket.socket, session: dict, cursor_state: dict) -> None:
    """Handle one JSON-RPC style request from a client connection."""
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        req = json.loads(data.decode())
        method = req.get("method")

        if method == "ping":
            conn.sendall((json.dumps({"ok": True}) + "\n").encode())

        elif method == "stop":
            conn.sendall((json.dumps({"ok": True, "msg": "stopping"}) + "\n").encode())
            conn.close()
            # Signal the main daemon thread to exit.
            os.kill(os.getpid(), signal.SIGTERM)

        elif method == "fetch":
            keyword = req.get("keyword", "")
            skip = set(req.get("skip_urns", []))
            sort = req.get("sort", "recent")

            # Reset cursor when keyword changes.
            if cursor_state.get("keyword") != keyword:
                cursor_state.clear()
                cursor_state["keyword"] = keyword
                cursor_state["cursor"] = None

            tries = 0
            result = None
            while tries < MAX_TRIES:
                post, new_cursor = fetch_next_post(
                    keyword,
                    cursor=cursor_state.get("cursor"),
                    session=session,
                    sort=sort,
                )
                cursor_state["cursor"] = new_cursor

                if post is None:
                    result = {"error": "keyword_exhausted", "keyword": keyword}
                    break

                if post.get("urn") in skip:
                    tries += 1
                    continue

                if not _is_relevant(post.get("text") or ""):
                    tries += 1
                    continue

                result = post
                break
            else:
                result = {"error": "no_relevant_post", "keyword": keyword}

            conn.sendall((json.dumps(result, ensure_ascii=False) + "\n").encode())

        elif method == "post":
            url = req.get("url", "")
            text = req.get("text", "")
            code = submit_comment_on_page(session["_page"], url, text)
            conn.sendall((json.dumps({"posted": code == 0, "code": code}) + "\n").encode())

        else:
            conn.sendall((json.dumps({"error": "unknown_method", "method": method}) + "\n").encode())

    except Exception as exc:
        try:
            conn.sendall((json.dumps({"error": str(exc)}) + "\n").encode())
        except Exception:
            pass
    finally:
        conn.close()


def _serve() -> int:
    """Run the daemon: open browser, listen on Unix socket, handle requests serially."""
    _TMPDIR.mkdir(parents=True, exist_ok=True)

    # Remove stale socket.
    if _SOCK_FILE.exists():
        _SOCK_FILE.unlink()

    session = open_session()
    cursor_state: dict = {}

    def _shutdown(sig, frame):
        print("Daemon shutting down…", file=sys.stderr, flush=True)
        close_session(session)
        try:
            _SOCK_FILE.unlink(missing_ok=True)
            _PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    _PID_FILE.write_text(str(os.getpid()))

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(_SOCK_FILE))
    srv.listen(4)

    print(json.dumps({"daemon": "ready", "sock": str(_SOCK_FILE), "pid": os.getpid()}), flush=True)

    try:
        while True:
            conn, _ = srv.accept()
            # Requests are serialised (one at a time) to keep Playwright thread-safe.
            _handle_client(conn, session, cursor_state)
    finally:
        close_session(session)
        try:
            _SOCK_FILE.unlink(missing_ok=True)
            _PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return 0


# ---------------------------------------------------------------------------
# Client — talk to the running daemon
# ---------------------------------------------------------------------------

def _daemon_running() -> bool:
    if not _SOCK_FILE.exists():
        return False
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(2)
        c.connect(str(_SOCK_FILE))
        c.sendall((json.dumps({"method": "ping"}) + "\n").encode())
        c.recv(256)
        c.close()
        return True
    except Exception:
        return False


def _rpc(req: dict) -> dict:
    """Send one request to the daemon and return the parsed response."""
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    c.settimeout(120)
    c.connect(str(_SOCK_FILE))
    try:
        c.sendall((json.dumps(req) + "\n").encode())
        data = b""
        while True:
            chunk = c.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        return json.loads(data.decode())
    finally:
        c.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Find next relevant LinkedIn post for engagement.")

    # Daemon control
    ap.add_argument("--serve", action="store_true", help="Start the browser daemon (keeps browser open)")
    ap.add_argument("--stop", action="store_true", help="Stop the running daemon")

    # Fetch args
    ap.add_argument("--keyword", default="", help="LinkedIn content search keyword")
    ap.add_argument("--skip-urns", default="", help="Comma-separated URNs to skip")
    ap.add_argument("--sort", choices=("recent", "relevance"), default="recent")

    # Post args
    ap.add_argument("--post-url", default="", help="Post URL to comment on")
    ap.add_argument("--post-comment", default="", metavar="TEXT", help="Comment text to post")

    args = ap.parse_args()

    # ---- daemon start ----
    if args.serve:
        return _serve()

    # ---- daemon stop ----
    if args.stop:
        if not _daemon_running():
            print(json.dumps({"ok": False, "msg": "no daemon running"}), flush=True)
            return 1
        result = _rpc({"method": "stop"})
        print(json.dumps(result), flush=True)
        return 0

    # ---- post via daemon ----
    if args.post_url and args.post_comment:
        if _daemon_running():
            result = _rpc({"method": "post", "url": args.post_url, "text": args.post_comment})
            print(json.dumps(result), flush=True)
            return 0 if result.get("posted") else 2
        # Fallback: no daemon — open a fresh browser just to post.
        session = open_session()
        try:
            code = submit_comment_on_page(session["_page"], args.post_url, args.post_comment)
            print(json.dumps({"posted": code == 0, "code": code}), flush=True)
            return 0 if code == 0 else 2
        finally:
            close_session(session)

    # ---- fetch via daemon ----
    if args.keyword:
        skip = [u.strip() for u in args.skip_urns.split(",") if u.strip()]
        if _daemon_running():
            result = _rpc({
                "method": "fetch",
                "keyword": args.keyword,
                "skip_urns": skip,
                "sort": args.sort,
            })
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0 if "urn" in result else 1
        # Fallback: no daemon — open browser, fetch, close (legacy behaviour).
        session = open_session()
        try:
            skip_set = set(skip)
            cursor = None
            tries = 0
            while tries < MAX_TRIES:
                post, cursor = fetch_next_post(args.keyword, cursor=cursor, session=session, sort=args.sort)
                if post is None:
                    print(json.dumps({"error": "keyword_exhausted", "keyword": args.keyword}), flush=True)
                    return 1
                if post.get("urn") in skip_set:
                    tries += 1
                    continue
                if not _is_relevant(post.get("text") or ""):
                    tries += 1
                    continue
                print(json.dumps(post, ensure_ascii=False), flush=True)
                return 0
            print(json.dumps({"error": "no_relevant_post", "keyword": args.keyword}), flush=True)
            return 1
        finally:
            close_session(session)

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
