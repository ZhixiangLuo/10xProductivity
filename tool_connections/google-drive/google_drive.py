"""
Google Drive helper — Playwright storage_state auth (no OAuth app needed).

Usage:
    from google_drive import GDrive

    with GDrive() as drive:
        files   = drive.search("coe")
        mine    = drive.search("owner:me")
        listing = drive.list_my_drive()
        content = drive.read(file_id, file_type)   # doc/sheet/slides → text/csv

Auth:
    Run once to capture session:
        python3 playwright_sso.py --gdrive-only
    Session saved to ~/.browser_automation/gdrive_auth.json (days/weeks lifetime).
    Re-run --gdrive-only if Drive redirects to sign-in.

Notes:
    - headless=False required — SSO needs it, and headed mode is 5× faster than
      headless for Drive (hardware-accelerated JS rendering vs software-only)
    - data-id in Drive DOM is truncated; full 44-char IDs come from href
    - read() uses browser download interception (temp path, NOT ~/Downloads)
    - Google Docs use canvas rendering — DOM text extraction not possible;
      read() calls the export URL which Playwright intercepts as a download

Verified: 2026-03-14, jeffrey.luo@workday.com
"""

import re, sys, time
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

    def __enter__(self) -> "GDrive":
        self._pw = sync_playwright().start()
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
        # Navigate to Drive once to establish session
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
            raise RuntimeError(
                "Google Drive session expired. Re-run: "
                "python3 playwright_sso.py --gdrive-only"
            )
        return self

    def __exit__(self, *_):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

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

    else:
        print(__doc__)
