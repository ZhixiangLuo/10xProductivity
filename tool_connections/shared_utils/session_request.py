#!/usr/bin/env python3
"""
One-shot HTTP client that reuses a Playwright persistent browser profile.

Opens the tool's saved Chromium profile, optionally warms up the session,
then performs GET/POST/PUT/PATCH/DELETE via context.request (cookies attached
automatically). Callable from CLI or imported by other Python scripts.

Usage:
    python3 tool_connections/shared_utils/session_request.py \\
        --profile ~/.browser_automation/linkedin_profile \\
        --warmup-url https://www.linkedin.com/feed/ \\
        --method GET \\
        --url https://www.linkedin.com/voyager/api/me \\
        --header "X-RestLi-Protocol-Version: 2.0.0" \\
        --csrf-from-cookie JSESSIONID \\
        --json

    # When the tool connection file has a sniffer: block:
    python3 tool_connections/shared_utils/session_request.py \\
        --tool google-ai-mode --method GET --url '...' --json

Library:
    from tool_connections.shared_utils.session_request import session_request

    result = session_request(
        profile_dir=Path.home() / ".browser_automation" / "linkedin_profile",
        method="GET",
        url="https://www.linkedin.com/voyager/api/me",
        warmup_url="https://www.linkedin.com/feed/",
        csrf_cookie="JSESSIONID",
    )
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parents[2]))
from tool_connections.shared_utils.browser import BROWSER_AUTOMATION_DIR, sync_playwright
from tool_connections.shared_utils.traffic_sniffer import _load_tool_config

_REPO_ROOT = Path(__file__).parents[2]
_BODY_LIMIT = 1 * 1024 * 1024  # 1 MB cap for CLI/library responses
_LOGIN_HINTS = ("login", "signin", "sign-in", "accounts.google.com", "auth.")


def _log(msg: str, *, json_mode: bool) -> None:
    if json_mode:
        print(msg, file=sys.stderr)
    else:
        print(msg)


def _parse_header(raw: str) -> tuple[str, str]:
    if ":" not in raw:
        raise ValueError(f"Invalid header (expected KEY:VALUE): {raw!r}")
    key, value = raw.split(":", 1)
    return key.strip(), value.strip()


def _looks_like_login(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in _LOGIN_HINTS)


def _cookie_value(ctx, name: str, url: str) -> str | None:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for cookie in ctx.cookies([origin]):
        if cookie.get("name") == name:
            return cookie.get("value", "").strip('"')
    for cookie in ctx.cookies():
        if cookie.get("name") == name:
            return cookie.get("value", "").strip('"')
    return None


def _build_headers(
    ctx,
    url: str,
    headers: dict[str, str] | None,
    csrf_cookie: str | None,
) -> dict[str, str]:
    out = dict(headers or {})
    if csrf_cookie:
        token = _cookie_value(ctx, csrf_cookie, url)
        if token:
            out.setdefault("Csrf-Token", token)
    return out


def _serialize_body(body: str | bytes | dict | None) -> tuple[str | bytes | None, dict[str, str]]:
    extra_headers: dict[str, str] = {}
    if body is None:
        return None, extra_headers
    if isinstance(body, dict):
        extra_headers["Content-Type"] = "application/json"
        return json.dumps(body), extra_headers
    return body, extra_headers


def _shape_response(
    status: int,
    resp_headers: dict[str, str],
    body_bytes: bytes,
) -> dict[str, Any]:
    truncated = len(body_bytes) > _BODY_LIMIT
    if truncated:
        body_bytes = body_bytes[:_BODY_LIMIT]

    result: dict[str, Any] = {
        "ok": 200 <= status < 400,
        "status": status,
        "headers": resp_headers,
    }

    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        result["binary"] = True
        result["body"] = base64.b64encode(body_bytes).decode("ascii")
        if truncated:
            result["truncated"] = True
        return result

    result["body"] = text
    if truncated:
        result["truncated"] = True

    try:
        result["json"] = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    return result


def _request_via_context(
    ctx,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: str | bytes | None,
    timeout_ms: int,
) -> dict[str, Any]:
    req = ctx.request
    method_upper = method.upper()
    kwargs: dict[str, Any] = {"headers": headers, "timeout": timeout_ms}

    if payload is not None:
        if isinstance(payload, (dict, list)):
            kwargs["data"] = json.dumps(payload)
        else:
            kwargs["data"] = payload

    dispatch = {
        "GET": req.get,
        "POST": req.post,
        "PUT": req.put,
        "PATCH": req.patch,
        "DELETE": req.delete,
    }
    if method_upper not in dispatch:
        raise ValueError(f"Unsupported method: {method}")

    if method_upper == "GET":
        kwargs.pop("data", None)

    response = dispatch[method_upper](url, **kwargs)
    try:
        body_bytes = response.body()
    except Exception:
        body_bytes = b""
    return _shape_response(response.status, dict(response.headers), body_bytes)


def _request_via_page_fetch(
    page,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: str | bytes | None,
) -> dict[str, Any]:
    body_str: str | None
    if payload is None:
        body_str = None
    elif isinstance(payload, bytes):
        body_str = payload.decode("utf-8", errors="replace")
    else:
        body_str = payload

    result = page.evaluate(
        """async ({ url, method, headers, body }) => {
            const opts = { method, headers: headers || {}, credentials: 'include' };
            if (body != null) opts.body = body;
            const r = await fetch(url, opts);
            const text = await r.text();
            const out = { status: r.status, headers: {}, body: text };
            r.headers.forEach((v, k) => { out.headers[k] = v; });
            return out;
        }""",
        {"url": url, "method": method.upper(), "headers": headers, "body": body_str},
    )
    body_bytes = (result.get("body") or "").encode("utf-8", errors="replace")
    return _shape_response(int(result.get("status", 0)), dict(result.get("headers") or {}), body_bytes)


def session_request(
    *,
    profile_dir: Path,
    method: str,
    url: str,
    warmup_url: str | None = None,
    headers: dict[str, str] | None = None,
    body: str | bytes | dict | None = None,
    csrf_cookie: str | None = None,
    timeout_ms: int = 30_000,
    headless: bool = True,
    via_page_fetch: bool = False,
    json_mode: bool = False,
) -> dict[str, Any]:
    """
    Perform one HTTP call using a persistent Playwright profile.

    Returns {ok, status, headers, body, json?, binary?, truncated?, error?}.
    """
    profile_dir = Path(profile_dir).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    stale_lock = profile_dir / "SingletonLock"
    if stale_lock.exists():
        stale_lock.unlink()

    payload, body_headers = _serialize_body(body)
    ctx = None

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(profile_dir),
                channel="chrome",
                headless=headless,
                ignore_https_errors=True,
                args=["--window-size=1280,900", "--window-position=100,50"],
            )

            page = ctx.new_page()
            if warmup_url:
                _log(f"  Warmup: {warmup_url}", json_mode=json_mode)
                page.goto(warmup_url, wait_until="domcontentloaded", timeout=timeout_ms)
                if _looks_like_login(page.url):
                    return {
                        "ok": False,
                        "error": f"Session not logged in — redirected to {page.url}",
                    }

            merged_headers = _build_headers(ctx, url, headers, csrf_cookie)
            merged_headers.update(body_headers)

            if via_page_fetch:
                _log("  Request via page.fetch()", json_mode=json_mode)
                result = _request_via_page_fetch(page, method, url, merged_headers, payload)
            else:
                _log(f"  {method.upper()} {url}", json_mode=json_mode)
                result = _request_via_context(ctx, method, url, merged_headers, payload, timeout_ms)

            ctx.close()
            ctx = None
            return result

    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def _resolve_profile_and_warmup(
    tool: str | None,
    profile: Path | None,
    warmup_url: str | None,
) -> tuple[Path, str | None]:
    if tool:
        cfg = _load_tool_config(tool)
        if profile is None:
            profile = cfg["profile"]
        if warmup_url is None:
            warmup_url = cfg["url"]
    if profile is None:
        raise ValueError("--profile is required unless --tool provides one via sniffer: config")
    return profile, warmup_url


def _main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tool", default=None, help="Tool name — reads profile/warmup from connection sniffer: block")
    parser.add_argument("--profile", type=Path, default=None, help="Persistent Chromium profile directory")
    parser.add_argument("--warmup-url", default=None, help="Navigate here before the API call")
    parser.add_argument("--method", required=True, help="GET, POST, PUT, PATCH, or DELETE")
    parser.add_argument("--url", required=True, help="Full request URL")
    parser.add_argument("--header", dest="headers", action="append", default=[], metavar="KEY:VALUE",
                        help="Extra header (repeatable)")
    parser.add_argument("--body", default=None, help="Request body string")
    parser.add_argument("--body-file", type=Path, default=None, help="Read request body from file")
    parser.add_argument("--csrf-from-cookie", default=None, metavar="NAME",
                        help="Set Csrf-Token header from cookie value (e.g. JSESSIONID)")
    parser.add_argument("--timeout-ms", type=int, default=30_000, help="Request timeout in ms")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--via-page-fetch", action="store_true",
                        help="Use page.evaluate(fetch) instead of context.request")
    parser.add_argument("--json", action="store_true", help="Print only JSON result to stdout")
    args = parser.parse_args()

    try:
        profile, warmup_url = _resolve_profile_and_warmup(args.tool, args.profile, args.warmup_url)
    except (FileNotFoundError, ValueError) as exc:
        print(f"  ✗ {exc}", file=sys.stderr)
        sys.exit(1)

    headers = dict(_parse_header(h) for h in args.headers)

    body: str | bytes | dict | None = None
    if args.body_file is not None:
        raw = args.body_file.read_text()
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
    elif args.body is not None:
        try:
            body = json.loads(args.body)
        except json.JSONDecodeError:
            body = args.body

    if args.tool and not args.json:
        print(f"  Tool: {args.tool}")
    if not args.json:
        print(f"  Profile: {profile}")

    result = session_request(
        profile_dir=profile,
        method=args.method,
        url=args.url,
        warmup_url=warmup_url,
        headers=headers or None,
        body=body,
        csrf_cookie=args.csrf_from_cookie,
        timeout_ms=args.timeout_ms,
        headless=not args.headed,
        via_page_fetch=args.via_page_fetch,
        json_mode=args.json,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        status = result.get("status", "?")
        print(f"\n  → HTTP {status}  ok={result.get('ok')}")
        if result.get("json") is not None:
            print(json.dumps(result["json"], indent=2, ensure_ascii=False)[:4000])
        elif result.get("body"):
            print(result["body"][:2000])
        if result.get("error"):
            print(f"  Error: {result['error']}", file=sys.stderr)

    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    _main()
