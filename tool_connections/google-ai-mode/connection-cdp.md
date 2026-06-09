---
name: google-ai-mode
auth: cdp-browser-profile
description: Google Search AI Mode through a dedicated signed-in real-Chrome CDP profile. Use for AI-synthesized web search answers and follow-up questions when Google AI Mode behavior is desired.
env_vars: []
auth_file: ~/.browser_automation/google_ai_mode_cdp_profile
sniffer:
  profile: ~/.browser_automation/google_ai_mode_cdp_profile
  url: https://www.google.com/search?udm=50&q=example
  filter: google.com
---

# Google AI Mode — Chrome CDP Profile

Google Search AI Mode (`udm=50`) through a dedicated signed-in real-Chrome profile. Use when the user wants Google AI Mode's synthesized web answer and follow-up behavior.

API docs: none. Google AI Mode is a consumer Search UI, not an official public API.

Session lifetime: Google session cookies in the Chrome profile typically last weeks to months. The SSO script checks session validity automatically and only asks for sign-in when the session has actually expired.

**Verified:** Production (`google.com/search?udm=50`) — initial query + multi-turn follow-up through real Chrome CDP — 2026-05. No VPN required.

## Credentials

Setup: `tool_connections/google-ai-mode/setup.md`

No `.env` variables are required. Sign in manually once in the dedicated profile:

```text
~/.browser_automation/google_ai_mode_cdp_profile
```

## Auth

Launch real Google Chrome with a dedicated automation profile and attach over CDP. This avoids using the user's daily Chrome profile while still allowing normal Google sign-in.

The SSO script resumes the existing profile session if valid, and only opens Chrome for sign-in when needed:

```bash
cd /path/to/10xProductivity
.venv/bin/python3 tool_connections/google-ai-mode/sso.py
```

Verified scrubbed output (session valid):

```text
$ .venv/bin/python3 tool_connections/google-ai-mode/sso.py
Session valid — profile: /home/user/.browser_automation/google_ai_mode_cdp_profile
No sign-in needed. Use --force to re-authenticate.
```

Verified scrubbed output (force re-auth):

```text
$ .venv/bin/python3 tool_connections/google-ai-mode/sso.py --force
Opened Google AI Mode profile: /home/user/.browser_automation/google_ai_mode_cdp_profile
Sign in to Google in the Chrome window.
The session persists in this dedicated profile.
```

## Verified snippets

```bash
# Single-turn AI Mode query.
cd /path/to/10xProductivity
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
        "8 ways to stand out in your stand-up meetings",
        "Jul 11, 2023 — The daily stand-up meeting agenda is for team members to report three things ...",
        "AI Mode response is ready"
      ],
      "url": "https://www.google.com/search?q=...&udm=50&mstk=..."
    }
  ]
}
```

```bash
# Multi-turn AI Mode conversation.
cd /path/to/10xProductivity
.venv/bin/python3 tool_connections/google-ai-mode/google_ai_mode.py \
  "What should a team member report in daily standup? Keep it brief." \
  --followup "Now tailor that for a principal engineer leading an AI platform migration."
```

Verified scrubbed output (second turn):

```json
{
  "turns": [
    {
      "query": "What should a team member report in daily standup? Keep it brief.",
      "lines": ["...initial answer with Yesterday/Today/Blockers format..."],
      "url": "https://www.google.com/search?q=...&udm=50&mstk=..."
    },
    {
      "query": "Now tailor that for a principal engineer leading an AI platform migration.",
      "lines": [
        "...initial context carried forward...",
        "Now tailor that for a principal engineer leading an AI platform migration.",
        "A principal engineer leading an AI platform migration should focus on high-level architecture, critical dependencies, and systemic blockers.",
        "Milestones: Completed the model training pipeline migration to the new cluster.",
        "Decisions: Finalized the data schema mapping for the real-time inference API.",
        "Next Steps: Leading the load testing for the new vector database.",
        "Risks: Data ingestion latency is spikes above our 50ms SLA target.",
        "Dependencies: Awaiting security clearance for the new cloud data warehouse.",
        "AI Mode response is ready"
      ],
      "url": "https://www.google.com/search?q=...&udm=50&mstk=...&csuir=1"
    }
  ]
}
```

```bash
# Traffic capture for endpoint research.
cd /path/to/10xProductivity
.venv/bin/python3 tool_connections/shared_utils/traffic_sniffer.py \
  --profile "$HOME/.browser_automation/google_ai_mode_cdp_profile" \
  --url "https://www.google.com/search?udm=50&q=example" \
  --filter "google.com" \
  --output "${TENX_PRIVATE_DIR:-$HOME/.10xProductivity}/personal/google-ai-mode/google_ai_mode_traffic.jsonl"
# → Captures /search?udm=50 and AI Mode async calls. Direct replay of /async/folif returned HTTP 400, so browser extraction remains the supported path.
```

## Agent behavior

**Read actions — run freely, no approval needed:**
- Submit a Google AI Mode query through the dedicated profile.
- Submit follow-up questions in the same AI Mode page.
- Extract rendered answer text and source result snippets from the page.

**Write/interact actions — get explicit approval before executing:**
- Signing in to Google.
- Changing Google account settings.
- Interacting with personalized Google services beyond Search/AI Mode.

## Typical actions to capture with the sniffer

Run:

```bash
.venv/bin/python3 tool_connections/shared_utils/traffic_sniffer.py --tool google-ai-mode --capture-bodies
```

Then perform:
- Initial AI Mode query.
- One or more follow-up questions.
- Click cited sources.
- Open AI Mode history if needed.

## Notes

- This is a browser connection, not a stable REST API. Prefer rendered-page extraction over replaying Google async endpoints.
- Direct replay of captured `/async/folif` and `/async/folwr` calls returned HTTP 400 because requests include volatile page/session parameters.
- Anonymous access may work for some queries but can hit Google's unusual-traffic interstitial. A signed-in dedicated Chrome profile is more reliable.
- Do not use the user's daily Chrome profile; use the dedicated automation profile only.
- Close or reuse the CDP Chrome window. If the profile is locked after a crash, terminate the Chrome process for this profile and remove `SingletonLock` in the dedicated profile only.
