---
name: qa-test
description: Trigger `/qa:test`. Run automated QA testing workflow with Playwright MCP and GitHub issue logging.
---

# qa-test

## Trigger
- Primary: `/qa:test`
- Text alias: `qa:test`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/qa/test.md`

## Execution
1. Use this skill when the user invokes `/qa:test` or explicitly asks for the QA `test` workflow.
2. Follow the workflow steps in `.codex/prompts/qa/test.md` as the authoritative runbook.
3. Keep Codex-native paths and wording (`AGENTS.md`, `.codex/*`) when presenting or adapting instructions.
4. Preserve confirmation steps before creating GitHub issues or changing external systems.
