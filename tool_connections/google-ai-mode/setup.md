---
name: google-ai-mode-setup
description: Set up Google Search AI Mode through a dedicated real-Chrome CDP profile. No API token; sign in once in the automation profile.
---

# Google AI Mode — Setup

## Auth method: real Chrome CDP profile

Google AI Mode is a consumer Google Search surface, not an official public API. The working 10x path is a dedicated real-Chrome profile with Chrome DevTools Protocol attach, similar to the Google Drive CDP pattern.

Session lifetime: Google session cookies in the Chrome profile typically last weeks to months. The SSO script checks validity automatically and only asks for sign-in when expired.

**What to ask the user:**
- "Sign in to Google in the Chrome window that opens." No API token or OAuth app is needed.

## Steps

1. Open the dedicated Chrome profile:

```bash
cd /path/to/10xProductivity
.venv/bin/python3 tool_connections/google-ai-mode/sso.py
```

2. If the session is already valid, the script reports it and exits:

```text
Session valid — profile: /home/user/.browser_automation/google_ai_mode_cdp_profile
No sign-in needed. Use --force to re-authenticate.
```

3. If not signed in, sign in to Google in the Chrome window that opens.

4. Verify with a query:

```bash
.venv/bin/python3 tool_connections/google-ai-mode/google_ai_mode.py \
  "what should a team member report in daily standup? answer briefly"
```

## Verify

```bash
.venv/bin/python3 tool_connections/google-ai-mode/google_ai_mode.py \
  "what should a team member report in daily standup? answer briefly"
```

Verified scrubbed output:

```json
{
  "turns": [
    {
      "query": "what should a team member report in daily standup? answer briefly",
      "lines": [
        "what should a team member report in daily standup? answer briefly",
        "A team member should report three key points during a daily standup:",
        "Yesterday: What you completed since the last meeting.",
        "Today: What you plan to achieve before the next meeting.",
        "Blockers: Any obstacles slowing down your progress.",
        "Keep the update focused, relevant to the team, and under two minutes.",
        "AI Mode response is ready"
      ],
      "url": "https://www.google.com/search?q=...&udm=50&mstk=..."
    }
  ]
}
```

If Chrome routes a new query into `chrome://contextual-tasks`, the query command
automatically recovers the matching embedded webview. Requested follow-ups use
the contextual-task host page's native composer, so they remain visible in the
same saved Google thread.

Multi-turn:

```bash
.venv/bin/python3 tool_connections/google-ai-mode/google_ai_mode.py \
  "What should a team member report in daily standup? Keep it brief." \
  --followup "Now tailor that for a principal engineer leading an AI platform migration."
```

Verified scrubbed output (second turn):

```json
{
  "query": "Now tailor that for a principal engineer leading an AI platform migration.",
  "lines": [
    "A principal engineer leading an AI platform migration should focus on high-level architecture, critical dependencies, and systemic blockers.",
    "Milestones: Completed the model training pipeline migration to the new cluster.",
    "Decisions: Finalized the data schema mapping for the real-time inference API.",
    "Next Steps: Leading the load testing for the new vector database.",
    "Risks: Data ingestion latency is spikes above our 50ms SLA target.",
    "Dependencies: Awaiting security clearance for the new cloud data warehouse.",
    "AI Mode response is ready"
  ]
}
```

**Connection details:** `tool_connections/google-ai-mode/connection-cdp.md`

## `.env` entries

None. Session state lives in the dedicated Chrome profile:

```text
~/.browser_automation/google_ai_mode_cdp_profile
```

## Refresh

The SSO script automatically resumes the existing session if valid:

```bash
.venv/bin/python3 tool_connections/google-ai-mode/sso.py
# → "Session valid" if signed in, or opens Chrome for sign-in if expired.
```

Use `--force` to open Chrome for manual re-authentication regardless:

```bash
.venv/bin/python3 tool_connections/google-ai-mode/sso.py --force
```
