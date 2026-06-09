# macOS Notifications Trigger

This trigger watches macOS Notification Center records and turns desktop notifications into normalized events.

It is useful in enterprise environments because many systems already send desktop or browser notifications even when direct webhooks, app installs, or bot tokens are unavailable.

## What It Does

```text
Desktop app / browser notification
  -> macOS Notification Center
  -> local usernoted SQLite database
  -> NormalizedEvent(source="macos_notifications")
  -> configured workflow
```

## Default Scope

The default watched bundle ID is Slack:

```text
com.tinyspeck.slackmacgap
```

Override with:

```text
TENX_MACOS_NOTIF_WATCH_APPS=com.tinyspeck.slackmacgap,com.microsoft.Outlook
```

## App Catalog To Build

The trigger should grow app-specific notes under this folder as each desktop/web app is tested:

- GitHub / GitHub Enterprise review-request notifications
- Outlook messages from GitHub/GHE or calendar reminders
- Slack mentions and channel notifications
- Teams mentions and messages
- PagerDuty incidents
- Calendar reminders

For each app, capture:

- Bundle ID
- Example title/subtitle/body values
- Detectable event types
- Metadata that must be fetched later from a tool connection
- False positives
- Dedupe strategy
- Verification steps

## Limitations

- This is macOS-only.
- Notification records can be short-lived, so the listener polls frequently.
- The notification preview is often incomplete; use tool connections for follow-up.
- It only sees notifications the OS actually presents.
