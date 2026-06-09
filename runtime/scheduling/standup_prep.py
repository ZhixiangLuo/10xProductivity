from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from runtime.agent_clients.claude import run_claude_agent
from runtime.env import load_environment, repo_root, tmp_dir

DEFAULT_AGENT_TIMEOUT_S = 720
DEFAULT_WORKFLOW_PATH = "workflows/standup-prep/README.md"


def state_path() -> Path:
    raw = os.environ.get("TENX_STANDUP_PREP_STATE_FILE", "").strip()
    return Path(raw).expanduser() if raw else tmp_dir() / "scheduling" / "standup-prep-state.json"


def load_state(path: Path | None = None) -> dict:
    path = path or state_path()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(state: dict, path: Path | None = None) -> None:
    path = path or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def workflow_path(raw: str | None = None) -> Path:
    value = raw or os.environ.get("TENX_STANDUP_PREP_WORKFLOW_PATH") or DEFAULT_WORKFLOW_PATH
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo_root() / path


def build_agent_prompt(*, workflow: Path, meeting_context: str, since: str | None = None) -> str:
    since_line = f"Use this lower bound for recent work if useful: {since}.\n" if since else ""
    return (
        f"Read and follow the workflow at {workflow}.\n"
        "Prepare a Slack-ready stand-up brief for the user. Use configured 10x tool "
        "connections and cite source links when available. If a source is unavailable, say so briefly.\n"
        f"{since_line}"
        "Meeting or team context:\n"
        f"{meeting_context.strip() or '(no explicit context provided)'}\n\n"
        "Output only the final brief text. Do not post to Slack yourself."
    )


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def compose_standup_prep(
    *,
    meeting_context: str,
    since: str | None = None,
    workflow: Path | None = None,
    timeout_s: int = DEFAULT_AGENT_TIMEOUT_S,
) -> str:
    workflow = workflow or workflow_path()
    prompt = build_agent_prompt(workflow=workflow, meeting_context=meeting_context, since=since)
    result = run_claude_agent(
        prompt=prompt,
        cwd=repo_root(),
        timeout_s=timeout_s,
        command=os.environ.get("TENX_CLAUDE_CLI_COMMAND", "claude").strip() or "claude",
        output_format="json",
        model=os.environ.get("TENX_STANDUP_PREP_MODEL", "").strip() or None,
        permission_mode=os.environ.get("TENX_CLAUDE_PERMISSION_MODE", "bypassPermissions").strip() or "bypassPermissions",
    )
    text = ""
    if isinstance(result.parsed_json, dict):
        parsed = result.parsed_json
        if isinstance(parsed.get("result"), str):
            text = parsed["result"]
        elif isinstance(parsed.get("response"), dict) and isinstance(parsed["response"].get("text"), str):
            text = parsed["response"]["text"]
    text = text or result.stdout or result.stderr
    if result.exit_code != 0:
        raise RuntimeError(f"stand-up prep agent failed ({result.exit_code}): {text[:500]}")
    text = _strip_code_fences(text)
    if not text:
        raise RuntimeError("stand-up prep agent returned an empty brief")
    return text


def _slack_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def post_to_slack(text: str, *, channel: str | None = None) -> str:
    token = os.environ.get("SLACK_XOXC", "").strip()
    cookie = os.environ.get("SLACK_D_COOKIE", "").strip()
    channel = channel or os.environ.get("TENX_STANDUP_PREP_SLACK_CHANNEL", "").strip()
    if not token or not cookie or not channel:
        raise RuntimeError("Missing SLACK_XOXC, SLACK_D_COOKIE, or TENX_STANDUP_PREP_SLACK_CHANNEL")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    if cookie:
        headers["Cookie"] = f"d={cookie}"
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps({"channel": channel, "text": text}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, context=_slack_context(), timeout=25) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Slack post failed: {result.get('error')}")
    return str(result.get("ts") or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a stand-up brief with a one-shot coding agent")
    parser.add_argument("--meeting-context", default=os.environ.get("TENX_STANDUP_PREP_CONTEXT", ""))
    parser.add_argument("--since", default=None, help="Optional lower bound for recent work, e.g. 2026-06-08")
    parser.add_argument("--workflow-path", default=None)
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_AGENT_TIMEOUT_S)
    parser.add_argument("--post", action="store_true", help="Post the brief to Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print the brief and do not persist state")
    args = parser.parse_args(argv)

    load_environment()
    previous = load_state()
    since = args.since or previous.get("last_success_at")
    brief = compose_standup_prep(
        meeting_context=args.meeting_context,
        since=since,
        workflow=workflow_path(args.workflow_path),
        timeout_s=args.timeout_s,
    )
    print(brief, flush=True)
    if args.post and not args.dry_run:
        ts = post_to_slack(brief)
    else:
        ts = ""
    if not args.dry_run:
        write_state(
            {
                "last_success_at": datetime.now(timezone.utc).isoformat(),
                "last_slack_ts": ts,
                "last_context": args.meeting_context,
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
