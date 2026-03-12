---
name: cicd-infra-init
description: Trigger `/cicd:infra-init`. Scaffold IaC directory with tiered structure (foundation/platform/app)
---

# cicd-infra-init

## Trigger
- Primary: `/cicd:infra-init`
- Text alias: `cicd:infra-init`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/infra-init.md`

## Execution
1. Use this skill when the user invokes `/cicd:infra-init` or explicitly asks for the `infra-init` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/infra-init.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
