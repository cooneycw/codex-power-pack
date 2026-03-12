# QA Trigger to Skill Map

This file maps QA testing triggers to Codex prompts and skill packages.

| Trigger | Prompt Entrypoint | Skill Package |
|---|---|---|
| `/qa:help` | `.codex/prompts/qa/help.md` | `.codex/skills/qa-help/SKILL.md` |
| `/qa:test` | `.codex/prompts/qa/test.md` | `.codex/skills/qa-test/SKILL.md` |

Canonical inventory: `.claude/commands/qa/*.md`, `.codex/prompts/qa/*.md`, and `.codex/skills/qa-*/`.
