---
name: flow-sync
description: Trigger `/flow:sync`.
---

# flow-sync

## Trigger
- Primary: `/flow:sync`
- Text alias: `flow:sync`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/sync.md`

## Execution
1. Use this skill when the user invokes `/flow:sync` or explicitly asks for the flow `sync` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/sync.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
