from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class CursorMode(str, Enum):
    ASK = "ask"
    PLAN = "plan"
    EXECUTE = "execute"


@dataclass(frozen=True)
class CursorRunResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    parsed_json: dict | None
    session_id: str | None = None
    started_at_iso: str | None = None
    duration_s: float | None = None


def format_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _try_parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    for line in reversed([line.strip() for line in text.splitlines() if line.strip()]):
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _read_cursor_api_key_from_file(env_file: Path) -> str | None:
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CURSOR_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"") or None
    except OSError:
        return None
    return None


def _env_with_cursor_api_key(cwd_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    if (env.get("CURSOR_API_KEY") or "").strip():
        return env
    for env_file in (cwd_path / ".env", Path.home() / ".10xProductivity" / ".env"):
        key = _read_cursor_api_key_from_file(env_file)
        if key:
            env["CURSOR_API_KEY"] = key
            break
    return env


@contextlib.contextmanager
def _singleflight(timeout_s: int) -> "contextlib.Iterator[None]":
    raw = os.environ.get("TENX_CURSOR_CLI_LOCK_FILE", "").strip()
    lock_path = Path(raw).expanduser() if raw else Path.home() / ".cursor" / "agent-cli.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + max(1, min(timeout_s, 60))
    with lock_path.open("w", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for Cursor CLI lock: {lock_path}")
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _terminate_process_group(pid: int, *, grace_s: int = 5) -> None:
    try:
        pgid = os.getpgid(pid)
    except OSError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + grace_s
    while time.time() < deadline:
        try:
            os.killpg(pgid, 0)
        except OSError:
            return
        time.sleep(0.2)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def run_cursor_agent(
    *,
    prompt: str,
    cwd: str | Path,
    mode: CursorMode,
    timeout_s: int = 900,
    command: str = "agent",
    output_format: str = "json",
    resume_session_id: str | None = None,
    model: str = "auto",
    extra_env: dict[str, str] | None = None,
) -> CursorRunResult:
    if not prompt or not prompt.strip():
        raise ValueError("prompt is required")

    cwd_path = Path(cwd).expanduser().resolve()
    if not cwd_path.exists():
        raise ValueError(f"cwd does not exist: {cwd_path}")

    cmd = [command, "-p", prompt, "--output-format", output_format, "--trust"]
    if resume_session_id and resume_session_id.strip():
        cmd.extend(["--resume", resume_session_id.strip()])
    if mode in (CursorMode.ASK, CursorMode.PLAN):
        cmd.extend(["--mode", mode.value])
    if mode == CursorMode.EXECUTE:
        cmd.append("--force")
    cmd.extend(["--model", (model or "auto").strip().lower() or "auto"])

    env = _env_with_cursor_api_key(cwd_path)
    if extra_env:
        env.update(extra_env)

    started = time.time()
    with _singleflight(timeout_s):
        logger.info("Cursor CLI start timeout_s=%s cmd=%s", timeout_s, format_cmd(cmd))
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd_path),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
            exit_code = proc.returncode or 0
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc.pid)
            stdout, stderr = proc.communicate()
            exit_code = 124

    parsed = _try_parse_json(stdout) if output_format == "json" else None
    session_id = None
    if isinstance(parsed, dict) and isinstance(parsed.get("session_id"), str):
        session_id = parsed["session_id"].strip() or None

    return CursorRunResult(
        ok=exit_code == 0,
        exit_code=exit_code,
        stdout=stdout or "",
        stderr=stderr or "",
        parsed_json=parsed,
        session_id=session_id,
        started_at_iso=datetime.fromtimestamp(started, tz=timezone.utc).isoformat(),
        duration_s=time.time() - started,
    )
