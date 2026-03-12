# Project Trigger to Skill Map

This file maps project command triggers to Codex prompts and skill packages.

| Trigger | Prompt Entrypoint | Skill Package |
|---|---|---|
| `/project:help` | `.codex/prompts/project/help.md` | `.codex/skills/project-help/SKILL.md` |
| `/project:init` | `.codex/prompts/project/init.md` | `.codex/skills/project-init/SKILL.md` |

Canonical inventory: `.claude/commands/project/*.md`, `.codex/prompts/project/*.md`, and `.codex/skills/project-*/`.
