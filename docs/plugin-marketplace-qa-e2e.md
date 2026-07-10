# QA Plugin E2E Transcript

This transcript dogfoods the `$qa-test` local fallback without relying on a
host-specific Playwright MCP installation.

## Fixture

`tests/fixtures/qa-dogfood/index.html` exposes a labelled form, a submit action,
and an ARIA live result. `tests/qa-dogfood.spec.cjs` verifies page navigation,
semantic form interaction, rendered result, and an empty browser console-error
collection.

## Run (2026-07-10)

```text
$ python3 -m http.server 4173 --directory tests/fixtures/qa-dogfood
$ npm install --prefix /tmp/cxpp-qa-dogfood --no-save @playwright/test@1.61.1
$ NODE_PATH=/tmp/cxpp-qa-dogfood/node_modules \
    /tmp/cxpp-qa-dogfood/node_modules/.bin/playwright \
    test tests/qa-dogfood.spec.cjs --reporter=line

Running 1 test using 1 worker
  1 passed
```

The environment had no `playwright` MCP pointer, so this is the documented
fallback path. A normal installed plugin session uses the native
`@playwright/mcp` server and follows the same navigation, interaction, and
console-evidence sequence.
