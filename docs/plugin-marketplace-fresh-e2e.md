# Fresh Marketplace E2E Acceptance

This is the recorded #99 acceptance run on 2026-07-10. It used an isolated
`CODEX_HOME`; the temporary profile warning about helper aliases under `/tmp`
did not affect marketplace or plugin installation.

## Plugin install

```text
codex plugin marketplace add <codex-power-pack checkout> --json
codex plugin add project@codex-power-pack --json
codex plugin add spec@codex-power-pack --json
codex plugin add github@codex-power-pack --json
codex plugin add cxpp@codex-power-pack --json
```

All four packages reported `installed: true` and `enabled: true` from the
isolated profile. `cxpp:init` remains consent-first; it was not used to write
host configuration during this local acceptance run.

## Project scaffold

The installed project workflow created a throwaway `e2e-demo` with:

- `AGENTS.md`, Makefile, `.codex/cicd.yml`, and a gitleaks-first GitHub Actions
  workflow;
- a Python package and pytest smoke test;
- a local Git repository and initial commit using an explicit local author;
- `uv sync --extra dev` followed by `make verify`.

The verification result was clean: ruff, pytest (1 test), and mypy all passed.
The initial commit subject was `Initial Codex project scaffold`.

## Spec task sync

The packaged `spec-sync` helper first dry-ran the two task fixture entries. With
the confirmed target `cooneycw/codex-power-pack`, it then created #122 (`T901`)
and #123 (`T902`) label-free through `gh`. Both temporary acceptance issues were
closed immediately after creation. A final dry run skipped both identifiers,
proving idempotency across closed issues without leaving test work pending.

No secrets were supplied or printed during the run.
