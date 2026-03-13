---
name: documentation-help
description: Trigger `/documentation:help`.
---

# documentation-help

## Trigger
- Primary: `/documentation:help`
- Text alias: `documentation:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/documentation/help.md`

## Execution
1. Use this skill when the user invokes `/documentation:help` or explicitly asks for the documentation `help` workflow.
2. Follow the workflow steps in `.codex/prompts/documentation/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
