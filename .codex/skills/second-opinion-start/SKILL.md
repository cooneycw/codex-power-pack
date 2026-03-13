---
name: second-opinion-start
description: Trigger `/second-opinion:start`.
---

# second-opinion-start

## Trigger
- Primary: `/second-opinion:start`
- Text alias: `second-opinion:start`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/second-opinion/start.md`

## Execution
1. Use this skill when the user invokes `/second-opinion:start` or explicitly asks for the second-opinion `start` workflow.
2. Follow the workflow steps in `.codex/prompts/second-opinion/start.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
