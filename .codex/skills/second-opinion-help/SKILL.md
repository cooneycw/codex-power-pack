---
name: second-opinion-help
description: Trigger `/second-opinion:help`.
---

# second-opinion-help

## Trigger
- Primary: `/second-opinion:help`
- Text alias: `second-opinion:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/second-opinion/help.md`

## Execution
1. Use this skill when the user invokes `/second-opinion:help` or explicitly asks for the second-opinion `help` workflow.
2. Follow the workflow steps in `.codex/prompts/second-opinion/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
