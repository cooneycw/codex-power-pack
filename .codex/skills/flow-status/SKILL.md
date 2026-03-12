---
name: flow-status
description: Trigger `/flow:status`.
---

# flow-status

## Trigger
- Primary: `/flow:status`
- Text alias: `flow:status`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/status.md`

## Execution
1. Use this skill when the user invokes `/flow:status` or explicitly asks for the flow `status` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/status.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
