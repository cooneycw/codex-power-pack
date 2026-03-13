# Spec Trigger to Skill Map

This file maps spec triggers to Codex prompts and skill packages.

| Trigger | Prompt Entrypoint | Skill Package |
|---|---|---|
| `/spec:create` | `.codex/prompts/spec/create.md` | `.codex/skills/spec-create/SKILL.md` |
| `/spec:help` | `.codex/prompts/spec/help.md` | `.codex/skills/spec-help/SKILL.md` |
| `/spec:init` | `.codex/prompts/spec/init.md` | `.codex/skills/spec-init/SKILL.md` |
| `/spec:status` | `.codex/prompts/spec/status.md` | `.codex/skills/spec-status/SKILL.md` |
| `/spec:sync` | `.codex/prompts/spec/sync.md` | `.codex/skills/spec-sync/SKILL.md` |

Canonical inventory: `.claude/commands/spec/*.md`, `.codex/prompts/spec/*.md`, and `.codex/skills/spec-*/`.
