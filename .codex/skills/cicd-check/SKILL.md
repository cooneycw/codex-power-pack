---
name: cicd-check
description: Trigger `/cicd:check`. Validate Makefile against CPP standards
---

# cicd-check

## Trigger
- Primary: `/cicd:check`
- Text alias: `cicd:check`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/check.md`

## Execution
1. Use this skill when the user invokes `/cicd:check` or explicitly asks for the `check` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/check.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
