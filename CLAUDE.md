# 10xProductivity — Claude Code Instructions

At the start of every session, read these two files:

1. `~/code/10xProductivity/verified_connections.md` — active tool connections and capability index
2. `~/code/10xProductivity/workflows/enterprise-search/enterprise-search.md` — cross-tool search workflow

## Critical: always activate the venv

All tool operations that use Playwright (Google Drive, Slack SSO refresh, Sana SSO refresh) require the venv:

```bash
cd ~/code/10xProductivity && source .venv/bin/activate
```

The system Python (3.7) does not have playwright installed. Only the venv at `.venv/` does.

## Tool connection paths

All active connections are in `personal/` (not `tool_connections/`):

- `personal/slack/` — Slack enterprise SSO session
- `personal/google-drive/` — Google Drive Playwright session
- `personal/outlook/` — Outlook M365 SSO tokens
- `personal/github/` — GitHub.com PAT
- `personal/sana/` — Sana Agents SSO session

## Refreshing short-lived tokens

```bash
cd ~/code/10xProductivity && source .venv/bin/activate

# Slack (~8h)
python3 tool_connections/shared_utils/playwright_sso.py --slack-only

# Outlook (~1h)
python3 tool_connections/shared_utils/playwright_sso.py --outlook-only

# Google Drive (days–weeks)
python3 tool_connections/shared_utils/playwright_sso.py --gdrive-only

# Sana Agents (unknown TTL)
python3 personal/sana/sso.py --force
```
