from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def private_dir() -> Path:
    return Path(os.environ.get("TENX_PRIVATE_DIR", "~/.10xProductivity")).expanduser()


def tmp_dir() -> Path:
    raw = os.environ.get("TENX_TMP_DIR", "").strip()
    path = Path(raw).expanduser() if raw else private_dir() / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_environment() -> Path:
    root = repo_root()
    load_dotenv(dotenv_path=root / ".env", override=False)
    load_dotenv(dotenv_path=private_dir() / ".env", override=False)
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
    return root


def truthy_env(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")
