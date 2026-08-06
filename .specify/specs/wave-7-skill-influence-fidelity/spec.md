# Feature Specification: Wave 7 - Codex Skill Influence & Behavioral Fidelity

> **Tracking issue:** #153
> **Created:** 2026-08-06
> **Status:** Approved

---

## Overview

Codex Power Pack successfully installs and advertises a broad catalogue of
skills, but installation and byte parity do not guarantee that a Codex session
selects the right skill, follows the intended workflow, or reaches the same
quality bar as the corresponding Claude Power Pack command. The current system
has four recurring failure modes:

1. Codex skills are documented as slash commands even though Codex's reusable
   workflow surface is explicit `$skill-name` selection or `/skills` plus
   description-driven implicit invocation.
2. CxPP-owned native skills can drift semantically from mature CPP commands;
   `project-next` is the reference example.
3. Sync and harness-lint gates prove file integrity and catch a small set of
   Claude-only tokens, but allow dangling skill references, stale runtime paths,
   misleading metadata, and unpackaged capabilities.
4. Installed skills are mostly on-demand. Target repositories receive no
   durable CxPP workflow routing, and useful hooks remain checkout-local rather
   than deliberately packaged and trusted.

Wave 7 makes behavioral fidelity, activation quality, and durable session
influence first-class product contracts. It begins with a complete
`project-next` vertical slice and then generalizes the same controls across the
plugin catalogue.

### Baseline Evidence

The 2026-08-06 repository and live-install audit established this starting
point:

- 83 source skill directories exist under `.codex/skills/`.
- 73 skills are packaged across 16 plugins and advertised for implicit use.
- 10 source skills are not packaged, including capabilities referenced by
  packaged help or workflow text.
- A full installed session advertises 78 total skills, 73 from CxPP, consuming
  approximately 19,931 characters of initial skill metadata.
- CPP's `project-next` command contains the richer ranking, mode, spec-sync,
  and edge-case contract, while CxPP's native skill contains stronger PR and
  remote-branch mapping but a materially thinner decision policy.
- Existing sync and harness-lint gates pass despite operational `.claude/`
  paths and unresolved skill references in packaged payloads.

---

## User Stories

### US1: Dependable Next-Action Recommendation [P1]

**As a** maintainer choosing what to work on,
**I want** `project-next` to return a reproducible, evidence-backed top action,
**So that** I can trust Codex instead of rerunning the workflow in Claude Code.

**Acceptance Criteria:**

- [ ] `project-next` distinguishes the top action now from the next new issue
      that is safe to start.
- [ ] Active PRs, local and remote issue branches, worktrees, dirty state,
      review state, and CI state are included in the decision input.
- [ ] In-flight, blocked, and available issues are materialized as disjoint
      sets, with transitive dependencies and cycles handled deterministically.
- [ ] Blocked or in-flight issues never appear as startable recommendations.
- [ ] Ranking covers critical/security work, declared priority, phase or wave,
      issue type, quick wins, staleness, and a documented stable tie-break.
- [ ] Compact, `--brief`, and `--full` modes have versioned output contracts.
- [ ] Spec-kit tasks without matching issues are surfaced without being treated
      as ready GitHub issues.
- [ ] Repository-specific ranking policy can be declared in a harness-neutral
      configuration file and degrades predictably when absent.
- [ ] The decision engine accepts fixture data and emits structured JSON so its
      classification and ranking can be tested without an LLM or live GitHub.

**Test Scenarios:**

1. Given a high-priority issue with an active PR and a lower-priority available
   issue, when `project-next` runs, then the active PR is a continue/review
   action and only the available issue is a candidate to start.
2. Given A depends on B and B depends on C, when C remains open, then A and B
   are blocked and neither is startable.
3. Given two otherwise equal available issues, when ranking runs repeatedly,
   then the same issue wins through the documented tie-break.
4. Given failing required checks on active work, when recommendations are built,
   then repairing the gate outranks starting broad new work.

---

### US2: Honest and Predictable Skill Invocation [P1]

**As a** Codex user,
**I want** CxPP documentation and metadata to match Codex's real invocation
model,
**So that** explicit and natural-language requests reliably select the intended
workflow.

**Acceptance Criteria:**

- [ ] User-facing Codex guidance uses `$skill-name` or `/skills`; it does not
      present plugin skills as first-class custom slash commands.
- [ ] Every plugin and skill starter prompt references a bundled, selectable
      capability.
- [ ] Each implicitly eligible skill description begins with a recognizable
      user goal and includes clear trigger boundaries.
- [ ] Direct, indirect, incomplete, and negative activation prompts exist for
      every implicit entrypoint.
- [ ] Implicit eligibility is curated by workflow value and ambiguity rather
      than enabled for every skill solely to make it visible.
- [ ] Explicitly selected skills remain usable even when implicit invocation is
      disabled.
- [ ] A full-suite prompt-inventory test detects missing, duplicated, or
      materially truncated priority entrypoints.

---

### US3: Semantic Harness Compatibility [P1]

**As a** CxPP maintainer,
**I want** generated and native Codex skills checked for executable semantic
compatibility,
**So that** parity gates cannot pass while the installed workflow points at the
wrong host, path, command, or package.

**Acceptance Criteria:**

- [ ] Every cross-skill reference resolves to a packaged skill, a supported
      native Codex command, or an explicit reviewed exclusion.
- [ ] Operational `.claude/` paths, Claude marketplace commands, Claude-only
      tools, and CPP-only runtime discovery fail validation unless a narrow
      adaptation proves why the occurrence is safe.
- [ ] The source-skill inventory, packaged inventory, and published marketplace
      inventory reconcile through one machine-readable manifest.
- [ ] Intentional exclusions carry an owner, rationale, replacement, and review
      date.
- [ ] Plugin and skill metadata cannot name a fixed repository when the workflow
      is repository-neutral.
- [ ] Required runtime services or tools are declared or checked with an
      actionable graceful-degradation path.
- [ ] CI verifies behavioral contracts in addition to file hashes.

---

### US4: Measurable Skill Quality [P1]

**As a** release owner,
**I want** activation and outcome evaluations for important skills,
**So that** regressions are visible before a plugin release reaches daily use.

**Acceptance Criteria:**

- [ ] A versioned evaluation schema supports direct, indirect, negative,
      incomplete-input, and edge-case prompts.
- [ ] Deterministic fixture tests run on every PR without network or model cost.
- [ ] A bounded live Codex evaluation lane can run manually or on a schedule and
      records skill selected, required steps followed, output-contract result,
      latency, and safe failure reason.
- [ ] Direct activation recall is 100% for published entrypoints.
- [ ] Indirect activation recall is at least 90% for high-value implicit
      entrypoints.
- [ ] Negative-prompt precision is at least 95%.
- [ ] `project-next` selects the expected top action and next-startable issue in
      100% of deterministic fixtures.
- [ ] Evaluation failures block the affected skill's release or require a
      documented exception with an expiry date.

---

### US5: Durable, Consent-First Session Influence [P2]

**As a** developer using CxPP across repositories,
**I want** an optional durable routing and lifecycle layer,
**So that** CxPP conventions influence the session without pasting instructions
into every prompt.

**Acceptance Criteria:**

- [ ] CxPP provides a concise, additive `AGENTS.md` routing block that maps
      recognizable outcomes to installed skills.
- [ ] `cxpp-init` and `cxpp-update` preview the exact guidance change and require
      explicit approval before editing a target repository.
- [ ] Security masking and friction-capture hooks are packaged only in the
      families that own them and require normal Codex hook trust review.
- [ ] Missing, untrusted, disabled, or stale hooks are reported by
      `cxpp-status`; they are never silently installed or force-enabled.
- [ ] Hooks do not create issues, alter code, change permissions, or invoke
      shipping workflows automatically.
- [ ] Removing a plugin or its optional routing block leaves the repository and
      global Codex configuration in a recoverable state.

---

### US6: Safe Rollout and Migration [P2]

**As a** current CxPP user,
**I want** the fidelity changes shipped without breaking existing explicit
workflows,
**So that** quality improves without another installed-but-invisible cutover.

**Acceptance Criteria:**

- [ ] Release notes explain invocation changes, implicit-policy changes, hook
      trust, rollback, and the required new-session boundary.
- [ ] Marketplace installation is verified at an immutable commit or signed tag.
- [ ] Existing explicit `$skill-name` invocation continues to work throughout
      the rollout.
- [ ] `cxpp-status` reports the installed version, enabled state, pin posture,
      priority skill visibility, and optional influence-layer state.
- [ ] At least 20 representative dogfood sessions complete without a priority
      activation or behavioral-fidelity regression before the wave is closed.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| More open issues than the GitHub query limit | Report the incomplete inventory and do not claim a globally correct top pick |
| Dependency wording is ambiguous | Classify as uncertain and exclude from startable recommendations until reviewed |
| A worktree cannot be mapped to an issue | Report it separately with branch, status, and recent commits; do not infer from similar wording |
| A generated skill references an intentionally excluded skill | Require an explicit replacement or exclusion record; help text cannot advertise it as available |
| The full skill catalogue exceeds the initial metadata budget | Preserve priority entrypoints, warn in diagnostics, and rely on explicit `/skills` selection for secondary capabilities |
| A plugin hook changes after trust was granted | Codex's normal hash-based trust review applies; the changed hook remains inactive until reviewed |
| A target repository already has custom AGENTS.md routing | Preview a bounded additive merge and preserve existing instructions |
| Live model evaluation is unavailable | Deterministic gates still run; mark the live lane not checked rather than green |

---

## Out of Scope

- Reintroducing deprecated custom-prompt slash commands as the primary CxPP
  distribution model.
- Making all installed skills globally persistent in prompt context.
- Automatically trusting hooks, changing approval policy, or widening sandbox
  permissions.
- Rewriting every CPP command in this wave; only behavior needed by the staged
  CxPP fidelity work is reconciled.
- Starting, stopping, deploying, or managing external MCP services.
- Implementing the wave in this specification PR.
- Creating all implementation issues before the specification PR is reviewed
  and merged.

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Provide a deterministic `project-next` classification and ranking core with structured input/output | Must | US1 |
| R2 | Preserve Codex-native PR, branch, worktree, review, and gate awareness | Must | US1 |
| R3 | Reconcile CPP ranking, modes, spec awareness, and edge cases into the authoritative contract | Must | US1 |
| R4 | Normalize user-facing invocation to supported Codex skill selection | Must | US2 |
| R5 | Curate and test implicit-invocation metadata | Must | US2, US4 |
| R6 | Validate cross-skill references, runtime paths, packaging coverage, and exclusions | Must | US3 |
| R7 | Run deterministic skill-contract tests on every PR | Must | US3, US4 |
| R8 | Provide a bounded live activation/outcome evaluation lane | Should | US4 |
| R9 | Offer additive target-repository AGENTS.md routing with explicit consent | Should | US5 |
| R10 | Package owner-specific hooks with trust and status diagnostics | Should | US5 |
| R11 | Publish migration, rollback, and immutable-pin verification | Must | US6 |

### Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | Initial-context efficiency | Priority implicit metadata remains within a documented budget and is measured in CI |
| NFR2 | Determinism | Repeated fixture runs produce byte-stable classification and ranking JSON |
| NFR3 | Safety | No new external writes occur without existing user confirmation and host approval controls |
| NFR4 | Portability | Deterministic tooling uses Python 3.11+ and runs on Linux, macOS, and Windows where git/gh are available |
| NFR5 | Auditability | Every exclusion and evaluation exception has an owner, reason, and expiry/review date |
| NFR6 | Backward compatibility | Existing explicit skill selection remains functional during migration |

---

## Success Criteria

- [ ] `project-next` is preferred over rerunning the same task in Claude Code in
      dogfood feedback.
- [ ] No packaged help or workflow text references an unavailable capability.
- [ ] No operational Claude-only path or command reaches a CxPP release without
      a reviewed adaptation.
- [ ] Priority skills meet the activation and outcome thresholds in US4.
- [ ] CxPP's optional persistent influence layer is transparent, consent-first,
      removable, and visible in status output.
- [ ] All staged implementation issues are merged with `make verify` green.
- [ ] Documentation, release guidance, and rollback instructions match the
      installed behavior.

---

## Open Questions

- [ ] After baseline evaluation, which one to three skills per family should
      remain implicitly eligible by default?
- [ ] Should the cross-repository `project-next` behavioral contract ultimately
      live in CxPP, CPP, or a small harness-neutral package consumed by both?
- [ ] Which live evaluation cadence provides useful signal without making
      ordinary PR verification depend on model availability?

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
