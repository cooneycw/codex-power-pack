# Skill Contract Baseline

> Captured 2026-08-06T19:21:59Z from `b98934be8f8a654d65d1728207fadc1597ad8c7c` for issue #157.
> This report records evidence and dispositions; it does not change skill runtime behavior.

## Inventory

| Surface | Count |
|---|---:|
| Source skills | 83 |
| Packaged skills | 73 |
| Unpackaged source skills | 10 |
| Marketplace plugins | 16 |
| Implicitly eligible packaged skills | 73 |
| Extracted packaged-Markdown references | 697 |
| Unexplained reference occurrences | 430 |

The machine-readable source of truth is [`.agents/skill-contracts.json`](../.agents/skill-contracts.json).

## Full-Suite Prompt Capture

An isolated `codex-cli 0.146.1` full-suite install exposed 78 entries: 73 CxPP and 5 system entries. Skill entry lines consumed 20,640 bytes; the framed Skills section consumed 21,127 bytes.

Prompt presence passed. Direct recall, indirect recall, and negative precision remain explicitly unmeasured until issue #161 supplies the bounded live evaluator; this baseline does not turn absence of measurement into green.

## Unpackaged Skills

| Skill | Owner | Disposition | Review by |
|---|---|---|---|
| `browser-help` | Wave 7 Stage 3 (#160) | Package, replace with qa-help and upstream Playwright MCP guidance, or record a reviewed exclusion. | 2026-09-30 |
| `browser-session` | Wave 7 Stage 3 (#160) | Package, replace with qa-test and upstream Playwright MCP sessions, or record a reviewed exclusion. | 2026-09-30 |
| `cicd-woodpecker` | Wave 7 Stage 3 (#160) | Package, replace with the packaged cicd-pipeline and woodpecker skills, or record a reviewed exclusion. | 2026-09-30 |
| `cpp-dockers` | Wave 7 Stage 3 (#160) | Package, replace with CxPP host-status guidance, or record a reviewed exclusion. | 2026-09-30 |
| `cpp-happy-check` | Wave 7 Stage 3 (#160) | Package, replace with CxPP status guidance, or record a reviewed exclusion. | 2026-09-30 |
| `cpp-help` | Wave 7 Stage 3 (#160) | Package, replace with the packaged family help skills, or record a reviewed exclusion. | 2026-09-30 |
| `cpp-load-best-practices` | Wave 7 Stage 3 (#160) | Package, replace with focused Codex documentation, or record a reviewed exclusion. | 2026-09-30 |
| `cpp-load-mcp-docs` | Wave 7 Stage 3 (#160) | Package, replace with docs/HOST_MANAGED.md and second-opinion-help, or record a reviewed exclusion. | 2026-09-30 |
| `flow-auto_codex` | Wave 7 Stage 3 (#160) | Package, replace with flow-auto plus claude-code-review escalation, or record a reviewed exclusion. | 2026-09-30 |
| `flow-repair` | Wave 7 Stage 3 (#160) | Package, replace with plugin-bundled flow helpers and flow-doctor, or record a reviewed exclusion. | 2026-09-30 |

## Reference Classification

| Classification | Occurrences | Meaning |
|---|---:|---|
| Resolvable | 36 | Explicit `$skill-name` resolves to a packaged skill. |
| Native | 17 | Supported Codex host command. |
| Adapted | 214 | The packaged skill carries an explicit Codex harness adaptation. |
| Unexplained | 430 | Scheduled for invocation normalization or semantic review. |

Unexplained occurrences are grouped below so every gap has one owner and disposition without hiding its evidence locations.

| Token | Evidence count | Owner | Disposition | Review by |
|---|---:|---|---|---|
| `/plugin` | 4 | Wave 7 Stage 3 (#160) | Resolve to a packaged/native capability, add a narrow adaptation, or record a reviewed exclusion. | 2026-09-30 |
| `.claude/` | 38 | Wave 7 Stage 3 (#160) | Resolve to a packaged/native capability, add a narrow adaptation, or record a reviewed exclusion. | 2026-09-30 |
| `/agents-md:help` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/agents-md:lint` | 6 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-check` | 11 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-container` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-health` | 14 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-infra-discover` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-infra-init` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-infra-pipeline` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-init` | 15 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-pipeline` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-smoke` | 12 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-verify` | 10 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cicd-woodpecker` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/codex:code_review` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cpp-load-mcp-docs` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cpp:init` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cpp:update` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cxpp:init` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cxpp:status` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/cxpp:update` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/documentation-c4` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/documentation-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/documentation-pptx` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/evaluate-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/evaluate-issue` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-auto` | 31 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-auto_codex` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-check` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-cleanup` | 6 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-deploy` | 26 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-doctor` | 7 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-eli5` | 6 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-finish` | 37 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-merge` | 21 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-repair` | 17 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-start` | 20 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-status` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/flow-sync` | 5 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/github-issue-close` | 6 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/github-issue-create` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/github-issue-list` | 3 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/github-issue-update` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/github-issue-view` | 4 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/project-init` | 3 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/project-lite` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/project-next` | 3 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/second-opinion-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/second-opinion-models` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/second-opinion-start` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-delete` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-get` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-list` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-rotate` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-run` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-set` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-ui` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/secrets-validate` | 2 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/security-explain` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/security-scan` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/self-improvement-deployment` | 9 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/self-improvement-help` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/self-improvement-retro` | 10 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |
| `/spec:adopt` | 1 | Wave 7 Stage 2 (#159) | Replace legacy slash-style skill invocation with `$skill-name` or `/skills`. | 2026-09-30 |

## Known Failures and Owners

| ID | Finding | Owner | Disposition |
|---|---|---|---|
| KF-001 | Ten source skills have no plugin package or marketplace publication path. | Wave 7 Stage 3 (#160) | Package, replace, or explicitly retire every source-only skill. |
| KF-002 | All 73 packaged skills are implicitly eligible without evidence that the set meets an ambiguity or metadata budget. | Wave 7 Stage 2 (#159) | Curate implicit entrypoints using the versioned evaluation cases. |
| KF-003 | Packaged guidance still presents historical slash-style skill commands that Codex does not expose as first-class custom commands. | Wave 7 Stage 2 (#159) | Normalize user-facing invocation to `$skill-name` and `/skills`. |
| KF-004 | Packaged Markdown contains host-specific commands and `.claude/` runtime paths whose safety currently depends on prose adaptations. | Wave 7 Stage 3 (#160) | Validate each reference semantically and repair or time-bound every unexplained occurrence. |
| KF-005 | Direct recall, indirect recall, negative precision, procedure adherence, and output fidelity have no reproducible measured baseline. | Wave 7 Stage 4 (#161) | Run the cases through the bounded live evaluation lane and publish aggregate results. |

## Evaluation Contract

[`.agents/skill-evaluation-cases.schema.json`](../.agents/skill-evaluation-cases.schema.json) versions direct, indirect, negative, incomplete, and edge cases. [`.agents/skill-evaluation-cases.json`](../.agents/skill-evaluation-cases.json) preserves this capture, including honest `not_run` activation results for Stage 4 to replace with measurements.

## Reproduction

```bash
uv run --extra dev python scripts/skill_contract_baseline.py --check
```

Use `--write` only when intentionally reconciling the current source/package/reference manifest. Do not rewrite the dated evaluation capture when runtime behavior changes; add a new capture instead.
