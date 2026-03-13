---
name: spec-init
description: Trigger `/spec:init`.
---

# spec-init

## Trigger
- Primary: `/spec:init`
- Text alias: `spec:init`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/spec/init.md`

## Execution
1. Use this skill when the user invokes `/spec:init` or explicitly asks for the spec `init` workflow.
2. Follow the workflow steps in `.codex/prompts/spec/init.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
