# 10xProductivity - Codex Instructions

This file is the Codex entry point for 10xProductivity. Cursor skills are under `.cursor/skills/`; Codex should read those skill files directly when relevant.

## Connection Catalog

Load this at the start of any task that may use connected tools:

`~/.10xProductivity/verified_connections.md`

That file is the master catalog of active connections. It points to the right connection files under:

- `~/git_repos/10xProductivity/tool_connections/` for shared/public recipes
- `~/.10xProductivity/personal/` for private, device-specific recipes

Credentials live in:

`~/.10xProductivity/.env`

Never commit private connection files, credentials, cookies, tokens, or generated auth state.

## Skills And Workflows

Use `.cursor/skills/*/SKILL.md` as the local skill index for Codex too. These are thin pointers or task-specific instructions for:

- `enterprise-search`
- `tool-connector`
- `create-workflow`
- `linkedin-engagement`
- `colleague-distillation`
- `discover-ui-surface`

When a skill points to a canonical workflow under `workflows/`, read that canonical file and follow it.

## Search And Access Rules

For broad knowledge questions, read:

`workflows/enterprise-search/enterprise-search.md`

For setting up or repairing a connection, read:

`setup.md`

For creating a new connection, read:

`add-new-tool.md`

Use local files and the verified connection catalog before guessing endpoints or credentials.
