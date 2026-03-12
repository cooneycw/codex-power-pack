# Flow Trigger to Skill Map

This file maps flow triggers to Codex prompts and skill packages.

| Trigger | Prompt Entrypoint | Skill Package |
|---|---|---|
| `/flow:auto` | `.codex/prompts/flow/auto.md` | `.codex/skills/flow-auto/SKILL.md` |
| `/flow:check` | `.codex/prompts/flow/check.md` | `.codex/skills/flow-check/SKILL.md` |
| `/flow:cleanup` | `.codex/prompts/flow/cleanup.md` | `.codex/skills/flow-cleanup/SKILL.md` |
| `/flow:deploy` | `.codex/prompts/flow/deploy.md` | `.codex/skills/flow-deploy/SKILL.md` |
| `/flow:doctor` | `.codex/prompts/flow/doctor.md` | `.codex/skills/flow-doctor/SKILL.md` |
| `/flow:finish` | `.codex/prompts/flow/finish.md` | `.codex/skills/flow-finish/SKILL.md` |
| `/flow:help` | `.codex/prompts/flow/help.md` | `.codex/skills/flow-help/SKILL.md` |
| `/flow:merge` | `.codex/prompts/flow/merge.md` | `.codex/skills/flow-merge/SKILL.md` |
| `/flow:start` | `.codex/prompts/flow/start.md` | `.codex/skills/flow-start/SKILL.md` |
| `/flow:status` | `.codex/prompts/flow/status.md` | `.codex/skills/flow-status/SKILL.md` |
| `/flow:sync` | `.codex/prompts/flow/sync.md` | `.codex/skills/flow-sync/SKILL.md` |

Canonical inventory: `.claude/commands/flow/*.md`, `.codex/prompts/flow/*.md`, and `.codex/skills/flow-*/`.
