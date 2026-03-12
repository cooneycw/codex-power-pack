---
name: qa-help
description: Trigger `/qa:help` to show QA command guidance.
---

# qa-help

## Trigger
- Primary: `/qa:help`
- Text alias: `qa:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/qa/help.md`

## Execution
1. Use this skill when the user asks for QA command help.
2. Follow `.codex/prompts/qa/help.md` as the authoritative runbook.
3. Keep guidance Codex-native and focused on `.codex/*` paths.
