---
name: github-help
description: Trigger `/github:help`.
---

# github-help

## Trigger
- Primary: `/github:help`
- Text alias: `github:help`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/github/help.md`

## Execution
1. Use this skill when the user invokes `/github:help` or explicitly asks for the GitHub `help` workflow.
2. Follow the workflow steps in `.codex/prompts/github/help.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
