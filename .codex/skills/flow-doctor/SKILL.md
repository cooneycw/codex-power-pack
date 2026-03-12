---
name: flow-doctor
description: Trigger `/flow:doctor`.
---

# flow-doctor

## Trigger
- Primary: `/flow:doctor`
- Text alias: `flow:doctor`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/doctor.md`

## Execution
1. Use this skill when the user invokes `/flow:doctor` or explicitly asks for the flow `doctor` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/doctor.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
