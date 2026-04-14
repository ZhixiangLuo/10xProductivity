---
name: colleague-distillation
description: Distill a colleague into a reusable AI skill (work + persona) using tool connections — Slack, Slack AI, Jira, GHE, Bitbucket, Confluence, SharePoint, Teams, Outlook, Notion, Linear, Google Docs, and more — without manual paste. Use when the user wants a colleague skill, digital twin of a coworker, or capture of someone's technical voice from workplace systems. Requires tool_connections + 10xProductivity verified_connections (or equivalent .env).
---

> **Canonical copy:** `~/git_repos/the-genesis/.genesis/skills/colleague-distillation/SKILL.md`. This file is a **mirror** for Cursor when the workspace is 10xProductivity only; prefer editing Genesis first, then re-copy if needed.

# Colleague distillation (tool-backed)

## Purpose

Produce a **colleague skill**: structured **work knowledge** (systems, standards, review style) plus **persona** (tone, decisions, interpersonal habits), using **APIs and search** already wired in **tool_connections** / **10xProductivity** — not hand-pasted exports.

Output layout matches the open **[colleague-skill](https://github.com/titanwings/colleague-skill)** convention so results can coexist with that generator:

- `colleagues/{slug}/work.md`
- `colleagues/{slug}/persona.md`
- `colleagues/{slug}/meta.json`
- `colleagues/{slug}/SKILL.md` (merged invocable skill)

**Optional:** Clone colleague-skill for its `prompts/work_analyzer.md`, `persona_analyzer.md`, `work_builder.md`, `persona_builder.md` if you want identical extraction templates; this skill defines *what to fetch* and *where to write*.

---

## Prerequisites

1. Load **`tool_connections`** — `$GENESIS_DIRECTORY/.genesis/skills/tool_connections/SKILL.md`, or if `GENESIS_DIRECTORY` is unset use `~/git_repos/the-genesis/.genesis/skills/tool_connections/SKILL.md`.
2. Load **`~/git_repos/10xProductivity/verified_connections.md`** — only call tools listed there (or documented in `10xProductivity/tool_connections/` / `personal/`).
3. Load **`jira`** — `$GENESIS_DIRECTORY/.genesis/skills/jira/SKILL.md` or `~/git_repos/the-genesis/.genesis/skills/jira/SKILL.md` for all Jira JQL and REST.
4. **Credentials:** `source` or load **`~/git_repos/10xProductivity/.env`** (or project `.env`) before `curl` / scripts. Never commit secrets.

---

## Cursor vs Claude Code

| Environment | Where to put generated files | How this skill is loaded |
|-------------|------------------------------|---------------------------|
| **Cursor** | Repo root: `colleagues/{slug}/` (e.g. 10xProductivity or the-genesis) | `.cursor/skills/colleague-distillation/SKILL.md` |
| **Claude Code** | Same `colleagues/{slug}/` under the active project | `.claude/skills/colleague-distillation/SKILL.md` |

Use the **same** slug and folder layout in both; only the skill *install path* differs.

---

## Slug rules

- **Slug** = unique directory name: `michael_donnelly`, `michael_donnelly_2`, … (ASCII, underscores).
- **Collisions:** Same slug **overwrites** an existing colleague folder. Disambiguate with `_2`, `_3`, or a distinct codename.
- Store display name and aliases in **`meta.json`**, not only in the slug.

---

## Phase 1 — Resolve identity

Before searching, pin **who** the colleague is:

1. **Active Directory** (if configured in tool_connections): resolve **email**, **manager chain**, **department** — use for Jira/Slack account mapping when IDs are unknown.
2. **Slack**: From `verified_connections.md`, use Slack API recipes to resolve **`@handle` → user id** (`U…`) for `from:@user` / `from:U…` search syntax.
3. **Jira**: Resolve **accountId** (assignee, reporter, comment author) via Jira user search API — see `jira` skill.

Record: `slack_user_id`, `jira_account_id`, `email`, `ad_cn` (as available).

---

## Phase 2 — Pull source material (priority order)

Gather **raw excerpts** (save under `colleagues/{slug}/knowledge/raw/` as `.md` or `.json` snippets) with **source + URL/ticket/channel + date** in each chunk header. Cap volume per source (e.g. last 90–180 days) unless the user asks for full history.

### Tier A — Highest signal for “how they work and sound”

| Source | What to fetch | Why |
|--------|----------------|-----|
| **Slack** | `search.messages`: `from:user`, date range, `in:#relevant-channels`; thread URLs they participated in | Tone, decisions, pushback, on-call voice |
| **Slack AI** (Slackbot DM) | Targeted questions: e.g. “Summarize how [Name] argues for design decisions in threads about [topic]” | Fast synthesis over large Slack corpus |
| **Jira** | JQL: `assignee`, `reporter`, `comment ~`, component/team filters; descriptions, comments, status transitions | Work scope, prioritization, written precision |
| **GHE** | PRs **authored**, **reviewed** (`/pulls`, review comments API); issues filed | Code review voice, technical standards |
| **Bitbucket Server** | Same pattern as GHE when Bitbucket Server is the primary Git host | Same |

### Tier B — Depth and standards

| Source | What to fetch | Why |
|--------|----------------|-----|
| **Confluence** | Pages **created by** or **substantially edited by** them (CQL / search); team runbooks they own | Long-form standards, architecture voice |
| **Notion** | Pages they authored or commented on | Long-form async thinking, project context |
| **SharePoint** | Docs and wikis they own or edited | Standards docs, team handbooks |

### Tier C — Optional / role-specific

| Source | When |
|--------|------|
| **Google Drive** | Docs/slides they own (if verified in `verified_connections.md`) |
| **PagerDuty** | Oncall/incident behavior |
| **Console / IAHub** | Release/ops ownership if building an ops-heavy persona |
| **Microsoft Teams / Outlook** | If verified — email/thread tone (handle consent carefully) |
| **Gmail (personal recipe)** | Only if user explicitly wants email and connection is verified |

### Tier D — Do not rely on for persona without extra care

- Raw **git blame** without PR context — noisy.
- **HR systems** — use only for title/team if needed, not personality inference.

---

## Phase 3 — Synthesize (work vs persona)

**Work (`work.md`):** Systems, stacks, coding/review conventions, doc habits, Jira/workflow patterns, incident/release behavior — cite **patterns**, not one-off jokes.

**Persona (`persona.md`):** Use a **layered** structure compatible with colleague-skill:

1. **Layer 0 — Hard rules** (non-negotiables: respect, no slurs, no real harassment simulation beyond professional friction the user explicitly asked for).
2. **Identity** — role, scope, team context.
3. **Expression** — vocabulary, sentence length, directness, humor.
4. **Decisions** — risk posture, escalation, “how they say no.”
5. **Interpersonal** — meetings, async, conflict.

**Grounding:** Prefer **quoted paraphrases** with source pointers; flag **low-confidence** traits when sample size is small.

---

## Phase 4 — Write artifacts

### `meta.json` (minimal)

```json
{
  "name": "Display Name",
  "slug": "michael_donnelly",
  "created_at": "<ISO8601 UTC>",
  "updated_at": "<ISO8601 UTC>",
  "version": "v1",
  "profile": {
    "company": "",
    "level": "",
    "role": "",
    "email": ""
  },
  "ids": {
    "slack_user_id": "",
    "jira_account_id": ""
  },
  "knowledge_sources": ["slack", "jira", "ghe"],
  "corrections_count": 0
}
```

### `SKILL.md` (invocable)

YAML frontmatter:

```yaml
---
name: colleague_{slug}
description: "<Name> — distilled work + persona (tool-sourced)."
user-invocable: true
---
```

Body: short intro + full `work.md` + full `persona.md` + **run rules**:

1. Persona decides attitude; work block executes the task.
2. Output matches persona expression.
3. Layer 0 never violated.

Optional: also write `work_skill.md` / `persona_skill.md` with names `colleague_{slug}_work` / `colleague_{slug}_persona` if your host expects split invocations (see colleague-skill `skill_writer.py`).

---

## Consent and safety

- Build skills only for **legitimate work purposes** and **policy-compliant** use of company tools.
- Do not exfiltrate **secrets**, **PII bundles**, or **restricted** content into `colleagues/` — redact tokens, customer data, and health/financial identifiers.
- When unsure whether content is allowed in a repo, **ask the user** before writing.

---

## Outputs checklist

- [ ] `colleagues/{slug}/` created with `knowledge/raw/` containing sourced excerpts
- [ ] `work.md` and `persona.md` complete
- [ ] `meta.json` with ids and source list
- [ ] `SKILL.md` merged and invocable
- [ ] User told how to invoke (`/{slug}` or host-specific command) and how to disambiguate duplicates (`_2`, `_3`)

---

## Related skills

- **`team_learner`** — team/domain bootstrap (similar tool sweep, different output shape).
- **`skill_creation`** — promote reusable methodology after validation.
- **`jira`**, **`tool_connections`** — all authenticated access.
