"""
Google Drive helper — hybrid local filesystem + Playwright daemon.

## Primary method: Google Drive for Desktop (local filesystem)
No auth, no tokens, no expiry. Google Drive for Desktop mounts your Drive at:
    ~/Library/CloudStorage/GoogleDrive-<email>/

Use GDriveLocal for:
    - Listing folders and files (instant, no browser)
    - Reading non-Google files (PDF, docx, txt, csv, etc.)
    - Searching by filename/content (mdfind/Spotlight — macOS only)
    - Getting file IDs from .gdoc/.gsheet/.gslides stubs
    - smart_search(): local-first with automatic online fallback + caching

Use GDrive for:
    - Reading Google Docs/Sheets/Slides content (stubs don't contain content)
    - Searching all of Drive including "Shared with me" and cloud-only files
    - Full-text search across Drive content

## Write support
Not supported. Google Docs and Slides have no write path without OAuth2.
Google Sheets keyboard-navigation write exists but is too fragile for production use.

## Quick start

    from google_drive import GDriveLocal

    local = GDriveLocal()               # no setup needed
    files = local.list_folder("My Drive")
    results = local.search("budget")    # local Spotlight search (instant)

    # Smart search: local first, online fallback + auto-cache
    results = local.smart_search("AI projects")

    # Read Google Docs/Sheets/Slides content via daemon
    file_id, ftype = local.get_id_and_type("My Drive/plan.gdoc")
    content = local.drive.read(file_id, ftype)

## Setup

GDriveLocal: Google Drive for Desktop must be installed and signed in.
    Mount path auto-detected from ~/Library/CloudStorage/GoogleDrive-*.
    macOS only.

GDrive (daemon): Run once to capture session, then start the daemon:
    python3 tool_connections/google-drive/sso.py --force
    python3 tool_connections/google-drive/gdrive_server.py start &

    Session saved to ~/.browser_automation/gdrive_auth.json (~7 day lifetime).
    Re-run sso.py --force + restart daemon when session expires.

Notes:
    - headless=False required for Playwright — SSO needs it, and headed mode is
      faster than headless for Drive (hardware-accelerated JS rendering)
    - data-id in Drive DOM is truncated; full 44-char IDs come from href
    - read() uses browser download interception (temp path, NOT ~/Downloads)
    - Bridge cache lives in tool_connections/google-drive/bridge_cache/ (gitignored)
"""

import json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

AUTH_FILE = Path.home() / ".browser_automation" / "gdrive_auth.json"

_STUB_EXTENSIONS = {".gdoc", ".gsheet", ".gslides", ".gform", ".gdraw", ".gmap", ".gsite"}
# Bridge cache files use .gdrive.json (Drive for Desktop drops writes to _STUB_EXTENSIONS)
_BRIDGE_SUFFIX = ".gdrive.json"
_STUB_TO_TYPE = {
    ".gdoc": "document",
    ".gsheet": "spreadsheet",
    ".gslides": "presentation",
    ".gform": "form",
}


def _find_drive_root() -> Path:
    """Auto-detect the Google Drive for Desktop mount path."""
    cloud = Path.home() / "Library" / "CloudStorage"
    if cloud.exists():
        candidates = sorted(cloud.glob("GoogleDrive-*"))
        if candidates:
            return candidates[0]
    raise RuntimeError(
        "Google Drive for Desktop mount not found. "
        "Install Google Drive for Desktop and sign in, then the Drive will appear at "
        "~/Library/CloudStorage/GoogleDrive-<email>/"
    )


# ── Local filesystem helper ────────────────────────────────────────────────────

class GDriveLocal:
    """
    Google Drive via local filesystem (Google Drive for Desktop).

    No auth, no tokens, no browser. Instant access to all files.
    Google Docs/Sheets/Slides appear as .gdoc/.gsheet/.gslides stubs — use
    get_id() to extract the file ID, then pass to GDrive.read() for content.

    For online operations (smart_search fallback, read), a single GDrive
    (daemon) connection is used lazily on first use and reused for all
    subsequent calls — no repeated auth prompts.

    Usage:
        local = GDriveLocal()

        # Local operations — no browser
        files = local.list_folder("My Drive")
        files = local.list_folder("My Drive/AI initiative")
        results = local.search("AIOps")
        file_id, ftype = local.get_id_and_type("My Drive/AIOps plan.gdoc")

        # Smart search — local first, online fallback (daemon reused)
        results = local.smart_search("AI projects")
        results = local.smart_search("budget 2026")   # instant from cache

        # Read via daemon
        content = local.drive.read(file_id, ftype)
    """

    def __init__(self, drive_root: Path | str | None = None,
                 auth_file: Path | str | None = None):
        self.root = Path(drive_root) if drive_root else _find_drive_root()
        self._auth_file = Path(auth_file) if auth_file else AUTH_FILE
        self._drive: "GDrive | None" = None  # lazy — opened on first online operation

    @property
    def drive(self) -> "GDrive":
        """
        The shared GDrive instance — connected to the persistent daemon.

        Use this for read() operations. The daemon must be running:
            python3 tool_connections/google-drive/gdrive_server.py start &
        """
        if self._drive is None or not self._drive._is_alive():
            self._drive = GDrive(self._auth_file)
            self._drive.__enter__()
        return self._drive

    def close(self) -> None:
        """Close the shared connection. Call when done with all Drive operations."""
        if self._drive is not None:
            try:
                self._drive.__exit__(None, None, None)
            except Exception:
                pass
            self._drive = None

    def __del__(self) -> None:
        self.close()

    def _resolve(self, path: str) -> Path:
        """Resolve a relative path (e.g. 'My Drive/foo') to an absolute Path."""
        return self.root / path

    def list_folder(self, folder_path: str = "My Drive") -> list[dict]:
        """
        List files and folders at the given path.

        folder_path: relative to Drive root, e.g. "My Drive" or "My Drive/AI initiative"

        Returns list of {name, path, type, is_stub}.
        type: 'folder' | 'document' | 'spreadsheet' | 'presentation' | 'file' | ...
        is_stub: True for .gdoc/.gsheet/.gslides (content must be read via GDrive)

        Note: uses subprocess ls to avoid Python iterdir() blocking on the FUSE-mounted
        network filesystem. Shell ls is fast because macOS caches the directory metadata.
        """
        import subprocess
        p = self._resolve(folder_path)
        proc = subprocess.run(
            ["ls", "-1Ap", str(p)],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            raise FileNotFoundError(f"Folder not found or unreadable: {p}\n{proc.stderr}")
        results = []
        for name in proc.stdout.splitlines():
            if not name:
                continue
            is_dir = name.endswith("/")
            clean_name = name.rstrip("/")
            lower = clean_name.lower()
            ext = Path(clean_name).suffix.lower()
            is_stub = ext in _STUB_EXTENSIONS or lower.endswith(_BRIDGE_SUFFIX)
            if is_dir:
                ftype = "folder"
            elif lower.endswith(_BRIDGE_SUFFIX):
                ftype = "cached"
            else:
                ftype = _STUB_TO_TYPE.get(ext, "file")
            results.append({
                "name": clean_name,
                "path": str((p / clean_name).relative_to(self.root)),
                "type": ftype,
                "is_stub": is_stub,
            })
        return results

    def search(self, query: str, folder_path: str = "My Drive") -> list[dict]:
        """
        Search for files by name or content (macOS Spotlight / mdfind).

        query: text to search for — matches filenames AND file content indexed by Spotlight
        folder_path: where to search (default: "My Drive"; use "." for entire Drive)

        Returns list of {name, path, type, is_stub}.

        Note: uses mdfind (Spotlight) which queries the local metadata index and is
        instant even on large Drive mounts. find/glob block on the FUSE filesystem.
        macOS only.
        """
        import subprocess
        base = self._resolve(folder_path)
        proc = subprocess.run(
            ["mdfind", "-onlyin", str(base), query],
            capture_output=True, text=True, timeout=10,
        )
        results = []
        seen: set[str] = set()
        for line in proc.stdout.splitlines():
            item = Path(line)
            if str(item) in seen:
                continue
            seen.add(str(item))
            ext = item.suffix.lower()
            is_stub = ext in _STUB_EXTENSIONS
            is_dir = item.is_dir() if not is_stub else False
            ftype = "folder" if is_dir else _STUB_TO_TYPE.get(ext, "file")
            try:
                rel = str(item.relative_to(self.root))
            except ValueError:
                rel = line
            results.append({
                "name": item.name,
                "path": rel,
                "type": ftype,
                "is_stub": is_stub,
            })
        return results

    def get_id(self, file_path: str) -> str:
        """
        Extract the Google file ID from a .gdoc/.gsheet/.gslides stub or
        a .gdrive.json bridge cache file.

        file_path: relative to Drive root, e.g. "My Drive/plan.gdoc"
                   or absolute path to a bridge cache file from smart_search()

        Returns the doc_id string (44 chars), which can be passed to GDrive.read().
        """
        p = Path(file_path) if Path(file_path).is_absolute() else self._resolve(file_path)
        name = p.name.lower()
        if p.suffix.lower() not in _STUB_EXTENSIONS and not name.endswith(_BRIDGE_SUFFIX):
            raise ValueError(
                f"{file_path!r} is not a Google stub (.gdoc/.gsheet/.gslides) "
                f"or bridge cache file (.gdrive.json). "
                f"Read it directly with Path.read_text() instead."
            )
        data = json.loads(p.read_text())
        doc_id = data.get("doc_id", "")
        if not doc_id:
            raise ValueError(f"No doc_id found in: {file_path}")
        return doc_id

    def get_id_and_type(self, file_path: str) -> tuple[str, str]:
        """
        Extract the Google file ID and file type from a stub or bridge cache file.

        file_path: relative to Drive root, or absolute path to a bridge cache file,
                   or result['path'] from smart_search().

        Returns (doc_id, file_type) where file_type is 'document', 'spreadsheet',
        'presentation', or 'form'.
        """
        p = Path(file_path) if Path(file_path).is_absolute() else self._resolve(file_path)
        doc_id = self.get_id(file_path)
        if p.name.lower().endswith(_BRIDGE_SUFFIX):
            data = json.loads(p.read_text())
            ftype = data.get("type", "document")
        else:
            ftype = _STUB_TO_TYPE.get(p.suffix.lower(), "document")
        return doc_id, ftype

    def read_file(self, file_path: str) -> str:
        """
        Read a non-Google file as text (txt, csv, md, json, etc.).
        For .docx/.xlsx use python-docx/openpyxl separately.

        file_path: relative to Drive root, e.g. "My Drive/report.txt"

        Raises ValueError for stub files (use get_id + GDrive.read instead).
        """
        p = self._resolve(file_path)
        if p.suffix.lower() in _STUB_EXTENSIONS:
            raise ValueError(
                f"{file_path!r} is a Google stub — use get_id() + GDrive.read() to get content."
            )
        return p.read_text(errors="replace")

    # ── Bridge cache ──────────────────────────────────────────────────────────

    # Cache lives in personal/tool_connections/google-drive/bridge_cache/ —
    # user-specific data (searched file IDs) that must stay gitignored.
    # Resolved by walking up from this file to the repo root, then into personal/.
    @property
    def _bridge_cache_dir(self) -> Path:
        repo_root = Path(__file__).parent.parent.parent  # tool_connections/google-drive → repo root
        cache_dir = repo_root / "personal" / "tool_connections" / "google-drive" / "bridge_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def cache_stub(self, name: str, file_id: str, file_type: str,
                   queries: list[str] | None = None) -> Path:
        """
        Write a bridge cache entry to bridge_cache/.

        This is inside the repo so the agent can write to it without sandbox
        restrictions. smart_search() checks this cache before going online,
        so repeated searches for the same file are instant.

        name:      display name of the file
        file_id:   Google Drive file ID (44-char string)
        file_type: 'document' | 'spreadsheet' | 'presentation' | 'form' | 'file'
        queries:   list of search queries that found this file (stored for cache lookup)

        Returns the Path of the written cache file.
        """
        safe_name = re.sub(r'[/\\:*?"<>|]', "_", name)
        cache_path = self._bridge_cache_dir / f"{safe_name}.gdrive.json"

        existing_queries: list[str] = []
        if cache_path.exists():
            try:
                existing_queries = json.loads(cache_path.read_text()).get("queries", [])
            except Exception:
                pass
        merged_queries = list(dict.fromkeys(existing_queries + (queries or [])))

        cache_path.write_text(json.dumps({
            "doc_id": file_id,
            "type": file_type,
            "name": name,
            "queries": merged_queries,
        }, indent=2))
        return cache_path

    def _search_bridge_cache(self, query: str) -> list[dict]:
        """
        Search bridge_cache/ by:
        1. Original query match — returns all files found by the same query before
        2. Filename substring match — catches partial name matches
        """
        q = query.lower()
        results = []
        seen: set[str] = set()
        for p in self._bridge_cache_dir.glob("*.gdrive.json"):
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            name = data.get("name", p.stem)
            doc_id = data.get("doc_id", "")
            if doc_id in seen:
                continue
            stored_queries = [sq.lower() for sq in data.get("queries", [])]
            if q in stored_queries or q in name.lower():
                seen.add(doc_id)
                results.append({
                    "name": name,
                    "path": str(p),
                    "type": data.get("type", "document"),
                    "is_stub": True,
                    "id": doc_id,
                    "source": "cache",
                    "cached": True,
                })
        return results

    def get_cached_id_and_type(self, name: str) -> tuple[str, str] | None:
        """
        Look up a file by name in the bridge cache.
        Returns (doc_id, file_type) if found, None if not cached.
        """
        safe_name = re.sub(r'[/\\:*?"<>|]', "_", name)
        cache_path = self._bridge_cache_dir / f"{safe_name}.gdrive.json"
        if not cache_path.exists():
            return None
        data = json.loads(cache_path.read_text())
        return data.get("doc_id", ""), data.get("type", "document")

    def smart_search(self, query: str, folder_path: str = "My Drive") -> list[dict]:
        """
        Search for files — three-tier lookup, fastest first:

        1. mdfind (Spotlight) on local Drive mount — instant, covers synced files.
        2. bridge_cache/ in the repo — instant, covers previously found online files.
        3. Online Drive search via daemon — covers "Shared with me" and cloud-only files.
           Writes results to bridge_cache/ so future calls skip this step.

        Returns list of {name, path, type, is_stub, source} where
        source is 'local' | 'cache' | 'online'.

        Online fallback requires the daemon to be running:
            python3 tool_connections/google-drive/gdrive_server.py start &
        Re-run sso.py --force + restart daemon if session expired (~7 days).
        """
        local_results = self.search(query, folder_path)
        if local_results:
            for r in local_results:
                r["source"] = "local"
            return local_results

        cache_results = self._search_bridge_cache(query)
        if cache_results:
            return cache_results

        print(f"[smart_search] Not found locally — searching online for '{query}'...")
        online_results = self.drive.search(query)

        if not online_results:
            return []

        result = []
        for f in online_results:
            if f.get("type") != "folder":
                try:
                    stub_path = self.cache_stub(
                        f["name"], f["id"], f["type"], queries=[query]
                    )
                    cached = True
                except Exception:
                    stub_path = None
                    cached = False
            else:
                stub_path = None
                cached = False

            result.append({
                "name": f["name"],
                "path": str(stub_path) if stub_path else f["name"],
                "type": f["type"],
                "is_stub": cached,
                "source": "online",
                "id": f["id"],
                "cached": cached,
            })

        return result


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
    Playwright-based Google Drive — routes all browser operations through a
    persistent background daemon (gdrive_server.py) so the browser stays open
    across Python process invocations. No repeated SSO auth.

    The daemon starts automatically on first use and keeps running until
    explicitly stopped. One browser open = all agent calls reuse it.

    Usage:
        # Via GDriveLocal (preferred — handles search + read in one object)
        local = GDriveLocal()
        content = local.drive.read(file_id, ftype)

        # Standalone
        drive = GDrive()
        results = drive.search("AI projects")   # daemon starts if needed
        content = drive.read(file_id, "document")

    Daemon management:
        python3 gdrive_server.py status   # check if running
        python3 gdrive_server.py stop     # shut it down
    """

    def __init__(self, auth_file: Path | str | None = None):
        self._auth_file = Path(auth_file) if auth_file else AUTH_FILE

    def __enter__(self) -> "GDrive":
        return self

    def __exit__(self, *_):
        # Don't stop the daemon — it should stay running across calls
        pass

    def _is_alive(self) -> bool:
        import gdrive_server
        return gdrive_server.is_running()

    # ── Core operations — proxied to daemon ──────────────────────────────────

    def search(self, query: str) -> list[dict]:
        """
        Search Drive. Returns list of {id, name, type}.

        query: any text, or Drive operators:
            owner:me            — files you own (guaranteed exportable)
            "exact phrase"      — exact match
            owner:me keyword    — combine operators
        """
        import gdrive_server
        return gdrive_server.search(query)

    def list_my_drive(self) -> list[dict]:
        """List files/folders in My Drive root."""
        return self.search("owner:me")

    def list_folder(self, folder_id: str) -> list[dict]:
        """List contents of a specific folder by ID (online, via daemon)."""
        import gdrive_server
        return gdrive_server.search(f"parents:{folder_id}")

    def read(self, file_id: str, file_type: str) -> str:
        """
        Export a Google file and return its text content.

        file_type: 'document' → plain text
                   'spreadsheet' → CSV
                   'presentation' → text (slide titles + speaker notes)

        Routed through the persistent daemon — no new browser launch.
        Only works for files you can open.
        """
        import gdrive_server
        return gdrive_server.read(file_id, file_type)


# ── CLI helper ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "ls-local":
        folder = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "My Drive"
        local = GDriveLocal()
        results = local.list_folder(folder)
        for f in results:
            stub = " [stub]" if f["is_stub"] else ""
            print(f"[{f['type']:<14}] {f['name']}{stub}")

    elif cmd == "search-local":
        query = " ".join(sys.argv[2:])
        local = GDriveLocal()
        results = local.search(query)
        print(f"Found {len(results)} files matching '{query}':")
        for f in results:
            stub = " [stub — use read to get content]" if f["is_stub"] else ""
            print(f"  [{f['type']:<14}] {f['path']}{stub}")

    elif cmd == "smart-search":
        query = " ".join(sys.argv[2:])
        local = GDriveLocal()
        results = local.smart_search(query)
        print(f"Found {len(results)} files matching '{query}':")
        for f in results:
            src = f.get("source", "local")
            stub = " [stub]" if f.get("is_stub") else ""
            print(f"  [{src}] [{f['type']:<14}] {f['path']}{stub}")

    elif cmd == "get-id":
        path = " ".join(sys.argv[2:])
        local = GDriveLocal()
        file_id, ftype = local.get_id_and_type(path)
        print(f"id:   {file_id}")
        print(f"type: {ftype}")

    elif cmd == "search":
        query = " ".join(sys.argv[2:]) or "owner:me"
        drive = GDrive()
        results = drive.search(query)
        print(f"Found {len(results)} results for '{query}':")
        for i, f in enumerate(results, 1):
            print(f"  {i:2}. [{f['type']:<14}] {f['name']}")

    elif cmd == "read":
        if len(sys.argv) < 4:
            print("Usage: python google_drive.py read <file_id> <type>")
            print("  type: document | spreadsheet | presentation")
            sys.exit(1)
        file_id, file_type = sys.argv[2], sys.argv[3]
        drive = GDrive()
        content = drive.read(file_id, file_type)
        print(content)

    else:
        print(__doc__)
