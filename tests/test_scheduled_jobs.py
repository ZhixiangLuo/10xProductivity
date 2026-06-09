from __future__ import annotations

import json
from pathlib import Path

from runtime.scheduling import standup_prep


def test_build_agent_prompt_contains_workflow_context_and_rules(tmp_path: Path) -> None:
    workflow = tmp_path / "standup-prep.md"
    prompt = standup_prep.build_agent_prompt(
        workflow=workflow,
        meeting_context="Daily stand-up for Example Team",
        since="2026-06-08T12:00:00Z",
    )

    assert str(workflow) in prompt
    assert "Daily stand-up for Example Team" in prompt
    assert "2026-06-08T12:00:00Z" in prompt
    assert "Do not post to Slack yourself" in prompt
    assert "Output only the final brief text" in prompt


def test_strip_code_fences() -> None:
    assert standup_prep._strip_code_fences("```text\nhello\n```") == "hello"
    assert standup_prep._strip_code_fences("plain") == "plain"


def test_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    standup_prep.write_state({"last_success_at": "now"}, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"last_success_at": "now"}
    assert standup_prep.load_state(path) == {"last_success_at": "now"}


def test_load_state_tolerates_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not-json", encoding="utf-8")

    assert standup_prep.load_state(path) == {}
