---
name: second-opinion-models
description: Trigger `/second-opinion:models`.
---

# second-opinion-models

## Trigger
- Primary: `/second-opinion:models`
- Text alias: `second-opinion:models`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/second-opinion/models.md`

## Execution
1. Use this skill when the user invokes `/second-opinion:models` or explicitly asks for the second-opinion `models` workflow.
2. Follow the workflow steps in `.codex/prompts/second-opinion/models.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
