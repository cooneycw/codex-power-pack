---
name: cicd-init
description: Trigger `/cicd:init`. Detect framework and generate/validate Makefile for CI/CD integration
---

# cicd-init

## Trigger
- Primary: `/cicd:init`
- Text alias: `cicd:init`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/init.md`

## Execution
1. Use this skill when the user invokes `/cicd:init` or explicitly asks for the `init` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/init.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
