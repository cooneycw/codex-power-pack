---
name: spec-help
description: Trigger `/spec:help`.
---

# spec-help

## Trigger
- Primary: `/spec:help`
- Text alias: `spec:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/spec/help.md`

## Execution
1. Use this skill when the user invokes `/spec:help` or explicitly asks for the spec `help` workflow.
2. Follow the workflow steps in `.codex/prompts/spec/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
