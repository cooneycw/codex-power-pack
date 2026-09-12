# Skill Contract Baseline

> Captured 2026-08-06T19:21:59Z from `b98934be8f8a654d65d1728207fadc1597ad8c7c` for issue #157.
> This report records evidence and dispositions; it does not change skill runtime behavior.

## Inventory

| Surface | Count |
|---|---:|
| Source skills | 84 |
| Packaged skills | 74 |
| Unpackaged source skills | 10 |
| Marketplace plugins | 16 |
| Implicitly eligible packaged skills | 2 |
| Extracted packaged-Markdown references | 654 |
| Unexplained reference occurrences | 0 |

The machine-readable source of truth is [`.agents/skill-contracts.json`](../.agents/skill-contracts.json).

## Current Invocation Policy

Payload `0.3.0+codex.20260906121706` keeps `$flow-auto`, `$project-next` implicitly eligible. Every other packaged skill remains available through explicit `$skill-name` selection or `/skills` discovery. Plugin metadata changes require an upgrade or reinstall followed by a new Codex session.

The versioned source of truth is [`.agents/skill-invocation-policy.json`](../.agents/skill-invocation-policy.json).

## Current Fresh Full-Suite Capture

An isolated `codex-cli 0.146.1` full-profile install captured at `2026-08-06T20:56:44Z` exposed 7 entries: 2 CxPP and 5 system entries. Skill entry lines consumed 3,281 bytes; the framed Skills section consumed 3,789 bytes. The focused fresh-install tests reproduce the profile inventory and enforce the policy budgets.

## Stage 0 Full-Suite Prompt Capture

An isolated `codex-cli 0.146.1` full-suite install exposed 78 entries: 73 CxPP and 5 system entries. Skill entry lines consumed 20,640 bytes; the framed Skills section consumed 21,127 bytes.

Prompt presence passed. Direct recall, indirect recall, and negative precision remain explicitly unmeasured until issue #161 supplies the bounded live evaluator; this baseline does not turn absence of measurement into green.

## Unpackaged Skills

| Skill | Owner | Disposition | Review by |
|---|---|---|---|
| `browser-help` | Codex Power Pack maintainers (#173) | Replace: Codex browser orientation is covered by the native Playwright MCP workflow. Replacement: qa-help and upstream Playwright MCP guidance. | 2027-03-31 |
| `browser-session` | Codex Power Pack maintainers (#173) | Keep source-only: named concurrent authenticated sessions remain distinct, but no measured demand or activation evidence justifies packaging. Replacement: qa-test for single-session QA; no packaged replacement for named concurrent sessions. | 2027-03-31 |
| `cicd-woodpecker` | Codex Power Pack maintainers (#173) | Replace: supported Woodpecker pipeline generation and client operations are split across narrower skills; CxPP does not own server or agent lifecycle. Replacement: cicd-pipeline and the explicit woodpecker client skills. | 2027-03-31 |
| `cpp-dockers` | Codex Power Pack maintainers (#173) | Retire: whole-daemon inspection and the retired CPP Docker runtime are outside CxPP's host-runtime boundary. Replacement: no CxPP replacement; use host Docker tooling and cxpp-status for CxPP services. | 2027-03-31 |
| `cpp-happy-check` | Codex Power Pack maintainers (#173) | Retire: third-party Happy CLI currency is outside CxPP ownership and has no measured CxPP demand. Replacement: no CxPP replacement; use the Happy CLI update workflow outside CxPP. | 2027-03-31 |
| `cpp-help` | Codex Power Pack maintainers (#173) | Replace: a global catch-all would duplicate the bounded packaged family help skills. Replacement: the packaged family help skills. | 2027-03-31 |
| `cpp-load-best-practices` | Codex Power Pack maintainers (#173) | Replace: Codex uses focused instructions and documentation instead of a Claude context loader. Replacement: AGENTS.md and focused Codex documentation. | 2027-03-31 |
| `cpp-load-mcp-docs` | Codex Power Pack maintainers (#173) | Replace: MCP discovery is host-managed and does not need a Claude context loader. Replacement: docs/HOST_MANAGED.md and second-opinion-help. | 2027-03-31 |
| `flow-auto_codex` | Codex Power Pack maintainers (#173) | Replace: a second full-lifecycle entrypoint would duplicate flow-auto; claude-code-review is not an automatic Codex pre-PR stage. Replacement: flow-auto plus separately and explicitly selected claude-code-review. | 2027-03-31 |
| `flow-repair` | Codex Power Pack maintainers (#173) | Replace: Codex flow packages bundle helpers and do not install Claude stable-path scripts. Replacement: bundled flow helpers, flow-doctor, and reinstall or cxpp-update. | 2027-03-31 |

The post-release evidence and decision record is [`wave-7-exclusion-review.md`](wave-7-exclusion-review.md).

## Reference Classification

| Classification | Occurrences | Meaning |
|---|---:|---|
| Resolvable | 420 | Explicit `$skill-name` resolves to a packaged skill. |
| Native | 21 | Supported Codex host command. |
| Adapted | 123 | The packaged skill carries an explicit Codex harness adaptation. |
| Excluded | 23 | Target has a reviewed, owned, time-bound exclusion. |
| Source context | 66 | Non-operational provenance or migration text. |
| Example | 1 | Documented placeholder syntax, not a dependency. |
| Unexplained | 0 | Scheduled for invocation normalization or semantic review. |

Unexplained occurrences are grouped below so every gap has one owner and disposition without hiding its evidence locations.

| Token | Evidence count | Owner | Disposition | Review by |
|---|---:|---|---|---|

## Stage 0 Known Failures and Owners

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
