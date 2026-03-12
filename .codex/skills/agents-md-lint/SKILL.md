---
name: agents-md-lint
description: Trigger `/agents-md:lint` to audit AGENTS.md governance directives.
---

# agents-md-lint

## Trigger
- Primary: `/agents-md:lint`
- Text alias: `agents-md:lint`

## Source Mapping
- Prompt entrypoint: `.codex/prompts/agents-md/lint.md`

## Execution
1. Use this skill when the user asks to lint or audit `AGENTS.md`.
2. Follow `.codex/prompts/agents-md/lint.md` as the authoritative runbook.
3. Keep outputs actionable with clear PASS/FAIL/WARN criteria and concrete remediation blocks.
4. Only modify `AGENTS.md` after explicit user confirmation.
