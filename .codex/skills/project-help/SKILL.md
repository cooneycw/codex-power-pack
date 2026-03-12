---
name: project-help
description: Trigger `/project:help`.
---

# project-help

## Trigger
- Primary: `/project:help`
- Text alias: `project:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/project/help.md`

## Execution
1. Use this skill when the user invokes `/project:help` or explicitly asks for the project `help` workflow.
2. Follow the workflow steps in `.codex/prompts/project/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
