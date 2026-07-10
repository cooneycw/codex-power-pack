---
name: "qa-help"
description: "Explain Codex-native web QA with Playwright MCP"
---

# QA Help

`$qa-test` performs browser QA through native `@playwright/mcp`.

- Pass a URL directly for an exploratory test.
- Store repeatable targets and checklists in `.codex/qa.yml`.
- Use semantic browser locators, inspect console errors, and record reproducible
  evidence rather than reporting an unsupported visual impression.
- Creating a bug issue is opt-in: `$qa-test` shows the proposed issue before
  using the repository-aware `$github-issue-create` skill.

If Playwright MCP is unavailable, configure the host-managed pointer with
`$cxpp-init` or use the documented local CLI fallback. Neither path starts or
deploys a browser service from this repository.
