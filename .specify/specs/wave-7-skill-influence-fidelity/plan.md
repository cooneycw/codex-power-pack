# Implementation Plan: Wave 7 - Codex Skill Influence & Behavioral Fidelity

> **Tracking issue:** #153
> **Spec:** [spec.md](./spec.md)
> **Created:** 2026-08-06
> **Status:** Approved

---

## Summary

Wave 7 replaces artifact-parity confidence with measurable workflow fidelity.
The implementation starts with a deterministic `project-next` vertical slice,
then normalizes invocation and metadata, adds semantic package validation,
introduces skill activation/outcome evaluations, and finally offers an opt-in
`AGENTS.md` plus trusted-hook influence layer. Each stage is independently
mergeable and has a hard checkpoint before dependent work begins.

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Language | Python 3.11+ | Matches the constitution and existing cross-platform tooling |
| Package manager | uv | Existing repository standard |
| Test framework | pytest | Existing quality gate and fixture support |
| Skill format | Open Agent Skills `SKILL.md` plus `agents/openai.yaml` | Native Codex plugin surface |
| Durable guidance | Target-repository `AGENTS.md` block | Codex reads it before task work and supports nested precedence |
| Lifecycle integration | Plugin-bundled Codex hooks | Native, trust-reviewed, and scoped to owning plugins |
| Deterministic contracts | JSON fixtures and structured engine output | Separates data classification from model explanation |
| Live evaluation | Bounded `codex exec --json` lane | Tests real selection and workflow adherence without burdening every PR |
| Project creation | Explicit local Python scaffold | Makes the safe implemented behavior the default and separates later external effects |
| Spec Kit boundary | Official `v0.16.0` Codex integration plus CxPP extension | Pins upstream authoring and adds compilation without replacing core templates |
| Issue unit | Stage/story by default; task only by explicit request | Produces independently deliverable work suitable for `flow-auto` |

---

## Constitution Check

- [x] **P1 Context Efficiency:** The plan reduces implicit catalogue noise,
      measures metadata size, and keeps detailed procedures behind skill
      selection.
- [x] **P2 Issue-Driven:** Umbrella issue #153 owns the specification; each
      implementation stage becomes a child issue before coding.
- [x] **P3 Spec-First:** This spec, plan, and task breakdown land before
      implementation.
- [x] **P4 Test-Driven:** Deterministic fixtures, activation prompts, and stage
      exit gates are defined before behavior changes.
- [x] **P5 Cross-Platform:** New deterministic tooling is Python 3.11+; shell is
      limited to existing host commands such as git, gh, and Codex.

---

## Architecture

### Component Overview

```text
                 target repository state
                git + gh + optional spec-kit
                           |
                           v
             project-next collection adapter
                           |
                           v
         deterministic classification/ranking core
                           |
                     structured JSON
                           |
                           v
               project-next skill renderer

plugin source ----> semantic contract validator ----> packaged plugin
     |                         |                           |
     |                         v                           v
     +--------------> deterministic fixtures      Codex prompt inventory
                                 |                         |
                                 +------> live eval <------+

target AGENTS.md routing + trusted plugin hooks
             -> optional durable session influence

local project scaffold --separate consent--> GitHub publication
         |
         +--separate consent--> pinned official Spec Kit adoption
                                      |
                                      v
                         spec/plan/tasks authoring
                                      |
                           blocking readiness gate
                                      |
                                      v
                    CxPP Spec Kit extension (`spec-sync`)
                                      |
                         stage/story GitHub issues
                                      |
                         project-next -> flow-auto
```

### Key Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| `project-next` computation | Prompt-only, deterministic helper, MCP service | Deterministic Python core plus thin skill | Classification and ranking become reproducible without adding a service |
| Top recommendation model | Next new issue only, active work only, two-part result | Top action plus next startable issue | Matches how maintainers actually choose work while preserving the hard availability gate |
| Cross-harness fidelity | Copy CPP text, keep unrelated native fork, shared behavioral contract | Shared contract and fixtures with harness adapters | Retains Codex-native evidence while preventing silent semantic regression |
| Invocation syntax | Faux slash aliases, `$skill-name`, implicit only | `$skill-name` and `/skills`, with measured implicit entrypoints | Aligns documentation with supported Codex behavior |
| Implicit policy | All skills, no skills, curated entrypoints | Curated entrypoints based on evaluation | Balances visibility, activation precision, and prompt budget |
| Compatibility validation | Hash parity, denylist lint, semantic graph | Keep parity plus semantic graph validation | Existing checks remain useful but no longer define completeness |
| Persistent influence | Global prompt injection, target AGENTS.md, hooks only | Consent-first AGENTS.md routing plus narrowly owned hooks | Uses native durable surfaces while keeping changes transparent and removable |
| Evaluation cadence | All live on every PR, deterministic only, split lane | Deterministic per PR; bounded live manual/scheduled lane | Preserves reliable CI without external-model flakiness or uncontrolled cost |
| Project-init product | CPP zero-to-GitHub orchestration, native local scaffold, hybrid automatic pipeline | Native local scaffold with separately consented handoffs | Matches tested behavior and prevents one prompt from authorizing unrelated external state |
| Spec Kit composition | Hand-authored scaffold, preset, extension, bundle | Official pinned authoring plus one CxPP extension | Readiness and issue compilation are additive capabilities, not core-template replacements or a multi-component distribution stack |
| Issue compiler ownership | Copies in evaluate/project/project-next, spec-sync, shared helper | `spec-sync` only | One parser, grouping policy, idempotency model, and mapping writer can be tested and evolved coherently |
| Sync identity | Title/task ID, artifact commit, stable ledger identity | Stable repo + task-ledger path + group ID | Survives title edits and artifact revisions while immutable links preserve the approved source commit |

### Behavioral Contract Boundaries

The wave distinguishes four contracts:

1. **Discovery contract:** the skill is present, selectable, and described with
   the intended trigger boundary.
2. **Procedure contract:** after selection, the required evidence, decision
   points, safety boundaries, and output fields are followed.
3. **Runtime contract:** referenced commands, scripts, services, paths, and
   related skills exist in the installed environment or degrade explicitly.
4. **Session-influence contract:** persistent guidance and hooks are opt-in,
   visible, trusted, scoped, and removable.

No single hash, metadata flag, or prompt-inventory assertion satisfies all four.

### Project-to-Issue Composition Boundary

Issue #166 publishes the normative contract in
`.agents/project-init-spec-kit-contract.json` and its schema. The corresponding
decision record is `docs/project-init-spec-kit-contract.md`. This prerequisite
changes no runtime behavior; Stages 1 through 6 consume its assigned slices.

The composition is sequential but not automatic. A successful local scaffold
does not authorize publication. Publication does not authorize Spec Kit
installation. Adoption does not authorize issue creation. A readiness result
does not authorize GitHub writes until the user approves the artifact commit,
grouping, and repository. Persistent AGENTS.md or hook influence remains a
separate `cxpp-init` decision throughout.

The Spec Kit integration is pinned to `v0.16.0` at commit
`5dce710ce099067c7d3f2ef47a37b9a1c300b327`. CxPP will implement readiness and
issue compilation as an extension. The extension preserves official spec,
plan, and task authoring, rejects incomplete artifacts, and emits stable
stage/story mappings for `project-next` and `flow-auto`.

---

## Planned File Structure

```text
lib/project_next/
├── __init__.py
├── models.py                 # structured repository-state and result models
├── classify.py               # in-flight, dependency, blocked, available sets
├── rank.py                   # deterministic top-action and next-issue policy
└── render.py                 # brief, compact, and full structured views

scripts/
├── project-next.py           # git/gh/spec collection adapter
├── skill-contract-lint.py    # semantic path, link, metadata, and packaging gate
└── skill-eval.py             # deterministic and optional live evaluation runner

.agents/
├── skill-contracts.json      # published skills, aliases, ownership, exclusions
├── project-init-spec-kit-contract.schema.json
├── project-init-spec-kit-contract.json
└── routing-block.md          # concise target-repository AGENTS.md fragment

tests/
├── test_project_init_spec_kit_contract.py
├── project_next/
│   ├── fixtures/
│   ├── test_classification.py
│   ├── test_ranking.py
│   └── test_output_contract.py
├── skill_contracts/
│   ├── test_references.py
│   ├── test_runtime_paths.py
│   ├── test_packaging.py
│   └── test_metadata.py
└── skill_evals/
    ├── cases/
    ├── test_schema.py
    └── test_deterministic_outcomes.py

plugins/<family>/
├── skills/
└── hooks/                    # only where the family owns a reviewed hook

docs/
├── project-init-spec-kit-contract.md
├── skill-quality.md
└── migration/skill-influence-wave-7.md
```

Exact paths may be refined during the relevant stage, but ownership boundaries
and test responsibilities must remain intact.

---

## Implementation Stages

### Stage 0: Baseline and Contract Inventory

Create a machine-readable inventory before changing behavior. Record every
source skill, packaged skill, implicit setting, cross-skill reference, runtime
dependency, host-specific path, and deliberate exclusion. Define the evaluation
case schema and capture the current prompt inventory and activation baseline.

**Exit gate:** all currently unexplained inventory gaps and dangling references
are visible as data; no behavior has changed.

### Stage 1: `project-next` Fidelity Vertical Slice

Write the shared behavioral contract and fixture corpus first. Implement the
deterministic classifier/ranker, add the git/gh/spec collection adapter, and
update the CxPP skill to render the structured result. Reconcile the mature CPP
ranking/mode behavior with CxPP's PR, remote-branch, review, and CI evidence.

The stage must decide the final cross-repository source-of-truth location. If a
CPP change is required, land the CPP contract/generator change first, pin it,
and then adopt it in CxPP without leaving a second prompt-only fork.

PR #167 merged this foundation and closed #158 while issue #166 was in progress.
Stable stage/story/task mapping did not yet exist, so the consumer integration
is assigned to Stage 3 alongside the compiler. Task IDs remain traceability
keys, not proof that every task owns a GitHub issue.

**Exit gate:** fixture outcomes are deterministic; blocked and in-flight issues
cannot leak into startable choices; brief/compact/full outputs pass; live dogfood
chooses the expected action on both power-pack repositories.

### Stage 2: Invocation and Metadata Normalization

Replace faux plugin slash-command guidance with supported Codex selection,
rewrite trigger descriptions and starter prompts, and select the initial
implicit-entrypoint set using golden prompts. Add per-plugin and full-suite
prompt-inventory tests.

Align project-init's skill text, help, metadata, plugin manifest, and starter
prompts to the local-only explicit contract. Add negative activation cases for
orientation, next-work analysis, publication, Spec Kit adoption, issue sync,
and ordinary changes in existing repositories.

**Exit gate:** every advertised invocation is valid, every starter prompt
selects a bundled skill, and activation thresholds pass for the changed
families.

### Stage 3: Semantic Compatibility and Packaging Gates

Implement the semantic contract validator and explicit exclusion manifest.
Repair discovered stale runtime paths, fixed-repository descriptions, and
dangling references, beginning with the flow, CI/CD, GitHub, project, and help
surfaces. Integrate the validator into `make verify` and CI.

Existing issues #135 and #140 are inputs to this stage; the stage issues must
either satisfy their exit bars or explicitly narrow the remaining work.

This stage owns the runtime implementation of the project-to-issue contract:
pin official Spec Kit adoption, add the CxPP extension, implement the readiness
gate and stage/story compiler, write rich issue bodies and stable mappings, and
retire every duplicate compiler payload inventoried by issue #166. Replace the
new project-next task-ID heuristic with those mappings; missing, stale, or
ambiguous mappings remain uncertainty and cannot make blocked or represented
work appear startable.

**Exit gate:** source, packaged, and marketplace inventories reconcile; all
cross-skill links resolve; operational Claude-only constructs require reviewed
adaptations; every published family passes the semantic gate.

### Stage 4: Activation and Outcome Evaluation Harness

Add deterministic evaluation cases across priority skills and a bounded live
Codex lane. Separate activation failures from instruction-following and runtime
failures so metadata tuning does not mask procedure defects. Store only
non-secret summaries and aggregate metrics.

Add distinct fixtures for project routing, scaffold consent, pinned adoption,
artifact readiness, malformed tasks, grouping, issue bodies, idempotency,
mapping repair, and the complete scaffold-to-Flow dry run.

**Exit gate:** priority entrypoints meet the spec thresholds; deterministic
evaluations run on every PR; the live lane has a documented manual/scheduled
owner, timeout, budget, and failure policy.

### Stage 5: Consent-First Persistent Influence

Create the concise target-repository `AGENTS.md` routing block and additive
`cxpp-init` / `cxpp-update` workflow. Package secrets masking and friction
capture with the owning plugins, preserve Codex's hook trust flow, and extend
`cxpp-status` with safe diagnostics.

Project creation may offer this stage only as a handoff to `cxpp-init`.
Declining the handoff leaves the ordinary local scaffold unchanged and never
installs AGENTS.md routing, hooks, permissions, trust, or plugin state.

**Exit gate:** clean install, upgrade, decline, untrusted-hook, changed-hook,
disable, and removal scenarios are tested; no persistent component turns itself
on without approval.

### Stage 6: Rollout, Documentation, and Closeout

Publish migration guidance, update help and architecture documentation, cut a
pinned release, and run representative dogfood sessions. Review the implicit
set and remaining exclusions against measured results. Close or re-scope legacy
issues only after their exit bars are demonstrably met.

Dogfood at least one clean project through local scaffold, optional publication,
pinned Spec Kit adoption, approved artifact readiness, stage/story issue sync,
`project-next`, and `flow-auto`. Migration guidance must explain retirement of
duplicate helpers and one-line per-task issues.

**Exit gate:** immutable install and rollback transcripts pass, 20
representative sessions meet the success criteria, and all wave documentation
matches the released payload.

---

## Dependencies

### External Dependencies

| Dependency | Purpose | Failure Behavior |
|------------|---------|------------------|
| git | Repository, branch, and worktree state | Stop repository-state workflows with an actionable prerequisite |
| GitHub CLI (`gh`) | Issues, PRs, checks, and repository identity | Report authentication or rate-limit state; never rank an incomplete inventory as complete |
| Codex CLI | Prompt inventory and bounded live evaluation | Deterministic gates continue; live lane reports not checked |
| Official Spec Kit `v0.16.0` | Author spec, plan, and task artifacts through the Codex integration | Adoption stops on pin/install/init failure; repository analysis reports not configured when absent |
| Optional MCP services | Skill-specific live tools | Declare/check dependency and degrade per owning skill |

### Internal Dependencies

| Component | Purpose |
|-----------|---------|
| `scripts/codex_skills_sync.py` | Preserve generated-skill provenance and apply reviewed runtime overlays |
| `scripts/harness_lint.py` | Existing lexical compatibility gate to retain and narrow |
| `tests/test_project_plugin_marketplace.py` | Existing package and prompt-inventory coverage to generalize |
| `plugins/cxpp/` | Consent-first setup, update, and status surface |
| `.specify/` | Spec awareness and later implementation-issue synchronization |

---

## Testing Strategy

### Unit Tests

- Dependency parsing, transitive closure, cycle handling, disjoint-set
  validation, ranking, stable tie-breaks, and rendering modes.
- Skill-reference extraction, alias resolution, exclusion validation, runtime
  path classification, and metadata policies.
- AGENTS.md block generation and additive merge behavior.
- Hook payload validation, masking, failure-open behavior, and status reporting.
- Project routing, artifact-readiness checks, grouping, stable sync identity,
  issue-body rendering, open/closed idempotency, and mapping write-back.

### Integration Tests

- Fresh plugin install exposes expected priority skills in
  `codex debug prompt-input`.
- Full-suite install preserves required entrypoints and respects the metadata
  budget policy.
- Fixture git repositories plus a stubbed `gh` surface exercise the complete
  `project-next` collection-to-render pipeline.
- Packaged skills resolve bundled scripts and related skills without requiring
  a Claude Power Pack checkout.
- `cxpp-init`, update, status, and removal paths preserve consent and existing
  configuration.

### Live Evaluations

- Run representative direct, indirect, negative, incomplete, and edge-case
  prompts in an isolated Codex home.
- Record selected skill, expected procedure checkpoints, output-contract
  verdict, and safe error summary.
- Do not expose tokens, raw configuration, environment contents, or full private
  issue bodies in stored artifacts.
- Live evaluations are bounded and fail distinctly as unavailable, activation
  failure, procedure failure, runtime failure, or output-contract failure.

### Manual Dogfood

- Run `project-next` against CxPP and CPP with known expected top actions.
- Install only the project plugin, the recommended profile, and the full suite.
- Verify `$skill-name`, `/skills`, and natural-language activation behavior.
- Review and trust packaged hooks, then verify changed-hook re-review and clean
  removal.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cross-repo project-next source-of-truth work stalls | Medium | High | Make the behavioral contract and fixtures portable; keep the deterministic CxPP core independently testable while requiring an explicit ownership decision in Stage 1 |
| Reducing implicit skills recreates installed-but-invisible confusion | Medium | High | Preserve explicit selection, document `/skills`, test priority visibility in fresh installs, and roll out per family |
| Live evaluations are flaky or costly | Medium | Medium | Keep deterministic PR gates authoritative; bound live runs by cases, time, and budget |
| Semantic lint generates excessive legacy findings | High | Medium | Land baseline inventory first, require explicit time-bounded exclusions, and burn down family by family |
| Hooks create trust fatigue | Medium | Medium | Package only high-value owner-specific hooks, show exact files, preserve opt-out, and avoid a generic catch-all hook |
| AGENTS.md routing becomes noisy | Medium | Medium | Keep the block concise, outcome-based, additive, and covered by a byte budget |
| Project-next policy overfits current labels | Medium | High | Use harness-neutral configuration, stable fallbacks, and fixtures for flat, wave, epic, and parent-child repositories |
| Existing documentation and aliases break abruptly | Low | Medium | Publish a migration table and retain explicit skill names throughout the rollout |

---

## Rollout Strategy

1. Merge this specification without runtime behavior changes.
2. Create one child issue per stage from `tasks.md`; preserve dependencies.
3. Ship Stage 1 as the first visible proof point.
4. Roll metadata and semantic validation family by family, starting with
   project, flow, GitHub, and CI/CD.
5. Introduce live evaluations as advisory until the deterministic schema and
   failure taxonomy are stable; then gate priority-skill releases.
6. Offer persistent influence components only after their clean install,
   decline, trust, upgrade, and removal paths pass.
7. Cut an immutable release, dogfood it, and close the wave only after the
   quantitative success criteria pass.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
