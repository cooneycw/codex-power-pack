---
name: github-issue-update
description: Trigger `/github:issue-update`.
---

# github-issue-update

## Trigger
- Primary: `/github:issue-update`
- Text alias: `github:issue-update`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/github/issue-update.md`

## Execution
1. Use this skill when the user invokes `/github:issue-update` or explicitly asks for the GitHub `issue-update` workflow.
2. Follow the workflow steps in `.codex/prompts/github/issue-update.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
