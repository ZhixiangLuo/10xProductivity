#!/usr/bin/env python3
"""
Playwright UI surface observer.

Opens a headed browser at a URL, attaches listeners to every network
request/response, and lets you drive the page manually. Press Enter in the
terminal (or close the browser) to finish. Writes a structured JSON log and
a human-readable summary you can paste into a connection file.

Usage:
    python3 observe_session.py --url URL [options]

Options:
    --url URL               Starting URL (required)
    --filter-domain DOMAIN  Only log requests matching this domain
                            (default: derived from --url host)
    --out PATH              Output JSON path (default: session_trace.json)
    --load-state PATH       Load a saved Playwright storage_state JSON
                            (cookies + localStorage) — avoids re-login
    --persistent-profile DIR
                            Chromium user-data dir (launch_persistent_context).
                            Mutually exclusive with --load-state.
    --linkedin-10x-profile  Shorthand for 10xProductivity LinkedIn session:
                            ~/.browser_automation/linkedin_profile
    --save-state PATH       After the session ends, save storage_state to
                            this path for future --load-state reuse
    --quit-after-load       Open browser, wait for page load, then stop
                            immediately (use with --save-state to capture auth)
    --no-summary            Skip writing the _summary.md file
    --show-responses        Also log response bodies (truncated to 2 KB)
    --exclude-pattern PAT   Regex pattern to exclude URLs from the log
                            (e.g. 'analytics|metrics|beacon')
    --heartbeat SEC         Print session progress every SEC (default 30; 0=off)
    --autosave-every SEC    Write <out>.autosave.json every SEC during recording (0=off)

Examples:
    # Observe a LinkedIn flow (first-time login)
    python3 observe_session.py --url https://www.linkedin.com/feed/

    # Save auth state after logging in manually
    python3 observe_session.py --url https://www.linkedin.com \
        --save-state linkedin_auth.json --quit-after-load

    # Observe with saved auth, only log linkedin.com requests
    python3 observe_session.py --url https://www.linkedin.com/feed/ \
        --load-state linkedin_auth.json \
        --filter-domain linkedin.com \
        --out linkedin_trace.json

    # Observe Figma, excluding analytics noise
    python3 observe_session.py --url https://www.figma.com \
        --filter-domain figma.com \
        --exclude-pattern 'analytics|sentry|beacon|rum'

    # Scripted / CI / Cursor agent (no TTY): must pass --duration
    python3 observe_session.py --url https://www.linkedin.com/feed/ \
        --filter-domain linkedin.com --duration 600 --out trace.json

    # Same persistent Chromium profile as 10xProductivity linkedin_automation
    # (search_posts.py → ~/.browser_automation/linkedin_profile)
    python3 observe_session.py --url https://www.linkedin.com/feed/ \
        --linkedin-10x-profile --filter-domain linkedin.com --duration 600

Requirements:
    pip install playwright && playwright install chromium
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Installing playwright...")
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# Same path as 10xProductivity/workflows/linkedin_automation/search_posts.py
LINKEDIN_10X_PROFILE_DIR = Path.home() / ".browser_automation" / "linkedin_profile"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(obj, max_chars: int = 500) -> str:
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return s[:max_chars] + "…" if len(s) > max_chars else s


def _payload_keys(body: str | None) -> list[str]:
    if not body:
        return []
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return list(parsed.keys())
    except Exception:
        pass
    return []


def _payload_sample(body: str | None, max_chars: int = 800) -> dict | str | None:
    if not body:
        return None
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return json.loads(_truncate(json.dumps(parsed), max_chars))
    except Exception:
        pass
    return body[:max_chars] if body else None


def _path_only(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query[:80]
    return path


# ---------------------------------------------------------------------------
# Core observer
# ---------------------------------------------------------------------------

def run_observer(
    url: str,
    filter_domain: str | None = None,
    out_path: str = "session_trace.json",
    load_state: str | None = None,
    save_state: str | None = None,
    quit_after_load: bool = False,
    no_summary: bool = False,
    show_responses: bool = False,
    exclude_pattern: str | None = None,
    duration_seconds: int | None = None,
    persistent_profile: str | Path | None = None,
    heartbeat_seconds: float = 30.0,
    autosave_every: float = 0.0,
) -> None:
    if filter_domain is None:
        filter_domain = urlparse(url).hostname or ""
        # strip www. prefix
        if filter_domain.startswith("www."):
            filter_domain = filter_domain[4:]

    exclude_re = re.compile(exclude_pattern, re.IGNORECASE) if exclude_pattern else None

    interactions: list[dict] = []
    wall_start = time.time()

    def _should_log(req_url: str) -> bool:
        if filter_domain and filter_domain not in req_url:
            return False
        if exclude_re and exclude_re.search(req_url):
            return False
        return True

    print(f"\nObserver started")
    print(f"  URL:           {url}")
    print(f"  Filter domain: {filter_domain or '(all)'}")
    print(f"  Output:        {out_path}")
    if persistent_profile:
        print(f"  Persistent profile: {persistent_profile}")
    if load_state:
        print(f"  Loading state: {load_state}")
    if save_state:
        print(f"  Will save state to: {save_state}")
    print()
    print("  The browser will open. Perform your flow manually.")
    if quit_after_load:
        print("  --quit-after-load: will close automatically after page loads.")
    elif duration_seconds is not None and duration_seconds > 0:
        print(f"  --duration {duration_seconds}: will save and exit after that many seconds.")
    else:
        print("  When done, press Enter here (or close the browser).")
    print()

    with sync_playwright() as p:
        browser = None
        ctx = None

        if persistent_profile:
            profile_path = Path(persistent_profile).expanduser().resolve()
            profile_path.mkdir(parents=True, exist_ok=True)
            ctx = p.chromium.launch_persistent_context(
                str(profile_path),
                headless=False,
                args=["--window-size=1280,900", "--window-position=50,50"],
                ignore_https_errors=True,
            )
            page = ctx.new_page()
        else:
            browser = p.chromium.launch(
                headless=False,
                args=["--window-size=1280,900", "--window-position=50,50"],
            )

            ctx_kwargs: dict = {"ignore_https_errors": True}
            if load_state and Path(load_state).exists():
                ctx_kwargs["storage_state"] = load_state

            ctx = browser.new_context(**ctx_kwargs)
            page = ctx.new_page()

        # Monotonic clock origin: set immediately before listeners attach (after context exists).
        mono0 = time.monotonic()

        def _flush_autosave() -> None:
            p = Path(out_path)
            snap = {
                "recorded_at": datetime.now().isoformat(),
                "autosave": True,
                "start_url": url,
                "filter_domain": filter_domain,
                "persistent_profile": str(Path(persistent_profile).expanduser())
                if persistent_profile
                else None,
                "t_ms_basis": "monotonic_ms_since_listeners_attached",
                "interactions": list(interactions),
            }
            auto = p.with_name(p.stem + ".autosave.json")
            auto.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
            print(f"  (autosave → {auto})", flush=True)

        # ---- Attach request listener ----
        def on_request(request):
            if not _should_log(request.url):
                return
            if request.resource_type not in ("fetch", "xhr", "websocket"):
                return
            t_ms = int((time.monotonic() - mono0) * 1000)
            body_str = None
            try:
                body_bytes = request.post_data_buffer
                if body_bytes:
                    body_str = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass

            entry = {
                "t_ms": t_ms,
                "type": "request",
                "method": request.method,
                "url": request.url,
                "path": _path_only(request.url),
                "payload_keys": _payload_keys(body_str),
                "payload_sample": _payload_sample(body_str),
                "resource_type": request.resource_type,
            }
            interactions.append(entry)
            print(f"  [{t_ms:6d}ms] → {request.method:6s} {_path_only(request.url)}")

        def on_response(response):
            if not _should_log(response.url):
                return
            if response.request.resource_type not in ("fetch", "xhr", "websocket"):
                return
            t_ms = int((time.monotonic() - mono0) * 1000)

            body_str = None
            if show_responses:
                try:
                    body_str = response.body().decode("utf-8", errors="replace")
                except Exception:
                    pass

            entry = {
                "t_ms": t_ms,
                "type": "response",
                "status": response.status,
                "method": response.request.method,
                "url": response.url,
                "path": _path_only(response.url),
            }
            if show_responses and body_str:
                entry["response_sample"] = _payload_sample(body_str, max_chars=2000)
                entry["response_keys"] = _payload_keys(body_str)
            interactions.append(entry)
            print(f"  [{t_ms:6d}ms] ← {response.status:3d}    {_path_only(response.url)}")

        # Context-level listeners: capture XHR from every tab in this browser context,
        # not only the first page (users often open posts/profiles in new tabs).
        ctx.on("request", on_request)
        ctx.on("response", on_response)

        # ---- Navigate ----
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeout:
            print("  (page load timed out — continuing anyway)")
        except Exception as e:
            print(f"  (navigation error: {e} — continuing anyway)")

        if quit_after_load:
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeout:
                pass
        elif duration_seconds is not None and duration_seconds > 0:
            print(
                f"\n  Recording… {duration_seconds}s. Use **this** Chromium window only.\n"
                f"  (Main thread pumps Playwright every ≤500ms — timestamps stay honest. Ctrl+C ends early.)\n",
                flush=True,
            )
            deadline = time.monotonic() + float(duration_seconds)
            last_hb = time.monotonic()
            last_save = time.monotonic()
            try:
                while time.monotonic() < deadline:
                    rem = deadline - time.monotonic()
                    # wait_for_timeout yields to the Playwright driver so request/response handlers run.
                    page.wait_for_timeout(int(min(500, max(1, rem * 1000))))
                    now = time.monotonic()
                    if heartbeat_seconds > 0 and now - last_hb >= heartbeat_seconds:
                        last_hb = now
                        elapsed = int(now - mono0)
                        print(
                            f"  … {elapsed}s in session, {len(interactions)} events logged",
                            flush=True,
                        )
                    if autosave_every > 0 and now - last_save >= autosave_every:
                        last_save = now
                        _flush_autosave()
            except KeyboardInterrupt:
                print("\n  (interrupted — saving results)")
        else:
            # Never block the main thread on raw input()/sleep — handlers would not run (false “burst at end”).
            stop = threading.Event()

            def _stdin_waiter() -> None:
                try:
                    sys.stdin.readline()
                except (EOFError, KeyboardInterrupt):
                    pass
                stop.set()

            threading.Thread(target=_stdin_waiter, daemon=True).start()
            print(
                "\n  [Press Enter in this terminal when finished — keep using the Playwright browser window]\n",
                flush=True,
            )
            last_hb = time.monotonic()
            last_save = time.monotonic()
            try:
                while not stop.is_set():
                    page.wait_for_timeout(250)
                    now = time.monotonic()
                    if heartbeat_seconds > 0 and now - last_hb >= heartbeat_seconds:
                        last_hb = now
                        elapsed = int(now - mono0)
                        print(
                            f"  … {elapsed}s in session, {len(interactions)} events logged",
                            flush=True,
                        )
                    if autosave_every > 0 and now - last_save >= autosave_every:
                        last_save = now
                        _flush_autosave()
            except KeyboardInterrupt:
                print("\n  (interrupted — saving results)")

        # ---- Save storage state ----
        if save_state:
            try:
                ctx.storage_state(path=save_state)
                print(f"\n  Storage state saved to: {save_state}")
            except Exception as e:
                print(f"\n  Warning: could not save state: {e}")

        # Close may fail if the user already closed the window — still persist the trace.
        if browser is not None:
            try:
                browser.close()
            except Exception as e:
                print(f"\n  Warning: browser.close(): {e}")
        else:
            try:
                ctx.close()
            except Exception as e:
                print(f"\n  Warning: context.close(): {e}")

    # ---- Write output ----
    out = Path(out_path)
    trace = {
        "recorded_at": datetime.now().isoformat(),
        "start_url": url,
        "filter_domain": filter_domain,
        "persistent_profile": str(Path(persistent_profile).expanduser())
        if persistent_profile
        else None,
        # Wall time from process start (includes browser launch).
        "duration_ms": int((time.time() - wall_start) * 1000),
        "t_ms_basis": "monotonic_ms_since_listeners_attached",
        "interactions": interactions,
    }
    out.write_text(json.dumps(trace, indent=2, ensure_ascii=False))
    print(f"\n  Trace written: {out}  ({len(interactions)} events)")

    # ---- Sanity check: verify t_ms timeline spans the session ----
    # If t_ms values are all crammed into a short window despite a long session,
    # the main thread was blocking (e.g. time.sleep) and network callbacks stacked up.
    req_times = [e["t_ms"] for e in interactions if e.get("type") == "request"]
    if req_times and duration_seconds and duration_seconds > 0:
        span_ms = max(req_times) - min(req_times)
        expected_ms = duration_seconds * 1000
        if span_ms < expected_ms * 0.5:
            print(
                f"\n  ⚠ WARNING: t_ms span ({span_ms/1000:.1f}s) is less than 50% of "
                f"--duration ({duration_seconds}s). Timeline looks collapsed — "
                "were all requests dispatched in a burst at the end?\n"
                "  Likely cause: something blocked the main thread (e.g. time.sleep, "
                "blocking input). Re-capture using only wait_for_timeout().\n"
                "  See: discover-ui-surface/SKILL.md → Timestamps",
                flush=True,
            )

    if not no_summary:
        summary_path = out.with_suffix("").with_name(out.stem + "_summary.md")
        _write_summary(trace, summary_path)
        print(f"  Summary written: {summary_path}")


# ---------------------------------------------------------------------------
# Summary writer
# ---------------------------------------------------------------------------

def _write_summary(trace: dict, path: Path) -> None:
    basis = trace.get("t_ms_basis", "t_ms (unspecified clock)")
    lines = [
        f"# Session trace summary",
        f"",
        f"Recorded: {trace['recorded_at']}",
        f"Start URL: {trace['start_url']}",
        f"Duration (wall, script): {trace['duration_ms']}ms",
        f"`t_ms` basis: `{basis}`",
        f"",
        f"---",
        f"",
        f"## Network events (requests only)",
        f"",
    ]

    requests = [e for e in trace["interactions"] if e["type"] == "request"]
    responses_by_url: dict[str, list[dict]] = {}
    for e in trace["interactions"]:
        if e["type"] == "response":
            responses_by_url.setdefault(e["url"], []).append(e)

    if not requests:
        lines.append("_(no XHR/fetch requests captured)_")
    else:
        # Group consecutive requests that fired close together (within 500ms)
        groups: list[list[dict]] = []
        current_group: list[dict] = []
        prev_t = -1000
        for req in requests:
            if req["t_ms"] - prev_t > 800 and current_group:
                groups.append(current_group)
                current_group = []
            current_group.append(req)
            prev_t = req["t_ms"]
        if current_group:
            groups.append(current_group)

        for group in groups:
            first_t = group[0]["t_ms"]
            last_t = group[-1]["t_ms"]
            if len(group) == 1:
                lines.append(f"### [t={first_t/1000:.1f}s] {group[0]['method']} {group[0]['path']}")
            else:
                lines.append(f"### [t={first_t/1000:.1f}s–{last_t/1000:.1f}s] {len(group)} requests")

            for req in group:
                resp = responses_by_url.get(req["url"], [{}])[-1]
                status = resp.get("status", "?")
                lines.append(f"")
                lines.append(f"**{req['method']} {req['path']}**  `→ {status}`")
                if req.get("payload_keys"):
                    lines.append(f"  payload keys: `{', '.join(req['payload_keys'])}`")
                if req.get("payload_sample"):
                    sample = json.dumps(req["payload_sample"], ensure_ascii=False)
                    lines.append(f"  payload sample: `{sample[:300]}`")
                if resp.get("response_keys"):
                    lines.append(f"  response keys: `{', '.join(resp['response_keys'])}`")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines += [
        "## Notes",
        "",
        "_(Add your annotations here — which action triggered which group)_",
        "",
        "| Step | Action | Network group |",
        "|------|--------|---------------|",
        "| 1 | | [t=Xs] |",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="Starting URL")
    parser.add_argument(
        "--filter-domain",
        default=None,
        help="Only log requests matching this domain substring (default: host from --url)",
    )
    parser.add_argument("--out", default="session_trace.json", help="Output JSON path")
    parser.add_argument("--load-state", default=None, help="Load Playwright storage_state JSON")
    parser.add_argument(
        "--persistent-profile",
        default=None,
        metavar="DIR",
        help="Chromium user-data dir (launch_persistent_context). Same cookies/session as that profile.",
    )
    parser.add_argument(
        "--linkedin-10x-profile",
        action="store_true",
        help=f"Use 10xProductivity LinkedIn profile dir: {LINKEDIN_10X_PROFILE_DIR}",
    )
    parser.add_argument("--save-state", default=None, help="Save storage_state JSON after session")
    parser.add_argument(
        "--quit-after-load",
        action="store_true",
        help="Close browser after initial page load (use with --save-state to capture auth)",
    )
    parser.add_argument("--no-summary", action="store_true", help="Skip writing _summary.md")
    parser.add_argument(
        "--show-responses",
        action="store_true",
        help="Also capture and log response bodies (truncated to 2 KB)",
    )
    parser.add_argument(
        "--exclude-pattern",
        default=None,
        help="Regex to exclude URLs (e.g. 'analytics|beacon|sentry')",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        metavar="SECONDS",
        help="Wall-clock seconds to record, then save and exit (required when stdin is not a TTY)",
    )
    parser.add_argument(
        "--heartbeat",
        type=float,
        default=30.0,
        metavar="SEC",
        help="Print progress every SEC wall time (session age + event count). 0 disables.",
    )
    parser.add_argument(
        "--autosave-every",
        type=float,
        default=0.0,
        metavar="SEC",
        help="Write <out>.autosave.json every SEC during recording. 0 disables.",
    )
    args = parser.parse_args()

    persistent_profile = args.persistent_profile
    if args.linkedin_10x_profile:
        persistent_profile = str(LINKEDIN_10X_PROFILE_DIR)

    if persistent_profile and args.load_state:
        print(
            "observe_session: use either --persistent-profile (or --linkedin-10x-profile) "
            "or --load-state, not both.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not args.quit_after_load:
        if args.duration is None and not sys.stdin.isatty():
            print(
                "observe_session: stdin is not a TTY (no interactive terminal).\n"
                "  Either run this command in Terminal / Cursor’s integrated terminal,\n"
                "  or pass --duration SECONDS (e.g. --duration 600 for 10 minutes).",
                file=sys.stderr,
            )
            sys.exit(2)

    run_observer(
        url=args.url,
        filter_domain=args.filter_domain,
        out_path=args.out,
        load_state=args.load_state,
        save_state=args.save_state,
        quit_after_load=args.quit_after_load,
        no_summary=args.no_summary,
        show_responses=args.show_responses,
        exclude_pattern=args.exclude_pattern,
        duration_seconds=args.duration,
        persistent_profile=persistent_profile,
        heartbeat_seconds=args.heartbeat,
        autosave_every=args.autosave_every,
    )


if __name__ == "__main__":
    main()
