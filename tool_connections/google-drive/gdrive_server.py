#!/usr/bin/env python3
"""
Google Drive Playwright daemon — keeps one browser open across all agent calls.

The daemon holds a single Playwright browser session and serves requests over a
Unix socket. GDrive connects to it instead of launching its own browser, so the
SSO auth happens once and the browser stays open until you explicitly stop it.

Usage:
    # Start (auto-called by GDrive on first use — you don't need to run this manually)
    python3 gdrive_server.py start

    # Stop
    python3 gdrive_server.py stop

    # Status
    python3 gdrive_server.py status

Protocol (newline-delimited JSON over Unix socket):
    Request:  {"action": "search"|"read"|"ping", ...params}
    Response: {"ok": true, "result": ...} | {"ok": false, "error": "..."}
"""

import json, os, queue, re, signal, socket, subprocess, sys, time, traceback
import urllib.request
from pathlib import Path
from threading import Thread, Event

AUTH_FILE    = Path.home() / ".browser_automation" / "gdrive_auth.json"
PROFILE_DIR  = Path.home() / ".browser_automation" / "gdrive_cdp_profile"
SOCKET_PATH  = Path.home() / ".browser_automation" / "gdrive_server.sock"
PID_FILE     = Path.home() / ".browser_automation" / "gdrive_server.pid"
LOG_FILE     = Path.home() / ".browser_automation" / "gdrive_server.log"
CDP_PORT     = int(os.environ.get("GDRIVE_CDP_PORT", "9223"))
CHROME_APP   = "/Applications/Google Chrome.app"
DRIVE_URL    = "https://drive.google.com/drive/my-drive"

_ID_PATTERNS = [
    r"/document/d/([a-zA-Z0-9_-]{20,})",
    r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})",
    r"/presentation/d/([a-zA-Z0-9_-]{20,})",
    r"/file/d/([a-zA-Z0-9_-]{20,})",
    r"/folders/([a-zA-Z0-9_-]{20,})",
]
_TYPE_BY_PATH = {
    "/document/d/": "document",
    "/spreadsheets/d/": "spreadsheet",
    "/presentation/d/": "presentation",
    "/folders/": "folder",
}
_NAME_SUFFIXES = {
    "Google Docs": "document",
    "Google Sheets": "spreadsheet",
    "Google Slides": "presentation",
    "Google Forms": "form",
    "Shared folder": "folder",
    "Folder": "folder",
}
_EXPORT_URLS = {
    "document":     "https://docs.google.com/document/d/{id}/export?format=txt",
    "spreadsheet":  "https://docs.google.com/spreadsheets/d/{id}/export?format=csv",
    "presentation": "https://docs.google.com/presentation/d/{id}/export/txt",
}
_EXTRACT_JS = """() => {
    const files = []; const seen = new Set();
    document.querySelectorAll('[data-id]').forEach(el => {
        const dataId = el.getAttribute('data-id') || '';
        const name   = el.querySelector('[data-tooltip]')?.getAttribute('data-tooltip')
                    || el.getAttribute('data-tooltip') || '';
        const links  = Array.from(el.querySelectorAll('a[href]'))
                           .map(a => a.getAttribute('href')).filter(Boolean);
        files.push({ dataId, name: name.trim(), links });
    });
    return files;
}"""


def _extract_id(link):
    for pat in _ID_PATTERNS:
        m = re.search(pat, link)
        if m:
            return m.group(1)
    return None


def _parse_raw(raw):
    result = []; seen = set()
    for f in raw:
        best_id = f["dataId"]; best_link = ""
        for link in f["links"]:
            fid = _extract_id(link)
            if fid and len(fid) > len(best_id):
                best_id = fid; best_link = link
        if not best_id or len(best_id) < 15 or best_id in seen:
            continue
        seen.add(best_id)
        ftype = next((t for k, t in _TYPE_BY_PATH.items() if k in best_link), "file")
        name = f["name"]
        for suffix, t in _NAME_SUFFIXES.items():
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
                if ftype == "file": ftype = t
                break
        result.append({"id": best_id, "name": name, "type": ftype})
    return result


def _cdp_is_listening() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{CDP_PORT}/json/version",
            timeout=2,
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _launch_cdp_chrome() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    # Remove stale locks for the dedicated automation profile only. Never touch
    # the user's normal Chrome profile because that risks corruption.
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try:
            (PROFILE_DIR / name).unlink()
        except FileNotFoundError:
            pass

    subprocess.Popen(
        [
            "open", "-na", CHROME_APP, "--args",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            "--window-size=1400,900",
            DRIVE_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(40):
        time.sleep(0.25)
        if _cdp_is_listening():
            return
    raise RuntimeError(f"Chrome CDP did not start on port {CDP_PORT}")


# ── Daemon ────────────────────────────────────────────────────────────────────

class GDriveServer:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._log = open(LOG_FILE, "a", buffering=1)
        # All Playwright calls must happen on the main thread.
        # Network threads put (req, result_queue) here; main loop drains it.
        self._work_queue: queue.Queue = queue.Queue()

    def log(self, msg):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._log.write(f"[{ts}] {msg}\n")

    def start_browser(self):
        from playwright.sync_api import sync_playwright
        self.log("Starting browser via system Chrome CDP...")
        self._pw = sync_playwright().start()

        # Google rejects Playwright-launched Chromium with "This browser or app
        # may not be secure." Launch a separate normal Chrome instance instead
        # and attach through the Chrome DevTools Protocol.
        if not _cdp_is_listening():
            _launch_cdp_chrome()

        self._browser = self._pw.chromium.connect_over_cdp(
            f"http://127.0.0.1:{CDP_PORT}"
        )
        # When the user closes the Chrome window (right-click → Exit, ⌘Q, etc.),
        # send SIGTERM to ourselves so the shutdown handler runs cleanly.
        self._browser.on("disconnected", lambda: os.kill(os.getpid(), signal.SIGTERM))
        self._ctx = self._browser.contexts[0]
        self._ctx.set_default_timeout(30_000)
        self._ctx.set_default_navigation_timeout(45_000)
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

        try:
            self._page.goto(DRIVE_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception:
            pass
        time.sleep(2)
        if "accounts.google.com" in self._page.url:
            self.log("Google login required in the visible Chrome window.")
            try:
                self._page.wait_for_url("https://drive.google.com/**", timeout=180_000)
            except Exception as e:
                raise RuntimeError(
                    "Google Drive login is required. Complete sign-in in the visible "
                    "Chrome window opened for Drive, then retry the command."
                ) from e
        self.log("Browser ready.")

    def handle(self, req: dict) -> dict:
        from playwright.sync_api import TimeoutError as PWTimeout
        import urllib.parse
        action = req.get("action")
        try:
            if action == "ping":
                return {"ok": True, "result": "pong"}

            elif action == "search":
                query = req["query"]
                try:
                    self._page.goto(
                        f"https://drive.google.com/drive/search?q={urllib.parse.quote(query)}",
                        wait_until="networkidle", timeout=30_000)
                except PWTimeout:
                    pass
                time.sleep(1)
                files = _parse_raw(self._page.evaluate(_EXTRACT_JS))
                return {"ok": True, "result": files}

            elif action == "read":
                file_id = req["file_id"]
                file_type = req["file_type"]
                url = _EXPORT_URLS.get(file_type, "").format(id=file_id)
                if not url:
                    return {"ok": False, "error": f"Unsupported type: {file_type}"}
                # Use a fresh page so the main page stays on search results
                dl_page = self._ctx.new_page()
                try:
                    with dl_page.expect_download(timeout=25_000) as dl_info:
                        try:
                            dl_page.goto(url, wait_until="commit", timeout=10_000)
                        except Exception:
                            pass
                    content = Path(dl_info.value.path()).read_text(errors="replace")
                finally:
                    dl_page.close()
                return {"ok": True, "result": content}

            else:
                return {"ok": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            self.log(f"Error handling {action}: {e}\n{traceback.format_exc()}")
            return {"ok": False, "error": str(e)}

    def serve(self, stop_event: Event):
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(SOCKET_PATH))
        server.listen(5)
        server.settimeout(0.1)  # non-blocking accept so main thread can drain work queue
        self.log(f"Listening on {SOCKET_PATH}")

        def handle_client(conn):
            """Run in a thread: read request, post to work queue, wait for result."""
            try:
                data = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    if data.endswith(b"\n"):
                        break
                req = json.loads(data.decode())
                result_q: queue.Queue = queue.Queue()
                self._work_queue.put((req, result_q))
                resp = result_q.get(timeout=120)
                conn.sendall((json.dumps(resp) + "\n").encode())
            except Exception as e:
                self.log(f"Client error: {e}")
                try:
                    conn.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
                except Exception:
                    pass
            finally:
                conn.close()

        try:
            while not stop_event.is_set():
                # Accept new connections (non-blocking)
                try:
                    conn, _ = server.accept()
                    Thread(target=handle_client, args=(conn,), daemon=True).start()
                except OSError:
                    pass  # timeout or interrupt — no new connection

                # Drain work queue on main thread (Playwright must run here)
                try:
                    while True:
                        req, result_q = self._work_queue.get_nowait()
                        resp = self.handle(req)
                        result_q.put(resp)
                except queue.Empty:
                    pass
        finally:
            server.close()
            if SOCKET_PATH.exists():
                SOCKET_PATH.unlink()
            # Always close browser on the way out so Chromium never lingers
            self.log("Closing browser.")
            try:
                if self._browser:
                    self._browser.close()
            except Exception:
                pass
            try:
                if self._pw:
                    self._pw.stop()
            except Exception:
                pass


def run_daemon():
    server = GDriveServer()
    server.start_browser()
    PID_FILE.write_text(str(os.getpid()))

    stop_event = Event()

    def shutdown(sig, frame):
        server.log(f"Received signal {sig} — shutting down.")
        stop_event.set()  # signal the serve() loop to exit cleanly

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server.serve(stop_event)
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


# ── Client ────────────────────────────────────────────────────────────────────

def _send(req: dict, timeout: float = 60.0) -> dict:
    """Send a request to the daemon and return the response."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(str(SOCKET_PATH))
    sock.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
        if data.endswith(b"\n"):
            break
    sock.close()
    return json.loads(data.decode())


def is_running() -> bool:
    """Return True if the daemon is running and responsive."""
    if not SOCKET_PATH.exists():
        return False
    try:
        resp = _send({"action": "ping"}, timeout=3.0)
        return resp.get("result") == "pong"
    except Exception:
        return False


def ensure_running():
    """Start the daemon if not already running. Blocks until ready."""
    if is_running():
        return
    import subprocess
    subprocess.Popen(
        [sys.executable, __file__, "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Wait up to 60s for it to be ready
    for _ in range(120):
        time.sleep(0.5)
        if is_running():
            return
    raise RuntimeError(
        "gdrive_server failed to start. Check log: " + str(LOG_FILE)
    )


def search(query: str) -> list[dict]:
    ensure_running()
    resp = _send({"action": "search", "query": query}, timeout=60.0)
    if not resp["ok"]:
        raise RuntimeError(resp["error"])
    return resp["result"]


def read(file_id: str, file_type: str) -> str:
    ensure_running()
    resp = _send({"action": "read", "file_id": file_id, "file_type": file_type}, timeout=30.0)
    if not resp["ok"]:
        raise RuntimeError(resp["error"])
    return resp["result"]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "start":
        run_daemon()

    elif cmd == "stop":
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped (pid {pid})")
        else:
            print("Not running")

    elif cmd == "status":
        if is_running():
            pid = PID_FILE.read_text().strip() if PID_FILE.exists() else "?"
            print(f"Running (pid {pid})")
        else:
            print("Not running")

    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        ensure_running()
        results = search(query)
        print(f"{len(results)} results:")
        for f in results:
            print(f"  [{f['type']:<14}] {f['name']}")

    elif cmd == "read":
        file_id, file_type = sys.argv[2], sys.argv[3]
        ensure_running()
        content = read(file_id, file_type)
        print(content)
