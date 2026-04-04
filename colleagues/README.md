# Colleague skills (generated)

Distilled **work + persona** skills land here when you run the **colleague-distillation** flow:

- `.cursor/skills/colleague-distillation/SKILL.md` (Cursor)
- `.claude/skills/colleague-distillation/SKILL.md` (Claude Code)

Canonical instructions: `~/git_repos/the-genesis/.genesis/skills/colleague-distillation/SKILL.md`.

## Layout (per person)

```
colleagues/{slug}/
  SKILL.md          # merged invocable skill (name: colleague_{slug})
  work.md
  persona.md
  meta.json
  knowledge/
    raw/            # optional: sourced excerpts (consider gitignoring)
  versions/         # optional: if you add versioning like colleague-skill
```

## Slugs

Use unique folder names: `michael_donnelly`, `michael_donnelly_2`, … Same slug overwrites an existing tree.

## Git

Raw exports may include internal content. Add patterns to `.gitignore` if you do not want them committed (e.g. `colleagues/*/knowledge/raw/`).
