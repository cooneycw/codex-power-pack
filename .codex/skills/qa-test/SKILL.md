---
name: "qa-test"
description: "Test a web page through native Playwright MCP and report reproducible findings"
---

# QA Test

Use the host-managed `@playwright/mcp` server for browser interaction. This
skill does not start a browser service, retain credentials, or create GitHub
issues without confirmation.

## Procedure

1. Resolve the target from an explicit URL or `.codex/qa.yml`. The optional
   config contains `project.url`, `project.repository`, shortcuts, and named
   `test_areas`; if it is absent, ask for a URL and test the page generically.
2. Confirm Playwright is configured with `codex mcp get playwright`. If it is
   not available, report the host prerequisite and offer the local Playwright
   CLI fallback; do not install a global browser dependency silently.
3. Navigate with the native Playwright MCP tools, capture the accessibility
   tree, exercise the requested form/navigation behavior, and collect browser
   console errors. Prefer semantic locators over brittle CSS selectors.
4. Report each finding with URL, reproducible steps, expected/actual behavior,
   browser/console evidence, and severity. Mask credentials, tokens, and any
   sensitive form input.
5. Before creating a GitHub issue, show the proposed title/body/repository and
   ask for explicit confirmation. Use `$github-issue-create` only after that
   confirmation.

## Local CLI Fallback

For a local fixture or when MCP is intentionally unavailable, run a checked-in
Playwright test using a temporary dependency directory, then remove that
directory after the run:

```bash
python3 -m http.server 4173 --directory tests/fixtures/qa-dogfood
npm install --prefix /tmp/cxpp-qa --no-save @playwright/test
NODE_PATH=/tmp/cxpp-qa/node_modules /tmp/cxpp-qa/node_modules/.bin/playwright \
  test tests/qa-dogfood.spec.cjs --reporter=line
```

The test must exercise navigation, at least one interaction, and console-error
collection. This fallback is a local test runner, not a replacement for the
native MCP workflow.
