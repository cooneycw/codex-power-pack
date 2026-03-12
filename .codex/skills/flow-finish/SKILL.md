---
name: flow-finish
description: Trigger `/flow:finish`.
---

# flow-finish

## Trigger
- Primary: `/flow:finish`
- Text alias: `flow:finish`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/finish.md`

## Execution
1. Use this skill when the user invokes `/flow:finish` or explicitly asks for the flow `finish` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/finish.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
