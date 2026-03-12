---
name: cicd-container
description: Trigger `/cicd:container`. Run the /cicd:container workflow for Codex Power Pack CI/CD automation.
---

# cicd-container

## Trigger
- Primary: `/cicd:container`
- Text alias: `cicd:container`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/container.md`

## Execution
1. Use this skill when the user invokes `/cicd:container` or explicitly asks for the `container` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/container.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
