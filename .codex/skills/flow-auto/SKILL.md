---
name: flow-auto
description: Trigger `/flow:auto`.
---

# flow-auto

## Trigger
- Primary: `/flow:auto`
- Text alias: `flow:auto`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/auto.md`

## Execution
1. Use this skill when the user invokes `/flow:auto` or explicitly asks for the flow `auto` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/auto.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
