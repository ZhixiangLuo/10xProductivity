# Triggers

Triggers are reusable event listeners. They detect events from systems, tools, and apps, normalize them into workflow events, and hand them to workflows or automations.

They complement `tool_connections/`:

- `tool_connections/` are the pull layer: the agent uses them to fetch context or take action on demand.
- `triggers/` are the push layer: they listen for events and wake up workflows when something happens.

Triggers do not decide what work should be done. A workflow or runtime host wires a trigger to a specific workflow.

```text
event from app/service
  -> trigger
  -> normalized workflow event
  -> workflow
  -> tool connections
  -> output
```

This layer is valuable in enterprise environments because normal webhook or app-install paths are often unavailable. A trigger can still listen through whatever surface the user already has: macOS notifications, desktop apps, browser notifications, authenticated sessions, email, or polling.

## Available Triggers

- `slack_polling/` polls the user's own Slack self-DM with an existing authenticated Slack session.
- `macos_notifications/` watches macOS Notification Center records for notifications from desktop apps and browsers.

## Future Trigger Research

The macOS notification trigger should grow an app catalog for common desktop/web apps:

- GitHub / GitHub Enterprise review-request notifications
- Outlook email notifications for PR review requests and calendar events
- Slack and Teams messages or mentions
- PagerDuty and incident notifications
- Calendar reminders

Each app note should capture bundle IDs, example notification payloads, what can be extracted, false positives, and which tool connection should be used for follow-up.
