---
name: cicd-health
description: Trigger `/cicd:health`. Run health checks against configured endpoints and processes
---

# cicd-health

## Trigger
- Primary: `/cicd:health`
- Text alias: `cicd:health`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/health.md`

## Execution
1. Use this skill when the user invokes `/cicd:health` or explicitly asks for the `health` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/health.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
