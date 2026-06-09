# Stand-up Prep Workflow

This workflow prepares a concise, evidence-backed brief before a recurring status meeting.

It is a workflow, not a scheduler. The runtime can run it manually, from cron/launchd, or after a future trigger. The workflow owns the useful work; runtime scheduling only decides when to call it.

## Goal

Prepare a Slack-ready brief for the user's stand-up or daily sync:

- What changed since the last brief
- What the user should say
- What blockers, review needs, or decisions should be raised
- Which source links support the update

## Run It

Review without posting:

```bash
10x-standup-prep \
  --meeting-context "Daily stand-up for <team/project>" \
  --dry-run
```

Post after review:

```bash
10x-standup-prep \
  --meeting-context "Daily stand-up for <team/project>" \
  --post
```

The command:

1. Loads repo `.env`, then `TENX_PRIVATE_DIR/.env`.
2. Reads this workflow.
3. Runs a one-shot coding agent.
4. Prints the brief.
5. Posts to Slack only when `--post` is passed.
6. Stores run state under `TENX_PRIVATE_DIR/tmp/scheduling/`.

## Environment

```text
TENX_PRIVATE_DIR=~/.10xProductivity
TENX_CLAUDE_CLI_COMMAND=claude
TENX_CLAUDE_PERMISSION_MODE=bypassPermissions
TENX_STANDUP_PREP_CONTEXT=Daily stand-up for <team/project>
TENX_STANDUP_PREP_SLACK_CHANNEL=D...
TENX_STANDUP_PREP_WORKFLOW_PATH=workflows/standup-prep/README.md
TENX_STANDUP_PREP_STATE_FILE=~/.10xProductivity/tmp/scheduling/standup-prep-state.json

# Slack posting uses the user-session credential verified by the Slack connection.
SLACK_XOXC=xoxc-...
SLACK_D_COOKIE=...
```

Connections for Jira, GitHub, Slack search, docs, and other sources come from `TENX_PRIVATE_DIR/verified_connections.md` and the corresponding `tool_connections/` recipes.

## Retrieval Guidance

Use externalized work traces only. Good sources include:

- Jira/Linear tickets assigned to, reported by, commented on, reviewed by, or blocking the user
- PRs authored by, reviewed by, assigned to, or mentioning the user
- Slack threads in work channels where the user answered, was asked for help, or made a decision
- Docs or pages recently created, edited, reviewed, or assigned to the user
- Calendar context only when it explains a decision, blocker, handoff, or expected update
- Operational systems only when they show a work action, incident, deployment, alert, or verification relevant to the meeting

Skip private notes, local-only experiments, generic DMs, routine meetings with no outcome, and anything not anchored to shared work.

## Brief Shape

Write a Slack-ready message using mrkdwn:

```text
*Stand-up Prep: <meeting/team>* — *<local time if known>*

- *<work item / category>:* <what changed + status>. Link the Jira key, PR, Slack thread, or doc inline.
- *<next item>:* ...
- _FYI (may skip):_ <low-priority awareness items, if any>
```

Keep it under about 60 seconds of spoken status. Prefer grouped bullets ordered by importance over rigid "Yesterday / Today / Blockers" sections. If a source is missing or credentials are expired, say that briefly instead of inventing an update.

## Future Workflow Example: Automatic PR Review

Automatic PR review is a good future workflow because it composes every layer:

```text
Outlook/GitHub/Slack notification trigger
  -> runtime dedupe and state
  -> automatic-pr-review workflow
  -> GitHub/GHE, Jira, Slack, and CI tool connections
  -> draft review summary, Slack reply, or PR comment
```

The trigger may be indirect. In enterprise environments, GitHub often reaches the user through Outlook, Slack, Teams, or a desktop/browser notification rather than through a webhook the user controls. The workflow should use the trigger as a signal, then fetch authoritative context through the relevant tool connections.
