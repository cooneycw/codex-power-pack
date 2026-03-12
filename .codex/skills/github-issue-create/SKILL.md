---
name: github-issue-create
description: Trigger `/github:issue-create`.
---

# github-issue-create

## Trigger
- Primary: `/github:issue-create`
- Text alias: `github:issue-create`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/github/issue-create.md`

## Execution
1. Use this skill when the user invokes `/github:issue-create` or explicitly asks for the GitHub `issue-create` workflow.
2. Follow the workflow steps in `.codex/prompts/github/issue-create.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
