---
name: flow-merge
description: Trigger `/flow:merge`.
---

# flow-merge

## Trigger
- Primary: `/flow:merge`
- Text alias: `flow:merge`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/merge.md`

## Execution
1. Use this skill when the user invokes `/flow:merge` or explicitly asks for the flow `merge` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/merge.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
