---
name: flow-cleanup
description: Trigger `/flow:cleanup`.
---

# flow-cleanup

## Trigger
- Primary: `/flow:cleanup`
- Text alias: `flow:cleanup`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/cleanup.md`

## Execution
1. Use this skill when the user invokes `/flow:cleanup` or explicitly asks for the flow `cleanup` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/cleanup.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
