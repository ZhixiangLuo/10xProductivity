"""
Google Drive helper — Playwright storage_state auth (no OAuth app needed).

Usage:
    from google_drive import GDrive

    with GDrive() as drive:
        files   = drive.search("coe")
        mine    = drive.search("owner:me")
        listing = drive.list_my_drive()
        content = drive.read(file_id, file_type)   # doc/sheet/slides → text/csv
        drive.write_document_append(file_id, "new text")  # Docs only (append at end)
        drive.write_presentation_append(file_id, "note text")  # Slides (notes or canvas)

Auth:
    Run once to capture session:
        python3 playwright_sso.py --gdrive-only
    Session saved to ~/.browser_automation/gdrive_auth.json (days/weeks lifetime).
    Re-run --gdrive-only if Drive redirects to sign-in.

Reuse the same browser session (optional):
    GDRIVE_CDP_URL=http://127.0.0.1:9222
        Connect to Chrome you already opened with a debugging port, e.g.:
        /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
          --remote-debugging-port=9222 --user-data-dir=\"$HOME/.chrome-gdrive-debug\"
        Then every script run uses that same logged-in browser (no new Chromium).
    GDRIVE_USE_PERSISTENT_PROFILE=1
        Use a single on-disk profile under ~/.browser_automation/gdrive_chromium_profile/
        so repeated runs share cookies without starting a fresh incognito-like context.
        Cookies from gdrive_auth.json are applied via add_cookies (Playwright
        persistent contexts do not all support storage_state on launch).

Notes:
    - headless=False required — SSO needs it, and headed mode is 5× faster than
      headless for Drive (hardware-accelerated JS rendering vs software-only)
    - data-id in Drive DOM is truncated; full 44-char IDs come from href
    - read() uses browser download interception (temp path, NOT ~/Downloads)
    - Google Docs use canvas rendering — DOM text extraction not possible;
      read() calls the export URL which Playwright intercepts as a download

Verified: 2026-03-14, jeffrey.luo@workday.com
"""

import os, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

sys.path.insert(0, str(Path(__file__).parents[1]))
from shared_utils.browser import BROWSER_AUTOMATION_DIR

AUTH_FILE = BROWSER_AUTOMATION_DIR / "gdrive_auth.json"

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


def _extract_id(link: str) -> str | None:
    for pat in _ID_PATTERNS:
        m = re.search(pat, link)
        if m:
            return m.group(1)
    return None


def _slides_click_main_slide(page) -> None:
    """
    Focus the main slide editing surface. Google's class names change; we try
    several selectors, then the largest wide canvas (skipping narrow left filmstrip),
    then a viewport click in the usual slide area.
    """
    page.wait_for_url(re.compile(r".*/presentation/d/[^/]+/edit.*"), timeout=90_000)
    time.sleep(2.0)

    for sel in (
        ".punch-viewport",
        "[class*='punch-viewport']",
        "#workspace",
        "[data-log-pane='body']",
        "div[role='application'] canvas",
    ):
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=10_000)
            box = loc.bounding_box()
            if box and box["width"] >= 80 and box["height"] >= 80:
                loc.click(
                    position={
                        "x": min(400, max(40, box["width"] / 2)),
                        "y": min(300, max(40, box["height"] / 2)),
                    },
                    timeout=15_000,
                )
                return
        except Exception:
            continue

    pt = page.evaluate(
        """() => {
            const canvases = Array.from(document.querySelectorAll('canvas'));
            let best = null;
            let area = 0;
            for (const c of canvases) {
                const r = c.getBoundingClientRect();
                if (r.width < 180 || r.height < 120) continue;
                if (r.left < 100) continue;
                const a = r.width * r.height;
                if (a > area) {
                    area = a;
                    best = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                }
            }
            return best;
        }"""
    )
    if pt and isinstance(pt, dict) and pt.get("x") is not None and pt.get("y") is not None:
        page.mouse.click(float(pt["x"]), float(pt["y"]))
        return

    vs = page.viewport_size
    if vs:
        page.mouse.click(vs["width"] * 0.56, vs["height"] * 0.40)
    else:
        page.mouse.click(720, 380)


def _parse_raw(raw: list[dict]) -> list[dict]:
    result = []
    seen: set[str] = set()
    for f in raw:
        best_id = f["dataId"]
        best_link = ""
        for link in f["links"]:
            fid = _extract_id(link)
            if fid and len(fid) > len(best_id):
                best_id = fid
                best_link = link
        if not best_id or len(best_id) < 15 or best_id in seen:
            continue
        seen.add(best_id)
        ftype = next((t for k, t in _TYPE_BY_PATH.items() if k in best_link), "file")
        name = f["name"]
        for suffix, t in _NAME_SUFFIXES.items():
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                if ftype == "file":
                    ftype = t
                break
        result.append({"id": best_id, "name": name, "type": ftype})
    return result


class GDrive:
    """
    Context manager for Google Drive operations.

    with GDrive() as drive:
        files = drive.search("coe")
        content = drive.read(files[0]["id"], files[0]["type"])
    """

    def __init__(self, auth_file: Path | str | None = None):
        self._auth_file = Path(auth_file) if auth_file else AUTH_FILE
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._mode = "default"

    def __enter__(self) -> "GDrive":
        self._pw = sync_playwright().start()
        cdp_url = os.environ.get("GDRIVE_CDP_URL", "").strip()
        use_persistent = os.environ.get("GDRIVE_USE_PERSISTENT_PROFILE", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        if cdp_url:
            self._mode = "cdp"
            self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
            if not self._browser.contexts:
                self._pw.stop()
                self._pw = None
                raise RuntimeError(
                    "GDRIVE_CDP_URL is set but the browser reports no contexts. "
                    "Start Chrome with --remote-debugging-port=9222 and keep a window open."
                )
            self._ctx = self._browser.contexts[0]
            # New tab — do not hijack whatever the user already had open.
            self._page = self._ctx.new_page()
        elif use_persistent:
            import json

            self._mode = "persistent"
            profile_dir = BROWSER_AUTOMATION_DIR / "gdrive_chromium_profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            self._ctx = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--window-size=1400,900"],
                ignore_https_errors=True,
                accept_downloads=True,
                viewport={"width": 1400, "height": 900},
            )
            self._browser = None
            if self._auth_file.exists():
                try:
                    data = json.loads(self._auth_file.read_text())
                    cookies = data.get("cookies")
                    if isinstance(cookies, list) and cookies:
                        self._ctx.add_cookies(cookies)
                except Exception:
                    pass
            self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        else:
            self._mode = "default"
            self._browser = self._pw.chromium.launch(
                headless=False,
                args=["--window-size=1400,900"],
            )
            self._ctx = self._browser.new_context(
                storage_state=str(self._auth_file),
                ignore_https_errors=True,
                accept_downloads=True,
            )
            self._page = self._ctx.new_page()

        try:
            self._page.goto(
                "https://drive.google.com/drive/my-drive",
                wait_until="networkidle",
                timeout=45_000,
            )
        except PlaywrightTimeout:
            pass
        time.sleep(1)
        if "accounts.google.com" in self._page.url:
            hint = ""
            if self._mode != "cdp":
                hint = (
                    " Or start Chrome with --remote-debugging-port=9222, sign in once, "
                    "and set GDRIVE_CDP_URL=http://127.0.0.1:9222 to reuse that window."
                )
            raise RuntimeError(
                "Google Drive session expired. Re-run: "
                "python3 playwright_sso.py --gdrive-only" + hint
            )
        return self

    def __exit__(self, *_):
        if self._mode == "persistent":
            if self._ctx:
                self._ctx.close()
        elif self._browser:
            self._browser.close()
        self._browser = None
        self._ctx = None
        self._page = None
        if self._pw:
            self._pw.stop()
            self._pw = None

    # ── Core operations ─────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict]:
        """
        Search Drive. Returns list of {id, name, type}.

        query: any text, or Drive operators:
            owner:me            — files you own (guaranteed exportable)
            "exact phrase"      — exact match
            owner:me coe        — combine
        """
        import urllib.parse
        try:
            self._page.goto(
                f"https://drive.google.com/drive/search?q={urllib.parse.quote(query)}",
                wait_until="networkidle",
                timeout=30_000,
            )
        except PlaywrightTimeout:
            pass
        time.sleep(1)
        return _parse_raw(self._page.evaluate(_EXTRACT_JS))

    def list_my_drive(self) -> list[dict]:
        """List files/folders in My Drive root."""
        try:
            self._page.goto(
                "https://drive.google.com/drive/my-drive",
                wait_until="networkidle",
                timeout=30_000,
            )
        except PlaywrightTimeout:
            pass
        time.sleep(1)
        return _parse_raw(self._page.evaluate(_EXTRACT_JS))

    def list_folder(self, folder_id: str) -> list[dict]:
        """List contents of a specific folder by ID."""
        try:
            self._page.goto(
                f"https://drive.google.com/drive/folders/{folder_id}",
                wait_until="networkidle",
                timeout=30_000,
            )
        except PlaywrightTimeout:
            pass
        time.sleep(1)
        return _parse_raw(self._page.evaluate(_EXTRACT_JS))

    def read(self, file_id: str, file_type: str) -> str:
        """
        Export a Google file and return its text content.

        file_type: 'document' → plain text
                   'spreadsheet' → CSV
                   'presentation' → text (slide titles + speaker notes)

        Note: Google Docs use canvas rendering — DOM text extraction is not
        possible. This triggers an export download that Playwright intercepts
        to a temp path (/var/folders/.../playwright-artifacts-...).
        ~/Downloads is NOT touched.

        Only works for files you can open. Use search("owner:me") for owned files.
        """
        url = _EXPORT_URLS.get(file_type, "").format(id=file_id)
        if not url:
            raise ValueError(f"Unsupported file type for export: {file_type!r}. "
                             f"Supported: {list(_EXPORT_URLS)}")

        with self._page.expect_download(timeout=25_000) as dl_info:
            try:
                self._page.goto(url, wait_until="commit", timeout=10_000)
            except Exception:
                pass  # "Download is starting" is expected

        download = dl_info.value
        return Path(download.path()).read_text(errors="replace")

    def write_document_append(self, doc_id: str, text: str, *, settle_s: float = 3.0) -> None:
        """
        Append text to the end of a Google Doc (opens the editor, focuses canvas,
        jumps to end, types). Docs auto-save; no separate save call.

        Uses the same Playwright session as read(). You need edit access to the doc.

        Note: This is best-effort UI automation — complex docs, comments-only mode,
        or Google UI changes can make focus unreliable. Prefer short, plain-text
        appends.
        """
        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        try:
            self._page.goto(url, wait_until="networkidle", timeout=45_000)
        except PlaywrightTimeout:
            pass
        time.sleep(settle_s)

        if "accounts.google.com" in self._page.url:
            raise RuntimeError(
                "Google session expired while opening the doc. Re-run: "
                "python3 playwright_sso.py --gdrive-only"
            )

        editor = self._page.locator(".kix-appview-editor").first
        editor.wait_for(state="visible", timeout=30_000)
        editor.click(position={"x": 320, "y": 320})
        time.sleep(0.4)

        if sys.platform == "darwin":
            self._page.keyboard.press("Meta+ArrowDown")
        else:
            self._page.keyboard.press("Control+End")
        time.sleep(0.35)
        self._page.keyboard.press("Enter")
        time.sleep(0.2)

        for i, line in enumerate(text.split("\n")):
            if i:
                self._page.keyboard.press("Enter")
                time.sleep(0.05)
            self._page.keyboard.type(line, delay=20)
        time.sleep(2.0)

    def write_presentation_append(
        self,
        presentation_id: str,
        text: str,
        *,
        settle_s: float = 4.0,
        target: str = "notes",
    ) -> None:
        """
        Append plain text to a Google Slides deck.

        target:
            'notes' — focus the speaker-notes editor (bottom of the editor UI) when
                possible; matches what read(..., 'presentation') exports as text.
            'slide' — click the main slide viewport and type (best on an empty area
                or when a text box is already selected).

        Best-effort UI automation; Slides layout and Google DOM changes can break it.
        """
        if target not in ("notes", "slide"):
            raise ValueError("target must be 'notes' or 'slide'")

        url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        try:
            self._page.goto(url, wait_until="networkidle", timeout=60_000)
        except PlaywrightTimeout:
            pass
        time.sleep(settle_s)

        if "accounts.google.com" in self._page.url:
            raise RuntimeError(
                "Google session expired while opening the deck. Re-run: "
                "python3 playwright_sso.py --gdrive-only"
            )

        used_notes = False
        slide_canvas = False
        if target == "notes":
            # Prefer a contenteditable in the lower part of the window (speaker notes).
            focused = self._page.evaluate(
                """() => {
                    const vh = window.innerHeight;
                    const eds = Array.from(
                        document.querySelectorAll('[contenteditable="true"]')
                    );
                    let best = null;
                    let bestTop = -1;
                    for (const e of eds) {
                        const r = e.getBoundingClientRect();
                        if (r.height < 24 || r.width < 80) continue;
                        if (r.top < vh * 0.45) continue;
                        if (r.top >= bestTop) {
                            bestTop = r.top;
                            best = e;
                        }
                    }
                    if (best) {
                        best.focus();
                        best.scrollIntoView({ block: 'nearest' });
                        return true;
                    }
                    return false;
                }"""
            )
            if focused:
                used_notes = True
            else:
                target = "slide"

        if target == "slide":
            _slides_click_main_slide(self._page)
            slide_canvas = True
            time.sleep(0.6)

        if used_notes:
            self._page.keyboard.press("End")
            time.sleep(0.2)
            self._page.keyboard.press("Enter")
            time.sleep(0.15)
        elif slide_canvas:
            # Do not use Meta+ArrowDown here — it can change slide selection instead
            # of inserting text. Click already focuses the canvas / a text box.
            time.sleep(0.15)
        else:
            if sys.platform == "darwin":
                self._page.keyboard.press("Meta+ArrowDown")
            else:
                self._page.keyboard.press("Control+End")
            time.sleep(0.25)
            self._page.keyboard.press("Enter")
            time.sleep(0.15)

        for i, line in enumerate(text.split("\n")):
            if i:
                self._page.keyboard.press("Enter")
                time.sleep(0.05)
            self._page.keyboard.type(line, delay=22)
        time.sleep(2.0)

    def write_sheet_cell(self, sheet_id: str, row: int, col: int, value: str,
                         gid: int = 0) -> None:
        """
        Write a value to a single Google Sheets cell by 1-indexed row/col.

        Uses keyboard navigation from A1 — reliable across all sheet layouts.
        Auto-saves (Google Sheets saves on every keystroke).

        Args:
            sheet_id: Spreadsheet ID (from URL: /spreadsheets/d/<ID>/edit)
            row:      1-indexed row number
            col:      1-indexed column number (1=A, 2=B, ...)
            value:    String value to write
            gid:      Sheet tab ID (default 0 = first tab)

        Example:
            drive.write_sheet_cell("1R1U8QywU4...", row=10, col=2, "alice@example.com")
            # Writes to B10
        """
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={gid}"
        try:
            self._page.goto(url, wait_until="networkidle", timeout=30_000)
        except PlaywrightTimeout:
            pass
        time.sleep(2)

        # Go to A1
        self._page.keyboard.press("Control+Home")
        time.sleep(0.3)

        # Navigate to target row (down row-1 times)
        for _ in range(row - 1):
            self._page.keyboard.press("ArrowDown")
            time.sleep(0.04)

        # Navigate to target column (right col-1 times)
        for _ in range(col - 1):
            self._page.keyboard.press("ArrowRight")
            time.sleep(0.04)

        # Clear existing content, then type new value
        self._page.keyboard.press("Delete")
        time.sleep(0.2)
        self._page.keyboard.type(value)
        self._page.keyboard.press("Enter")
        time.sleep(1)  # allow autosave

    def find_row_and_write(self, sheet_id: str, search_col: int,
                           search_value: str, write_col: int,
                           write_value: str, gid: int = 0) -> int:
        """
        Read the sheet as CSV, find the row where search_col contains search_value
        (exact, case-insensitive), then write write_value to write_col in that row.

        Returns the 1-indexed row number that was written, or raises ValueError.

        Example:
            row = drive.find_row_and_write(
                sheet_id, search_col=1, search_value="Claude-4.6-Sonnet-medium",
                write_col=2, write_value="alice@example.com"
            )
        """
        import csv, io
        csv_text = self.read(sheet_id, "spreadsheet")
        rows = list(csv.reader(io.StringIO(csv_text)))
        target_row = None
        for i, row_data in enumerate(rows):
            if len(row_data) >= search_col:
                cell = row_data[search_col - 1].strip().lower()
                if cell == search_value.strip().lower():
                    target_row = i + 1  # 1-indexed
                    break
        if target_row is None:
            raise ValueError(f"Value {search_value!r} not found in column {search_col}")
        self.write_sheet_cell(sheet_id, target_row, write_col, write_value, gid)
        return target_row


# ── CLI helper ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "search":
        query = " ".join(sys.argv[2:]) or "owner:me"
        with GDrive() as drive:
            results = drive.search(query)
        print(f"Found {len(results)} results for '{query}':")
        for i, f in enumerate(results, 1):
            print(f"  {i:2}. [{f['type']:<14}] {f['name']}")

    elif cmd == "ls":
        folder_id = sys.argv[2] if len(sys.argv) > 2 else None
        with GDrive() as drive:
            results = drive.list_folder(folder_id) if folder_id else drive.list_my_drive()
        for f in results:
            print(f"[{f['type']:<14}] {f['name']:<60} {f['id']}")

    elif cmd == "read":
        if len(sys.argv) < 4:
            print("Usage: python google_drive.py read <file_id> <type>")
            print("  type: document | spreadsheet | presentation")
            sys.exit(1)
        file_id, file_type = sys.argv[2], sys.argv[3]
        with GDrive() as drive:
            content = drive.read(file_id, file_type)
        print(content)

    elif cmd == "write-doc":
        if len(sys.argv) < 4:
            print("Usage: python google_drive.py write-doc <doc_id> <text...>")
            sys.exit(1)
        doc_id = sys.argv[2]
        append_text = " ".join(sys.argv[3:])
        with GDrive() as drive:
            drive.write_document_append(doc_id, append_text)
        print("Appended.")

    elif cmd == "write-slide":
        args = sys.argv[2:]
        tgt = "notes"
        if "--on-slide" in args:
            args = [a for a in args if a != "--on-slide"]
            tgt = "slide"
        if len(args) < 2:
            print("Usage: python google_drive.py write-slide [--on-slide] "
                  "<presentation_id> <text...>")
            print("  Default: append to speaker notes (matches export/txt).")
            print("  --on-slide: click main slide canvas and type there.")
            sys.exit(1)
        pres_id = args[0]
        append_text = " ".join(args[1:])
        with GDrive() as drive:
            drive.write_presentation_append(pres_id, append_text, target=tgt)
        print("Appended to Slides.")

    else:
        print(__doc__)
