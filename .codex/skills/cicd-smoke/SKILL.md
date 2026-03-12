---
name: cicd-smoke
description: Trigger `/cicd:smoke`. Run smoke tests from cicd.yml configuration
---

# cicd-smoke

## Trigger
- Primary: `/cicd:smoke`
- Text alias: `cicd:smoke`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/smoke.md`

## Execution
1. Use this skill when the user invokes `/cicd:smoke` or explicitly asks for the `smoke` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/smoke.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
