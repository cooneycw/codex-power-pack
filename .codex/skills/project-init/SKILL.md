---
name: project-init
description: Trigger `/project:init`.
---

# project-init

## Trigger
- Primary: `/project:init`
- Text alias: `project:init`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/project/init.md`

## Execution
1. Use this skill when the user invokes `/project:init` or explicitly asks for the project `init` workflow.
2. Follow the workflow steps in `.codex/prompts/project/init.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
