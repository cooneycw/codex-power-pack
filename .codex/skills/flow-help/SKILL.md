---
name: flow-help
description: Trigger `/flow:help`.
---

# flow-help

## Trigger
- Primary: `/flow:help`
- Text alias: `flow:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/help.md`

## Execution
1. Use this skill when the user invokes `/flow:help` or explicitly asks for the flow `help` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
