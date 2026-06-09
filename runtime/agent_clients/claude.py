from __future__ import annotations

import json
import logging
import os
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaudeRunResult:
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
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _terminate_process_group(pid: int, *, grace_s: int = 5) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            return
    deadline = time.time() + grace_s
    while time.time() < deadline:
        try:
            os.killpg(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_claude_agent(
    *,
    prompt: str,
    cwd: str | Path,
    timeout_s: int = 900,
    command: str = "claude",
    output_format: str = "json",
    resume_session_id: str | None = None,
    model: str | None = None,
    permission_mode: str = "bypassPermissions",
    extra_env: dict[str, str] | None = None,
) -> ClaudeRunResult:
    if not prompt or not prompt.strip():
        raise ValueError("prompt is required")

    cwd_path = Path(cwd).expanduser().resolve()
    if not cwd_path.exists():
        raise ValueError(f"cwd does not exist: {cwd_path}")

    cmd = [command, "-p", prompt, "--output-format", output_format]
    if resume_session_id and resume_session_id.strip():
        cmd.extend(["--resume", resume_session_id.strip()])
    if model and model.strip():
        cmd.extend(["--model", model.strip()])
    if permission_mode and permission_mode.strip():
        cmd.extend(["--permission-mode", permission_mode.strip()])

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    started = time.time()
    logger.info("Claude CLI start timeout_s=%s cmd=%s", timeout_s, format_cmd(cmd))
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

    return ClaudeRunResult(
        ok=exit_code == 0,
        exit_code=exit_code,
        stdout=stdout or "",
        stderr=stderr or "",
        parsed_json=parsed,
        session_id=session_id,
        started_at_iso=datetime.fromtimestamp(started, tz=timezone.utc).isoformat(),
        duration_s=time.time() - started,
    )
