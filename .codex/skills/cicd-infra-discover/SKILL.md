---
name: cicd-infra-discover
description: Trigger `/cicd:infra-discover`. Generate cloud resource discovery script for IaC import
---

# cicd-infra-discover

## Trigger
- Primary: `/cicd:infra-discover`
- Text alias: `cicd:infra-discover`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/infra-discover.md`

## Execution
1. Use this skill when the user invokes `/cicd:infra-discover` or explicitly asks for the `infra-discover` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/infra-discover.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
