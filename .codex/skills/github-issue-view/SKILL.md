---
name: github-issue-view
description: Trigger `/github:issue-view`.
---

# github-issue-view

## Trigger
- Primary: `/github:issue-view`
- Text alias: `github:issue-view`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/github/issue-view.md`

## Execution
1. Use this skill when the user invokes `/github:issue-view` or explicitly asks for the GitHub `issue-view` workflow.
2. Follow the workflow steps in `.codex/prompts/github/issue-view.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
