---
name: cicd-infra-pipeline
description: Trigger `/cicd:infra-pipeline`. Generate CI/CD pipelines for infrastructure tiers with approval gates
---

# cicd-infra-pipeline

## Trigger
- Primary: `/cicd:infra-pipeline`
- Text alias: `cicd:infra-pipeline`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/infra-pipeline.md`

## Execution
1. Use this skill when the user invokes `/cicd:infra-pipeline` or explicitly asks for the `infra-pipeline` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/infra-pipeline.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
