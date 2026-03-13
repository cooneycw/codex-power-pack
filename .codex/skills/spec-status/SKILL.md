---
name: spec-status
description: Trigger `/spec:status`.
---

# spec-status

## Trigger
- Primary: `/spec:status`
- Text alias: `spec:status`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/spec/status.md`

## Execution
1. Use this skill when the user invokes `/spec:status` or explicitly asks for the spec `status` workflow.
2. Follow the workflow steps in `.codex/prompts/spec/status.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
