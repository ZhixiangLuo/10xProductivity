from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .agent_clients.claude import run_claude_agent
from .agent_clients.cursor import CursorMode, run_cursor_agent
from .env import load_environment, repo_root, tmp_dir, truthy_env
from .events import NormalizedEvent

logger = logging.getLogger(__name__)


class AgentEngine(str, Enum):
    CURSOR = "cursor"
    CLAUDE = "claude"
    CODEX = "codex"


@dataclass(frozen=True)
class AgentInvocationResult:
    exit_code: int
    stdout: str
    stderr: str
    final_message: str
    session_id: str | None


DEFAULT_CURSOR_MODEL = "gpt-5.5-medium"


def resolve_engine(raw: str | None = None) -> AgentEngine:
    value = (raw or os.environ.get("TENX_AGENT_ENGINE") or "cursor").strip().lower()
    if value in ("cursor", "claude", "codex"):
        return AgentEngine(value)
    return AgentEngine.CURSOR


def workflow_path(raw: str | None = None) -> Path:
    value = raw or os.environ.get("TENX_WORKFLOW_PATH") or "workflows/assistant/assistant.md"
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo_root() / path


def session_file() -> Path:
    raw = os.environ.get("TENX_AGENT_SESSION_FILE", "").strip()
    return Path(raw).expanduser() if raw else tmp_dir() / "agent_sessions.json"


def _load_sessions() -> dict[str, str]:
    try:
        data = json.loads(session_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_sessions(sessions: dict[str, str | None]) -> None:
    path = session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: value for key, value in sessions.items() if value}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def session_key(trigger: str, engine: AgentEngine) -> str:
    return f"{trigger}_{engine.value}_session_id"


def _final_message_from_result(parsed_json: dict | None, *, stdout: str, stderr: str, exit_code: int) -> str:
    if isinstance(parsed_json, dict):
        result = parsed_json.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()
        response = parsed_json.get("response")
        if isinstance(response, dict) and isinstance(response.get("text"), str):
            return response["text"].strip()
        if isinstance(response, str) and response.strip():
            return response.strip()
    return (stdout or "").strip() or (stderr or "").strip() or f"Exit code {exit_code}"


def _sanitize_cursor_trace(text: str) -> str:
    if not truthy_env("TENX_CURSOR_SANITIZE_TRACE", default=True):
        return (text or "").strip()
    kept: list[str] = []
    for raw_line in (text or "").replace("\r\n", "\n").split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if "runtime.replies" in stripped:
            continue
        if re.fullmatch(r"\d{1,8}\s*ms", stripped):
            continue
        trimmed = re.sub(r"\s+[0-9]{1,8}\s*ms\s*$", "", raw_line.rstrip()).strip()
        if trimmed:
            kept.append(trimmed)
    return "\n".join(kept).strip()


def build_event_prompt(event: NormalizedEvent, workflow: Path) -> str:
    metadata = "\n".join(f"- {key}: {value}" for key, value in sorted(event.metadata.items()))
    return (
        f"Read and follow the workflow at {workflow}.\n"
        "A local trigger produced the event below. Decide what the workflow requires, "
        "use connected tools when needed, and return a concise user-visible result.\n\n"
        f"Source: {event.source}\n"
        f"User: {event.user_id or '(unknown)'}\n"
        f"Channel: {event.channel_id or '(none)'}\n"
        f"Thread: {event.thread_id or '(none)'}\n"
        f"Metadata:\n{metadata or '- none'}\n\n"
        f"Event text:\n{event.text.strip()}\n\n"
        "If you need to emit an intermediate reply from the coding-agent run, use "
        '`python -m runtime.replies --text "..."`.'
    )


def invoke_agent(
    *,
    prompt: str,
    engine: AgentEngine,
    resume_session_id: str | None,
    extra_env: dict[str, str] | None = None,
) -> AgentInvocationResult:
    root = repo_root()
    if engine == AgentEngine.CURSOR:
        result = run_cursor_agent(
            prompt=prompt,
            cwd=root,
            mode=CursorMode(os.environ.get("TENX_CURSOR_MODE", "execute")),
            timeout_s=int(os.environ.get("TENX_CURSOR_TIMEOUT_S", "900")),
            command=os.environ.get("TENX_CURSOR_CLI_COMMAND", "agent"),
            output_format="json",
            resume_session_id=resume_session_id,
            model=os.environ.get("TENX_CURSOR_MODEL", DEFAULT_CURSOR_MODEL),
            extra_env=extra_env,
        )
        text = _sanitize_cursor_trace(
            _final_message_from_result(result.parsed_json, stdout=result.stdout, stderr=result.stderr, exit_code=result.exit_code)
        )
        return AgentInvocationResult(result.exit_code, result.stdout, result.stderr, text, result.session_id)

    if engine == AgentEngine.CLAUDE:
        result = run_claude_agent(
            prompt=prompt,
            cwd=root,
            timeout_s=int(os.environ.get("TENX_CLAUDE_TIMEOUT_S", "900")),
            command=os.environ.get("TENX_CLAUDE_CLI_COMMAND", "claude"),
            output_format="json",
            resume_session_id=resume_session_id,
            model=os.environ.get("TENX_CLAUDE_MODEL", "").strip() or None,
            permission_mode=os.environ.get("TENX_CLAUDE_PERMISSION_MODE", "bypassPermissions"),
            extra_env=extra_env,
        )
        text = _final_message_from_result(result.parsed_json, stdout=result.stdout, stderr=result.stderr, exit_code=result.exit_code)
        return AgentInvocationResult(result.exit_code, result.stdout, result.stderr, text, result.session_id)

    with tempfile.NamedTemporaryFile(prefix="tenx-codex-final-", suffix=".txt", delete=False) as handle:
        final_path = Path(handle.name)
    cmd = [os.environ.get("TENX_CODEX_COMMAND", "codex"), "exec", "--json", "-o", str(final_path)]
    if truthy_env("TENX_CODEX_BYPASS_APPROVALS", default=False):
        cmd.append("--dangerously-bypass-approvals-and-sandbox")
    cmd.extend(["resume", resume_session_id, prompt] if resume_session_id else [prompt])
    proc = subprocess.run(cmd, cwd=str(root), env={**os.environ, **(extra_env or {})}, capture_output=True, text=True)
    try:
        text = final_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        text = ""
    finally:
        final_path.unlink(missing_ok=True)
    return AgentInvocationResult(proc.returncode or 0, proc.stdout or "", proc.stderr or "", text, None)


_dispatch_lock = threading.Lock()


def dispatch_event(event: NormalizedEvent, *, workflow: Path, engine: AgentEngine) -> str:
    with _dispatch_lock:
        sessions = _load_sessions()
        key = session_key(event.source, engine)
        session_id = sessions.get(key)
        with tempfile.NamedTemporaryFile(prefix="tenx-replies-", suffix=".jsonl", delete=False) as handle:
            reply_log = Path(handle.name)
        try:
            result = invoke_agent(
                prompt=build_event_prompt(event, workflow),
                engine=engine,
                resume_session_id=session_id,
                extra_env={
                    "TENX_REPLY_CHANNEL_ID": event.channel_id,
                    "TENX_REPLY_THREAD_ID": event.thread_id or "",
                    "TENX_REPLY_LOG_PATH": str(reply_log),
                },
            )
            sessions[key] = result.session_id or session_id
            _save_sessions(sessions)
            if result.exit_code != 0:
                return f"{engine.value} error: {result.stderr or result.stdout or result.final_message}"
            return result.final_message.strip()
        finally:
            reply_log.unlink(missing_ok=True)


def _run_slack_polling(workflow: Path, engine: AgentEngine) -> None:
    from triggers.slack_polling.poller import start_slack_poller

    def handle(event: NormalizedEvent) -> None:
        text = dispatch_event(event, workflow=workflow, engine=engine)
        if text:
            print(text, flush=True)

    start_slack_poller(handle, state_file=tmp_dir() / "triggers" / "slack_polling_state.json").join()


def _run_macos_notifications(workflow: Path, engine: AgentEngine) -> None:
    from triggers.macos_notifications.listener import start_macos_notification_listener

    def handle(event: NormalizedEvent) -> None:
        text = dispatch_event(event, workflow=workflow, engine=engine)
        if text:
            print(text, flush=True)

    start_macos_notification_listener(handle).join()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Run a 10x trigger against a workflow")
    parser.add_argument("--trigger", choices=("slack-polling", "macos-notifications"), required=True)
    parser.add_argument("--workflow", default=None, help="Workflow markdown path")
    parser.add_argument("--engine", choices=("cursor", "claude", "codex"), default=None)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    load_environment()
    engine = resolve_engine(args.engine)
    workflow = workflow_path(args.workflow)
    if args.trigger == "slack-polling":
        _run_slack_polling(workflow, engine)
    else:
        _run_macos_notifications(workflow, engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
