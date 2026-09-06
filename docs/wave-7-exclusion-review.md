# Wave 7 Exclusion Review

This review resolves the ten time-bounded source-skill exclusions tracked by
[issue #173](https://github.com/cooneycw/codex-power-pack/issues/173). It records
the evidence available after the v0.2.0 rollout and updates their dispositions;
it does not package a skill, change runtime behavior, or expand implicit
invocation.

## Evidence and limits

[PR #174](https://github.com/cooneycw/codex-power-pack/pull/174) released v0.2.0
after 20 bounded Codex 0.146.1 sessions: 18 passed, two explicit-only
`project-init` cases were correctly unavailable, and none failed. The ten skills
reviewed here were not cases in that lane, so its direct recall, indirect recall,
and negative precision results do not measure demand or activation for them.
The retained aggregate is in
[`wave-7-release-validation.md`](wave-7-release-validation.md).

On 2026-09-06, exact-name searches of the public CxPP issue and pull-request
tracker from the 2026-08-07 release through the review date found no post-release
item for any of the ten skills except issue #173 itself. That result measures the
public tracker only. CxPP has no private-usage or CLI-selection telemetry for
these skills, so the absence of a ticket is not proof that demand cannot exist.

The current contract also exposes replacement coverage. Six skills have no
operational references from packaged guidance. Four remain referenced:
`cicd-woodpecker` five times, `cpp-load-mcp-docs` once, `flow-auto_codex` once,
and `flow-repair` 17 times. These are migration or dependency references, not
user-demand observations. They remain classified as reviewed exclusions so the
coverage boundary stays visible.

[PR #186](https://github.com/cooneycw/codex-power-pack/pull/186) added the
explicit-only `$codex-wayfinder` surface and regenerated the contract without
changing these ten decisions. This review retains that skill, the 84 source / 74
packaged / 10 unpackaged inventory, and the two-entry implicit policy.

## Decisions

The owner for every decision is the Codex Power Pack maintainers. The review
date is 2027-03-31. For a permanent retirement, that date audits whether the
exclusion and references remain accurate; it does not reopen the ownership
decision without new evidence.

| Skill | Decision | Rationale | Replacement or remaining gap |
|---|---|---|---|
| `browser-help` | Replace | Native Playwright MCP guidance and the QA family cover browser orientation. | `$qa-help` and upstream Playwright MCP guidance. Named concurrency remains separately visible under `browser-session`. |
| `browser-session` | Keep | Named concurrent authenticated sessions are distinct, but no measured demand or activation evidence justifies packaging. | `$qa-test` covers single-session QA; there is no packaged replacement for named concurrent sessions. |
| `cicd-woodpecker` | Replace | Supported pipeline generation and client operations are already split across narrower skills; CxPP does not own server or agent lifecycle. | `$cicd-pipeline` and the explicit `woodpecker-*` client skills. |
| `cpp-dockers` | Retire | Whole-daemon inspection and the retired CPP Docker runtime are outside CxPP's host-runtime boundary. | No CxPP replacement; use host Docker tooling and `$cxpp-status` for CxPP services. |
| `cpp-happy-check` | Retire | Third-party Happy CLI currency is outside CxPP ownership and has no measured CxPP demand. | No CxPP replacement; use the Happy CLI update workflow outside CxPP. |
| `cpp-help` | Replace | A global catch-all would duplicate the bounded packaged family help skills. | The packaged family help skills. |
| `cpp-load-best-practices` | Replace | Codex uses focused instructions and documentation instead of a Claude context loader. | `AGENTS.md` and focused Codex documentation. |
| `cpp-load-mcp-docs` | Replace | MCP discovery is host-managed and does not need a Claude context loader. | [`HOST_MANAGED.md`](HOST_MANAGED.md) and `$second-opinion-help`. |
| `flow-auto_codex` | Replace | A second full-lifecycle entrypoint would duplicate `$flow-auto`; `$claude-code-review` is not an automatic Codex pre-PR stage. | `$flow-auto` plus separately and explicitly selected `$claude-code-review`. |
| `flow-repair` | Replace | Codex flow packages bundle helpers and do not install Claude stable-path scripts. | Bundled flow helpers, `$flow-doctor`, and reinstall or `$cxpp-update`. |

## Resulting boundary

No reviewed skill is packaged. `$flow-auto` and `$project-next` remain the only
implicit entrypoints; all replacements remain explicitly selected. The review
does not restore Docker runtime ownership, Claude-only context loaders, a
duplicate flow lifecycle, or Woodpecker server and agent lifecycle.

`Retire` is an inventory disposition, not a file deletion: `cpp-dockers` and
`cpp-happy-check` remain present in the source inventory while staying
unpackaged and excluded from the supported plugin surface.

The machine-readable exclusions remain generated from
[`skill_contract_baseline.py`](../scripts/skill_contract_baseline.py). This
review intentionally does not refresh adopted CPP source: the independent
source-currency failure is owned by a separate adoption decision.
