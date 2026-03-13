---
name: documentation-pptx
description: Trigger `/documentation:pptx`.
---

# documentation-pptx

## Trigger
- Primary: `/documentation:pptx`
- Text alias: `documentation:pptx`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/documentation/pptx.md`

## Execution
1. Use this skill when the user invokes `/documentation:pptx` or explicitly asks for the documentation `pptx` workflow.
2. Follow the workflow steps in `.codex/prompts/documentation/pptx.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
