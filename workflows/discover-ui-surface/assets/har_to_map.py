#!/usr/bin/env python3
"""
HAR to interaction map converter.

Takes a HAR file exported from Chrome DevTools (Network tab → ⬇ Save all as HAR)
and extracts only the meaningful XHR/fetch requests — filtering out analytics pings,
CDN assets, beacons, and other noise — then produces:

  1. A Markdown interaction map table ready to paste into a connection file
  2. A JSON file with the filtered+annotated entries for further processing

Usage:
    python3 har_to_map.py INPUT.har [options]

Options:
    --domain DOMAIN         Only include requests to this domain
                            (default: auto-detected from most common host)
    --out-md PATH           Output Markdown path (default: {input}_map.md)
    --out-json PATH         Output JSON path (default: {input}_filtered.json)
    --exclude PAT           Additional regex pattern to exclude URLs
                            (stacked with built-in noise filter)
    --min-size BYTES        Skip responses smaller than this (default: 50)
                            Filters out 1x1 pixel beacons, empty ACKs, etc.
    --show-response-keys    Include response body keys in output
    --max-entries N         Limit to first N entries (default: unlimited)

Examples:
    # Basic usage — auto-detect domain
    python3 har_to_map.py linkedin.har

    # Filter to specific domain
    python3 har_to_map.py figma.har --domain figma.com

    # Exclude specific patterns
    python3 har_to_map.py notion.har --exclude 'heartbeat|health|ping'

    # With response keys (useful for mapping response shapes)
    python3 har_to_map.py linkedin.har --show-response-keys

Requirements:
    No external dependencies — uses stdlib only.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, parse_qs


# ---------------------------------------------------------------------------
# Built-in noise patterns — requests that are never useful for automation
# ---------------------------------------------------------------------------

NOISE_PATTERNS = re.compile(
    r"""
    # Analytics / telemetry
    analytics | telemetry | beacon | pixel | tracking | collect |
    metrics | rum | apm | newrelic | datadog | segment\.com |
    amplitude | mixpanel | heap | hotjar | fullstory | logrocket |
    sentry | bugsnag | rollbar | raygun |

    # Ads
    doubleclick | googlesyndication | adsystem | adserver | pagead |

    # Font / icon CDN
    fonts\.googleapis | fonts\.gstatic | fontawesome |

    # Browser internals
    favicon\.ico | manifest\.json | service.?worker |

    # Short-lived status pings
    /ping$ | /health$ | /heartbeat$ | /alive$ | /status$
    """,
    re.IGNORECASE | re.VERBOSE,
)

USEFUL_CONTENT_TYPES = {
    "application/json",
    "application/x-www-form-urlencoded",
    "text/plain",
    "multipart/form-data",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_noise(entry: dict, domain_filter: str, extra_exclude: re.Pattern | None) -> bool:
    url = entry.get("request", {}).get("url", "")
    if NOISE_PATTERNS.search(url):
        return True
    if extra_exclude and extra_exclude.search(url):
        return True
    if domain_filter and domain_filter not in url:
        return True
    resource_type = entry.get("_resourceType", "")
    if resource_type in ("image", "font", "stylesheet", "media", "manifest", "other"):
        return True
    method = entry.get("request", {}).get("method", "GET")
    # Skip GET requests with no query string and tiny responses — likely prefetch/preload
    if method == "GET":
        resp_size = entry.get("response", {}).get("content", {}).get("size", 0)
        if resp_size < 50:
            return True
    return False


def _get_mime(entry: dict) -> str:
    return entry.get("response", {}).get("content", {}).get("mimeType", "").split(";")[0].strip()


def _request_body(entry: dict) -> str | None:
    post_data = entry.get("request", {}).get("postData", {})
    if not post_data:
        return None
    text = post_data.get("text")
    if text:
        return text
    params = post_data.get("params")
    if params:
        return "&".join(f"{p['name']}={p.get('value','')}" for p in params)
    return None


def _parse_body(body: str | None) -> tuple[list[str], dict | str | None]:
    if not body:
        return [], None
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return list(parsed.keys()), parsed
        return [], parsed
    except Exception:
        pass
    # Try form-encoded
    try:
        pairs = [p.split("=", 1) for p in body.split("&") if "=" in p]
        keys = [k for k, _ in pairs]
        return keys, dict(pairs)
    except Exception:
        pass
    return [], body[:500]


def _response_body(entry: dict, show_response_keys: bool) -> tuple[list[str], dict | None]:
    if not show_response_keys:
        return [], None
    text = entry.get("response", {}).get("content", {}).get("text")
    if not text:
        return [], None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return list(parsed.keys()), parsed
        if isinstance(parsed, list) and parsed:
            first = parsed[0]
            if isinstance(first, dict):
                return [f"[{len(parsed)}][0].{k}" for k in first.keys()], None
    except Exception:
        pass
    return [], None


def _path_only(url: str, include_query: bool = True) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if include_query and parsed.query:
        # Truncate very long query strings
        q = parsed.query[:80]
        path += "?" + q
    return path


def _auto_detect_domain(entries: list[dict]) -> str:
    hosts: list[str] = []
    for e in entries:
        url = e.get("request", {}).get("url", "")
        try:
            host = urlparse(url).hostname or ""
            if host.startswith("www."):
                host = host[4:]
            hosts.append(host)
        except Exception:
            pass
    if not hosts:
        return ""
    counter = Counter(hosts)
    return counter.most_common(1)[0][0]


def _truncate_sample(obj, max_chars: int = 300) -> str:
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return s[:max_chars] + "…" if len(s) > max_chars else s


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

def process_har(
    har_path: Path,
    domain_filter: str | None = None,
    out_md: Path | None = None,
    out_json: Path | None = None,
    extra_exclude: str | None = None,
    min_size: int = 50,
    show_response_keys: bool = False,
    max_entries: int | None = None,
) -> None:
    raw = json.loads(har_path.read_text(encoding="utf-8"))
    entries = raw.get("log", {}).get("entries", [])
    print(f"Loaded {len(entries)} entries from {har_path.name}")

    if not domain_filter:
        domain_filter = _auto_detect_domain(entries)
        print(f"Auto-detected domain filter: {domain_filter}")

    exclude_re = re.compile(extra_exclude, re.IGNORECASE) if extra_exclude else None

    filtered: list[dict] = []
    skipped = 0
    for entry in entries:
        if _is_noise(entry, domain_filter, exclude_re):
            skipped += 1
            continue
        resp_size = entry.get("response", {}).get("content", {}).get("size", 0)
        if resp_size < min_size:
            skipped += 1
            continue
        filtered.append(entry)

    print(f"Filtered: {len(filtered)} entries kept, {skipped} skipped as noise")

    if max_entries:
        filtered = filtered[:max_entries]
        print(f"Capped to first {max_entries} entries")

    # ---- Build structured records ----
    records: list[dict] = []
    for entry in filtered:
        req = entry.get("request", {})
        resp = entry.get("response", {})
        url = req.get("url", "")
        method = req.get("method", "")
        status = resp.get("status", 0)
        mime = _get_mime(entry)
        body_str = _request_body(entry)
        payload_keys, payload_sample = _parse_body(body_str)
        resp_keys, resp_sample = _response_body(entry, show_response_keys)
        start_time = entry.get("startedDateTime", "")
        time_ms = entry.get("time", 0)

        record = {
            "started": start_time,
            "duration_ms": round(time_ms),
            "method": method,
            "url": url,
            "path": _path_only(url),
            "status": status,
            "mime": mime,
            "payload_keys": payload_keys,
            "payload_sample": payload_sample if payload_sample and payload_keys else None,
            "response_keys": resp_keys,
            "response_sample": resp_sample if resp_sample and resp_keys else None,
        }
        records.append(record)

    # ---- Write JSON ----
    if out_json is None:
        out_json = har_path.with_name(har_path.stem + "_filtered.json")
    out_json.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"Filtered JSON written: {out_json}")

    # ---- Write Markdown ----
    if out_md is None:
        out_md = har_path.with_name(har_path.stem + "_map.md")
    _write_markdown(records, out_md, har_path.name, show_response_keys)
    print(f"Interaction map written: {out_md}")


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_markdown(records: list[dict], path: Path, source: str, show_response_keys: bool) -> None:
    lines = [
        f"# Interaction map",
        f"",
        f"Source: `{source}`  |  Entries: {len(records)}",
        f"",
        "---",
        "",
        "## Captured requests",
        "",
    ]

    if not records:
        lines.append("_(no entries after filtering)_")
    else:
        # Table header
        headers = ["#", "Method", "Path", "Status", "Payload keys"]
        if show_response_keys:
            headers.append("Response keys")
        headers.append("Notes")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for i, r in enumerate(records, 1):
            payload_keys_str = ", ".join(r["payload_keys"]) if r["payload_keys"] else "—"
            row = [
                str(i),
                f"`{r['method']}`",
                f"`{r['path']}`",
                str(r["status"]),
                payload_keys_str,
            ]
            if show_response_keys:
                row.append(", ".join(r["response_keys"]) if r["response_keys"] else "—")
            row.append("")  # Notes column — user fills in
            lines.append("| " + " | ".join(row) + " |")

        lines += [
            "",
            "---",
            "",
            "## Payload details",
            "",
        ]

        for i, r in enumerate(records, 1):
            if not r.get("payload_sample") and not r.get("response_sample"):
                continue
            lines.append(f"### {i}. `{r['method']} {r['path']}`")
            lines.append("")
            if r.get("payload_sample"):
                lines.append("**Request payload:**")
                lines.append("```json")
                lines.append(_truncate_sample(r["payload_sample"], max_chars=800))
                lines.append("```")
                lines.append("")
            if r.get("response_sample"):
                lines.append("**Response shape:**")
                lines.append("```json")
                lines.append(_truncate_sample(r["response_sample"], max_chars=800))
                lines.append("```")
                lines.append("")

    lines += [
        "---",
        "",
        "## Interaction map — copy into connection file",
        "",
        "| Step | Action | Element / selector | Network call | Status |",
        "|------|--------|-------------------|--------------|--------|",
        "| 1 | _(describe what you did)_ | _(selector)_ | `METHOD /path` | ✓ |",
        "",
        "### Key payload shapes",
        "",
        "_(paste the relevant payload shapes from the Payload details section above)_",
        "",
        "### Selector durability notes",
        "",
        "_(document which selectors are ARIA/text-based vs generated class names)_",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("har", help="Path to .har file")
    parser.add_argument("--domain", default=None, help="Domain filter (auto-detected if omitted)")
    parser.add_argument("--out-md", default=None, help="Output Markdown path")
    parser.add_argument("--out-json", default=None, help="Output JSON path")
    parser.add_argument("--exclude", default=None, help="Additional regex to exclude URLs")
    parser.add_argument("--min-size", type=int, default=50, help="Min response size in bytes (default 50)")
    parser.add_argument("--show-response-keys", action="store_true", help="Include response body keys")
    parser.add_argument("--max-entries", type=int, default=None, help="Cap to first N entries")
    args = parser.parse_args()

    har_path = Path(args.har)
    if not har_path.exists():
        print(f"Error: {har_path} not found", file=sys.stderr)
        sys.exit(1)

    process_har(
        har_path=har_path,
        domain_filter=args.domain,
        out_md=Path(args.out_md) if args.out_md else None,
        out_json=Path(args.out_json) if args.out_json else None,
        extra_exclude=args.exclude,
        min_size=args.min_size,
        show_response_keys=args.show_response_keys,
        max_entries=args.max_entries,
    )


if __name__ == "__main__":
    main()
