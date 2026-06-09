from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.events import NormalizedEvent
from runtime.host import (
    DEFAULT_CURSOR_MODEL,
    AgentEngine,
    _final_message_from_result,
    _sanitize_cursor_trace,
    build_event_prompt,
    resolve_engine,
    session_key,
)


def test_resolve_engine_default_is_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TENX_AGENT_ENGINE", raising=False)
    assert resolve_engine(None) == AgentEngine.CURSOR


def test_resolve_engine_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENX_AGENT_ENGINE", "claude")
    assert resolve_engine(None) == AgentEngine.CLAUDE


def test_resolve_engine_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENX_AGENT_ENGINE", "cursor")
    assert resolve_engine("codex") == AgentEngine.CODEX


def test_default_cursor_model_value() -> None:
    assert DEFAULT_CURSOR_MODEL == "gpt-5.5-medium"


def test_session_key_format() -> None:
    assert session_key("slack_polling", AgentEngine.CLAUDE) == "slack_polling_claude_session_id"
    assert session_key("macos_notifications", AgentEngine.CODEX) == "macos_notifications_codex_session_id"


def test_event_prompt_includes_workflow_event_and_reply_bridge() -> None:
    event = NormalizedEvent(
        source="slack_polling",
        text="Please prep my stand-up",
        user_id="U123",
        channel_id="D123",
        thread_id="D123",
        metadata={"slack_ts": "1.23"},
    )
    prompt = build_event_prompt(event, Path("workflows/assistant/assistant.md"))
    assert "workflows/assistant/assistant.md" in prompt
    assert "slack_polling" in prompt
    assert "Please prep my stand-up" in prompt
    assert "runtime.replies" in prompt


def test_sanitize_cursor_trace_strips_reply_shell_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TENX_CURSOR_SANITIZE_TRACE", raising=False)
    noisy = '$ python -m runtime.replies --text "Hi" 403ms\nHi there.'
    cleaned = _sanitize_cursor_trace(noisy)
    assert "runtime.replies" not in cleaned
    assert "403ms" not in cleaned
    assert "Hi there." in cleaned


def test_sanitize_cursor_trace_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENX_CURSOR_SANITIZE_TRACE", "0")
    assert _sanitize_cursor_trace("$ echo hi") == "$ echo hi"


def test_final_message_prefers_top_level_result() -> None:
    assert _final_message_from_result({"result": " ok "}, stdout="ignored", stderr="", exit_code=0) == "ok"


def test_final_message_falls_back_to_response_text() -> None:
    assert _final_message_from_result({"response": {"text": "nested"}}, stdout="", stderr="", exit_code=0) == "nested"


@patch("runtime.host.run_cursor_agent")
def test_cursor_orchestrator_passes_default_model(mock_run) -> None:
    from runtime.agent_clients.cursor import CursorRunResult
    from runtime.host import invoke_agent

    mock_run.return_value = CursorRunResult(
        ok=True,
        exit_code=0,
        stdout='{"result": "ok"}',
        stderr="",
        parsed_json={"result": "ok"},
        session_id="c1",
    )
    invoke_agent(prompt="hi", engine=AgentEngine.CURSOR, resume_session_id=None)
    assert mock_run.call_args.kwargs["model"] == DEFAULT_CURSOR_MODEL
