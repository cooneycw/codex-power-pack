---
name: github-issue-list
description: Trigger `/github:issue-list`.
---

# github-issue-list

## Trigger
- Primary: `/github:issue-list`
- Text alias: `github:issue-list`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/github/issue-list.md`

## Execution
1. Use this skill when the user invokes `/github:issue-list` or explicitly asks for the GitHub `issue-list` workflow.
2. Follow the workflow steps in `.codex/prompts/github/issue-list.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
