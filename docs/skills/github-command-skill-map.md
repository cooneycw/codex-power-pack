# GitHub Trigger to Skill Map

This file maps GitHub issue-management triggers to Codex prompts and skill packages.

| Trigger | Prompt Entrypoint | Skill Package |
|---|---|---|
| `/github:help` | `.codex/prompts/github/help.md` | `.codex/skills/github-help/SKILL.md` |
| `/github:issue-close` | `.codex/prompts/github/issue-close.md` | `.codex/skills/github-issue-close/SKILL.md` |
| `/github:issue-create` | `.codex/prompts/github/issue-create.md` | `.codex/skills/github-issue-create/SKILL.md` |
| `/github:issue-list` | `.codex/prompts/github/issue-list.md` | `.codex/skills/github-issue-list/SKILL.md` |
| `/github:issue-update` | `.codex/prompts/github/issue-update.md` | `.codex/skills/github-issue-update/SKILL.md` |
| `/github:issue-view` | `.codex/prompts/github/issue-view.md` | `.codex/skills/github-issue-view/SKILL.md` |

Canonical inventory: `.claude/commands/github/*.md`, `.codex/prompts/github/*.md`, and `.codex/skills/github-*/`.
