#!/usr/bin/env python3
"""
Shared Playwright browser utilities for tool SSO scripts.

Each tool's sso.py imports from here rather than duplicating boilerplate.

Requirements:
    pip install playwright && playwright install chromium
"""

import os
import re
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


def http_get(url: str, headers: dict) -> int:
    """Make a GET request and return the HTTP status code."""
    import ssl
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def http_get_no_redirect(url: str, headers: dict) -> int:
    """GET without following redirects — returns 302 for expired sessions."""
    import ssl

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    try:
        opener = urllib.request.build_opener(_NoRedirect())
        req = urllib.request.Request(url, headers=headers)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        with opener.open(req, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0
