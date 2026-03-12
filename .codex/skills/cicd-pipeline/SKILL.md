---
name: cicd-pipeline
description: Trigger `/cicd:pipeline`. Generate GitHub Actions CI/CD workflows
---

# cicd-pipeline

## Trigger
- Primary: `/cicd:pipeline`
- Text alias: `cicd:pipeline`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/pipeline.md`

## Execution
1. Use this skill when the user invokes `/cicd:pipeline` or explicitly asks for the `pipeline` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/pipeline.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
