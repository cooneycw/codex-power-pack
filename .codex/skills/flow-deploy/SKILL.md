---
name: flow-deploy
description: Trigger `/flow:deploy`.
---

# flow-deploy

## Trigger
- Primary: `/flow:deploy`
- Text alias: `flow:deploy`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/flow/deploy.md`

## Execution
1. Use this skill when the user invokes `/flow:deploy` or explicitly asks for the flow `deploy` workflow.
2. Follow the workflow steps in `.codex/prompts/flow/deploy.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before any overwrite or destructive action.
