---
name: agents-md-help
description: Trigger `/agents-md:help` to show AGENTS.md governance command guidance.
---

# agents-md-help

## Trigger
- Primary: `/agents-md:help`
- Text alias: `agents-md:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/agents-md/help.md`

## Execution
1. Use this skill when the user asks for AGENTS.md governance command help.
2. Follow `.codex/prompts/agents-md/help.md` as the authoritative runbook.
3. Keep guidance Codex-native and focused on `AGENTS.md` and `.codex/*` paths.
