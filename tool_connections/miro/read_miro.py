#!/usr/bin/env python3
"""
Miro read helper — internal web API (miro.com/api/v1) using MIRO_TOKEN session cookie.

Capture token:
  python3 tool_connections/shared_utils/playwright_sso.py --miro-only

Usage (repo root):
  python3 tool_connections/miro/read_miro.py --check
  python3 tool_connections/miro/read_miro.py --recent
  python3 tool_connections/miro/read_miro.py --org
  python3 tool_connections/miro/read_miro.py --me
  python3 tool_connections/miro/read_miro.py --board BOARD_ID
  python3 tool_connections/miro/read_miro.py --json --recent
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://miro.com/api/v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def miro_get(path: str, token: str) -> tuple[int, bytes]:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Cookie": f"token={token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, context=ssl_ctx(), timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _org_id(me: dict) -> str | None:
    if not me:
        return None
    oid = me.get("lastKnownOrgId")
    if oid:
        return str(oid)
    org = me.get("organization")
    if isinstance(org, dict) and org.get("id"):
        return str(org["id"])
    return None


def main() -> None:
    p = argparse.ArgumentParser(description="Read Miro data via session token (internal API).")
    p.add_argument("--check", action="store_true", help="Verify MIRO_TOKEN (GET /users/me/)")
    p.add_argument("--me", action="store_true", help="Print current user JSON")
    p.add_argument("--recent", action="store_true", help="List recent boards")
    p.add_argument("--org", action="store_true", help="List boards for org (from /users/me/)")
    p.add_argument("--board", metavar="ID", help="Fetch one board by id (URL-encoded automatically)")
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    args = p.parse_args()

    if not any([args.check, args.me, args.recent, args.org, args.board]):
        args.recent = True

    env = load_env(ENV_FILE)
    token = (env.get("MIRO_TOKEN") or "").strip()
    if not token:
        print(
            "Missing MIRO_TOKEN — run: python3 tool_connections/shared_utils/playwright_sso.py --miro-only",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.check:
        code, body = miro_get("/users/me/", token)
        if code == 200:
            print("OK — session valid")
            sys.exit(0)
        print(body.decode(errors="replace")[:1200], file=sys.stderr)
        sys.exit(1)

    if args.me:
        code, body = miro_get("/users/me/", token)
        text = body.decode(errors="replace")
        if args.json or code != 200:
            print(text)
            sys.exit(0 if code == 200 else 1)
        print(json.dumps(json.loads(body), indent=2))
        sys.exit(0 if code == 200 else 1)

    if args.board:
        bid = urllib.parse.quote(args.board, safe="")
        code, body = miro_get(f"/boards/{bid}", token)
        print(body.decode(errors="replace"))
        sys.exit(0 if code == 200 else 1)

    if args.recent:
        code, body = miro_get("/recent-boards", token)
        if code != 200:
            print(body.decode(errors="replace")[:2000], file=sys.stderr)
            sys.exit(1)
        data = json.loads(body)
        if args.json:
            print(json.dumps(data, indent=2))
            return
        boards = data if isinstance(data, list) else data.get("data") or data.get("boards") or []
        if not boards:
            print("No recent boards returned.")
            return
        for b in boards:
            if not isinstance(b, dict):
                continue
            print(f"{b.get('id', '?')}\t{b.get('title', b.get('name', '?'))}")
        return

    if args.org:
        code, body = miro_get("/users/me/", token)
        if code != 200:
            print(body.decode(errors="replace")[:2000], file=sys.stderr)
            sys.exit(1)
        me = json.loads(body)
        oid = _org_id(me)
        if oid:
            code, body = miro_get(f"/organizations/{oid}/boards/", token)
            if code != 200:
                print(body.decode(errors="replace")[:2000], file=sys.stderr)
                sys.exit(1)
            data = json.loads(body)
            if args.json:
                print(json.dumps(data, indent=2))
                return
            boards = data.get("data") if isinstance(data, dict) else []
        else:
            # Some accounts omit lastKnownOrgId; boards may still appear on /users/me/.
            boards_obj = me.get("boards")
            boards = (
                boards_obj.get("data", [])
                if isinstance(boards_obj, dict)
                else []
            )
            if not boards:
                print(json.dumps(me, indent=2))
                print(
                    "No organization id and no boards on /users/me/ — try --recent.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if args.json:
                print(json.dumps({"source": "users/me/boards", "data": boards}, indent=2))
                return
            print(
                "# Note: no lastKnownOrgId — listing boards embedded in /users/me/ (may be a subset).",
                file=sys.stderr,
            )
        if not boards:
            print("No boards in response.")
            return
        for b in boards:
            if isinstance(b, dict):
                print(f"{b.get('id', '?')}\t{b.get('title', b.get('name', '?'))}")


if __name__ == "__main__":
    main()
