---
name: spec-sync
description: Trigger `/spec:sync`.
---

# spec-sync

## Trigger
- Primary: `/spec:sync`
- Text alias: `spec:sync`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/spec/sync.md`

## Execution
1. Use this skill when the user invokes `/spec:sync` or explicitly asks for the spec `sync` workflow.
2. Follow the workflow steps in `.codex/prompts/spec/sync.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
