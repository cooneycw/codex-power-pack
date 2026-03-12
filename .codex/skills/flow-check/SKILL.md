---
name: flow-check
description: Trigger `/flow:check`.
---

# flow-check

## Trigger
- Primary: `/flow:check`
- Text alias: `flow:check`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/check.md`

## Execution
1. Use this skill when the user invokes `/flow:check` or explicitly asks for the flow `check` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/check.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
