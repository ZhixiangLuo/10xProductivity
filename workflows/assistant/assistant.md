# Assistant Inbox Workflow

This workflow handles inbound personal-assistant requests that arrive through local triggers.

The workflow is intentionally separate from the trigger. A Slack self-DM poller, macOS notification listener, or future local event source can all emit a normalized event into this same workflow.

```text
trigger
  -> runtime host
  -> this workflow
  -> tool connections / other workflows
  -> concise result
```

## Available Now

- Slack self-DM polling can feed this workflow without requiring a Slack app, Socket Mode, webhook, or bot install.
- macOS notifications can feed this workflow for apps that already notify the desktop.
- The runtime host invokes Cursor, Claude Code, or Codex and passes the normalized event into this workflow.

Run with Slack polling:

```bash
10x-host --trigger slack-polling --workflow workflows/assistant/assistant.md --engine cursor
```

Run with macOS notifications:

```bash
10x-host --trigger macos-notifications --workflow workflows/assistant/assistant.md --engine cursor
```

## Workflow Instructions

When this file is loaded by the runtime host, act as the inbox workflow for the user's personal assistant:

- Keep replies short and phone-readable unless the user asks for depth.
- Use `verified_connections.md` and `tool_connections/` before inventing API calls.
- For broad cross-tool questions, follow `workflows/enterprise-search/enterprise-search.md`.
- For stand-up prep, follow `workflows/standup-prep/README.md`.
- If the inbound event is only a notification that something happened, use it as a signal and fetch authoritative details through tool connections before acting.
- If you need to emit an intermediate reply from the invoked agent turn, run `python -m runtime.replies --text "..."`.
- Do not expose raw CLI JSON, stack traces, tokens, cookies, or local private paths in user-facing replies.
- If a connected tool is missing or expired, say what source was unavailable and continue with the remaining sources.

## Private State

Runtime writes local state under `TENX_PRIVATE_DIR/tmp/` by default:

```text
~/.10xProductivity/tmp/
  agent_sessions.json
  triggers/
  scheduling/
```

Do not commit these files.
