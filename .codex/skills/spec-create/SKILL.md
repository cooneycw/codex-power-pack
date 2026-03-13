---
name: spec-create
description: Trigger `/spec:create`.
---

# spec-create

## Trigger
- Primary: `/spec:create`
- Text alias: `spec:create`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/spec/create.md`

## Execution
1. Use this skill when the user invokes `/spec:create` or explicitly asks for the spec `create` workflow.
2. Follow the workflow steps in `.codex/prompts/spec/create.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
