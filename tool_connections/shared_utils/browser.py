#!/usr/bin/env python3
"""
Shared Playwright browser utilities for tool SSO scripts.

Each tool's sso.py imports from here rather than duplicating boilerplate.

Requirements:
    pip install playwright && playwright install chromium
"""

import functools
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Installing playwright...")
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Re-export for tool sso.py files that need it
__all__ = [
    "sync_playwright", "PlaywrightTimeout",
    "load_env_var", "load_env_file", "update_env_file",
    "http_get", "http_get_no_redirect",
    "make_ssl_ctx", "urlopen",
    "DEFAULT_ENV_FILE", "BROWSER_AUTOMATION_DIR",
]

DEFAULT_ENV_FILE = Path(__file__).parents[2] / ".env"

# Shared home for all persistent browser profiles and auth snapshots.
# Lives outside the repo (~/.browser_automation/) so sessions survive
# repo re-clones and are never accidentally committed.
BROWSER_AUTOMATION_DIR = Path.home() / ".browser_automation"


def load_env_var(key: str, default: str = "") -> str:
    """Load a variable from .env file or environment, falling back to default."""
    env_file = DEFAULT_ENV_FILE
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, default)


def load_env_file(env_path: Path) -> dict:
    """Read all key=value pairs from a .env file."""
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def update_env_file(env_path: Path, tokens: dict) -> None:
    """Write / update token values in a .env file."""
    if not env_path.exists():
        env_path.write_text("")
    content = env_path.read_text()

    def _upsert(text: str, key: str, value: str, section_hint: str = "") -> str:
        pattern = rf"^({re.escape(key)}=).*$"
        new_line = f"{key}={value}"
        if re.search(pattern, text, flags=re.MULTILINE):
            return re.sub(pattern, new_line, text, flags=re.MULTILINE)
        if section_hint and section_hint in text:
            return re.sub(
                rf"({re.escape(section_hint)}[^\n]*\n)",
                r"\1" + new_line + "\n",
                text,
            )
        return text + f"\n{new_line}\n"

    for key, value in tokens.items():
        if value:
            # Map token keys to env var names and section hints
            env_key = key.upper()
            section_hint = _section_hint(env_key)
            content = _upsert(content, env_key, value, section_hint)

    env_path.write_text(content)
    print(f"  Updated {env_path}")


def _section_hint(env_key: str) -> str:
    """Return the .env section comment that precedes the given env var.

    Derived automatically from the env key prefix (TOOL_... → # --- Tool),
    with overrides only for tools whose env key prefix doesn't match the tool name.
    No edits needed when adding new tools.
    """
    # Overrides for tools with irregular env key prefixes
    _overrides = {
        "GRAPH": "# --- Outlook / Microsoft 365",
        "OWA": "# --- Outlook / Microsoft 365",
        "GDRIVE": "# --- Google Drive",
    }
    prefix = env_key.split("_")[0]
    if prefix in _overrides:
        return _overrides[prefix]
    return f"# --- {prefix.title()}"


def make_ssl_ctx(verify: bool = True) -> ssl.SSLContext:
    """Create an SSL context.

    Default is normal certificate verification. Pass ``verify=False`` only after
    a verified request fails with ``ssl.SSLError`` (for example on laptops where
    Zscaler intercepts HTTPS and Python does not trust the local root CA).

    Usage in any connection file or sso.py:
        from tool_connections.shared_utils.browser import urlopen
        with urlopen(req, timeout=15) as r: ...

    If you need a raw context:
        ssl_ctx = make_ssl_ctx()
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as r: ...
    """
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


@functools.lru_cache(maxsize=1)
def _verified_ssl_ctx() -> ssl.SSLContext:
    return make_ssl_ctx(verify=True)


@functools.lru_cache(maxsize=1)
def _unverified_ssl_ctx() -> ssl.SSLContext:
    return make_ssl_ctx(verify=False)


def _is_ssl_error(exc: BaseException) -> bool:
    """Return True for direct or urllib-wrapped SSL failures."""
    if isinstance(exc, ssl.SSLError):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLError)


def urlopen(req, timeout: int = 15):
    """Open a URL with certificate verification, retrying once for Zscaler SSL.

    This is general-purpose: it first tries normal TLS verification for any
    website or application. Only if that exact request fails with ``SSLError``
    does it retry with verification disabled. Non-SSL errors are not masked.
    """
    try:
        return urllib.request.urlopen(req, context=_verified_ssl_ctx(), timeout=timeout)
    except Exception as exc:
        if not _is_ssl_error(exc):
            raise
        return urllib.request.urlopen(req, context=_unverified_ssl_ctx(), timeout=timeout)


def http_get(url: str, headers: dict) -> int:
    """Make a GET request and return the HTTP status code."""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urlopen(req, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def http_get_no_redirect(url: str, headers: dict) -> int:
    """GET without following redirects — returns 302 for expired sessions."""
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    def _open_with(ctx: ssl.SSLContext) -> int:
        opener = urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=8) as resp:
            return resp.status

    try:
        return _open_with(_verified_ssl_ctx())
    except Exception as exc:
        if not _is_ssl_error(exc):
            if isinstance(exc, urllib.error.HTTPError):
                return exc.code
            return 0
        try:
            return _open_with(_unverified_ssl_ctx())
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return 0
