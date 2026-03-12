---
name: github-issue-close
description: Trigger `/github:issue-close`.
---

# github-issue-close

## Trigger
- Primary: `/github:issue-close`
- Text alias: `github:issue-close`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/github/issue-close.md`

## Execution
1. Use this skill when the user invokes `/github:issue-close` or explicitly asks for the GitHub `issue-close` workflow.
2. Follow the workflow steps in `.codex/prompts/github/issue-close.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
