---
name: documentation-c4
description: Trigger `/documentation:c4`.
---

# documentation-c4

## Trigger
- Primary: `/documentation:c4`
- Text alias: `documentation:c4`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/documentation/c4.md`

## Execution
1. Use this skill when the user invokes `/documentation:c4` or explicitly asks for the documentation `c4` workflow.
2. Follow the workflow steps in `.codex/prompts/documentation/c4.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
