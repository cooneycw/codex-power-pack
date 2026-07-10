# AGENTS.md Lint Dogfood

Issue #90 requires the Codex-native `$agents-md-lint` workflow to inspect this
repository and an external project. The run below follows the skill rubric on
2026-07-10 and is read-only.

## Codex Power Pack

| Category | Status | Evidence |
|---|---|---|
| CI/CD protocol | PASS | `AGENTS.md` makes Make targets canonical. |
| Runtime boundary | PASS | It states that MCP services and deployment entrypoints are external/host-managed. |
| Troubleshooting protocol | WARN | It requires `make verify` after changes; add an explicit root-cause/no-bypass directive when the next governance edit is made. |
| Quality gates | PASS | It names `make lint`, `make test`, `make typecheck`, and `make verify`. |
| Docker conventions | WARN | A retained Woodpecker compose fixture exists; its documentation should explicitly say it is a fixture, not a repo-owned runtime. |
| Available commands | PASS | The Make targets are listed in the conventions. |
| Secret handling | PASS | The first core directive prohibits raw secret output. |

Result: **NEEDS ATTENTION**. The lint correctly distinguishes the active
host-managed runtime boundary from a checked-in fixture and produces targeted,
non-destructive suggestions.

## External project: `td-agentic`

| Category | Status | Evidence |
|---|---|---|
| CI/CD protocol | PASS | `AGENTS.md` directs all CI operations through Make. |
| Runtime boundary | FAIL | No ownership boundary for host services or credentials is documented. |
| Troubleshooting protocol | PASS | It directs maintainers to inspect the failing rule/test in isolation. |
| Quality gates | PASS | It names lint, test, and verify. |
| Docker conventions | SKIP | No Docker files are present. |
| Available commands | PASS | A commands table is present. |
| Secret handling | WARN | No explicit secret-output prohibition is present. |

Result: **NEEDS ATTENTION**. The suggested follow-up is to add the runtime
boundary and secret-handling blocks from `$agents-md-lint`; no external files
were modified during this dogfood run.
