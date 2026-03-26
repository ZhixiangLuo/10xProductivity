#!/usr/bin/env python3
"""
SSO session refresher — discovery orchestrator.

Discovers all tool_connections/*/sso.py plugins and delegates to them.
Each plugin exposes: TOOL_NAME, ENV_KEYS, check(env) -> bool, capture(env) -> dict.

Adding a new tool never requires changes to this file — just create
tool_connections/<tool>/sso.py with the standard interface.

Usage:
    python3 playwright_sso.py                  # refresh all expired tokens
    python3 playwright_sso.py --force          # refresh all regardless
    python3 playwright_sso.py --slack-only     # refresh Slack only
    python3 playwright_sso.py --grafana-only   # refresh Grafana only
    python3 playwright_sso.py --gdrive-only    # refresh Google Drive only
    python3 playwright_sso.py --teams-only     # refresh Microsoft Teams only
    python3 playwright_sso.py --outlook-only   # refresh Outlook only
    python3 playwright_sso.py --list           # list discovered plugins
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parents[2] / ".env"
TOOL_CONNECTIONS_DIR = Path(__file__).parents[1]


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def load_env(env_path: Path = ENV_FILE) -> dict[str, str]:
    if not env_path.exists():
        return {}
    return {k.strip(): v.strip() for line in env_path.read_text().splitlines()
            if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}


def write_env(tokens: dict[str, str], env_path: Path = ENV_FILE) -> None:
    content = env_path.read_text() if env_path.exists() else ""
    for key, value in tokens.items():
        new_line = f"{key}={value}"
        if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
            content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
        else:
            content += f"\n{new_line}\n"
    env_path.write_text(content)
    print(f"  Updated {env_path}")


# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------

def discover_plugins() -> dict[str, object]:
    """
    Scan tool_connections/*/sso.py and load each as a plugin module.
    Returns {tool_name: module} for every plugin with a valid interface.
    """
    plugins = {}
    for sso_path in sorted(TOOL_CONNECTIONS_DIR.glob("*/sso.py")):
        spec = importlib.util.spec_from_file_location(
            f"sso_{sso_path.parent.name}", sso_path
        )
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"  Warning: failed to load {sso_path}: {e}", file=sys.stderr)
            continue
        if hasattr(mod, "TOOL_NAME") and hasattr(mod, "check") and hasattr(mod, "capture"):
            plugins[mod.TOOL_NAME] = mod
    return plugins


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    plugins = discover_plugins()

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env-file", type=Path, default=ENV_FILE, metavar="PATH")
    parser.add_argument("--force", action="store_true", help="Refresh even if tokens are valid")
    parser.add_argument("--list", action="store_true", help="List discovered plugins and exit")

    for name in plugins:
        parser.add_argument(f"--{name}-only", action="store_true",
                            help=f"Refresh {name} only")

    args = parser.parse_args()

    if args.list:
        print("Discovered SSO plugins:")
        for name, mod in plugins.items():
            keys = getattr(mod, "ENV_KEYS", [])
            print(f"  {name:20s} → {', '.join(keys)}")
        return

    env = load_env(args.env_file)

    # Determine which tools to run
    only_flags = {name: getattr(args, f"{name}_only", False) for name in plugins}
    any_only = any(only_flags.values())

    targets = {name: mod for name, mod in plugins.items()
               if not any_only or only_flags.get(name)}

    print("SSO token refresher")
    print(f"  .env: {args.env_file}")
    print()

    for name, mod in targets.items():
        if not args.force:
            valid = mod.check(env)
            status = "ok" if valid else "expired or missing"
            print(f"  {name}: {status}")
            if valid:
                continue

        print(f"  Refreshing {name}...")
        try:
            tokens = mod.capture(env)
            write_env(tokens, args.env_file)
            env.update(tokens)
            for k, v in tokens.items():
                print(f"    {k}: {v[:50]}...")
        except Exception as e:
            print(f"  ERROR refreshing {name}: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
