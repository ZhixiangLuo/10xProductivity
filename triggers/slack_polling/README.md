# Slack Polling Trigger

This trigger watches the user's own Slack self-DM using an existing authenticated Slack session.

It is useful when enterprise employees cannot create a personal Slack app, install a bot, register webhooks, or use Socket Mode. The trigger is a local workaround: it uses the user's current Slack session (`SLACK_XOXC` + `SLACK_D_COOKIE`) and emits a normalized event when the user sends themselves a message.

## What It Does

```text
Slack self-DM message
  -> conversations.history polling
  -> dedupe by Slack timestamp
  -> NormalizedEvent(source="slack_polling")
  -> configured workflow
```

## Environment

```text
SLACK_XOXC=xoxc-...
SLACK_D_COOKIE=...
```

Store these in `TENX_PRIVATE_DIR/.env`, not in the repo.

## Runtime Behavior

- Cold start baselines to the newest existing message so old self-DM history is not replayed.
- Normal restarts resume from the persisted `last_ts`.
- New messages reset the polling interval.
- Idle cycles back off with random jitter.
- A weekday reset brings the cadence back down after long idle periods.
- Agent-written self-DM replies should be prefixed with `[agent_reply]:` so they do not loop back as user commands.

## Limitations

- Polling is a fallback, not the ideal event model.
- It can be slower than a real webhook because latency depends on the current poll interval.
- It uses a user session, so keep cadence human-like and avoid unnecessary calls.
- It only covers messages the user sends to themselves; team-channel activity should be captured through other triggers, such as macOS notifications.
