---
name: flow-start
description: Trigger `/flow:start`.
---

# flow-start

## Trigger
- Primary: `/flow:start`
- Text alias: `flow:start`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/start.md`

## Execution
1. Use this skill when the user invokes `/flow:start` or explicitly asks for the flow `start` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/start.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
