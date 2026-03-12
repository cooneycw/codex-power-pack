---
name: cicd-help
description: Trigger `/cicd:help`. Run the /cicd:help workflow for Codex Power Pack CI/CD automation.
---

# cicd-help

## Trigger
- Primary: `/cicd:help`
- Text alias: `cicd:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/cicd/help.md`

## Execution
1. Use this skill when the user invokes `/cicd:help` or explicitly asks for the `help` CI/CD workflow.
2. Follow the workflow steps in `.codex/prompts/cicd/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
