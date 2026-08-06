# Tasks: Wave 7 - Codex Skill Influence & Behavioral Fidelity

> **Tracking issue:** #153
> **Plan:** [plan.md](./plan.md)
> **Created:** 2026-08-06
> **Status:** Ready

---

## Task Format

```text
[ID] [P?] [Story] Description (depends on X, Y)
```

- **ID:** stable task identifier grouped by implementation stage.
- **[P]:** may run in parallel with other tasks whose dependencies are met.
- **[Story]:** specification user-story coverage.
- Each stage becomes one GitHub story issue before implementation begins.
- Tasks that require changes in `claude-power-pack` must identify and link the
  twin issue/PR from the stage issue.

---

## Stage 0: Baseline and Contract Inventory

- [x] **T001** [US3] Define `.agents/skill-contracts.json` schema for source,
      packaged, marketplace, implicit, dependency, alias, and exclusion state.
- [x] **T002** [US3] Inventory every `.codex/skills/` source and every packaged
      plugin skill, including the ten currently unpackaged source skills.
- [x] **T003** [P] [US3] Extract all cross-skill and host-command references from
      packaged Markdown and classify each as resolvable, native, adapted, or
      unexplained.
- [x] **T004** [P] [US2,US4] Define the versioned golden-prompt/evaluation-case
      schema for direct, indirect, negative, incomplete, and edge prompts.
- [x] **T005** [US2,US4] Capture the current full-suite prompt inventory,
      metadata byte count, activation baseline, and known failure examples.
- [x] **T006** [US3] Add a baseline report that assigns an owner and disposition
      to every unexplained gap; do not silently grandfather findings.

**Checkpoint:** The inventory reconciles all known source and package surfaces,
and every current semantic gap is either scheduled or explicitly time-bounded.
No runtime behavior changes in this stage.

---

## Prerequisite: `project-init` and Spec Kit Composition Contract

- [x] **T090** [US7] Audit the native project-init skill, scaffold helper,
      agent metadata, generated help, project manifest, CPP orchestration, Spec
      Kit skills, and every bundled task-to-issues helper.
- [x] **T091** [US7] Define the safe local scaffold default and separate consent
      boundaries for local Git, GitHub publication, Spec Kit adoption, issue
      compilation, and persistent influence.
- [x] **T092** [US2,US7] Define positive and negative routing, including
      explicit-only project-init selection.
- [x] **T093** [US3,US7] Pin the reviewed official Spec Kit Codex integration and
      select an additive CxPP extension rather than a preset, bundle, or
      hand-authored substitute scaffold.
- [x] **T094** [US7] Define the blocking artifact-readiness checks and explicit
      approval boundary.
- [x] **T095** [US1,US7] Define stage/story grouping, rich issue bodies, stable
      sync identity, open/closed idempotency, and feature-ledger write-back.
- [x] **T096** [US1-US7] Assign implementation, evaluation, consent, and rollout
      responsibilities to issues #158 through #163.
- [x] **T097** [US3,US7] Publish and test the versioned machine-readable
      composition contract without changing runtime behavior.

**Checkpoint:** Issue #166 has one reviewed decision record and schema-validated
contract; every runtime change has exactly one open Wave 7 owner.

---

## Stage 1: `project-next` Fidelity Vertical Slice

- [x] **T101** [US1] Write a shared `project-next` behavioral contract covering
      inputs, classification sets, ranking, top action, next startable issue,
      modes, uncertainty, and failure states.
- [x] **T102** [US1] Decide and document the durable CPP/CxPP source-of-truth and
      generation boundary; create/link a CPP twin issue if required.
- [x] **T103** [US1] Add structured repository-state and recommendation models
      under `lib/project_next/`.
- [x] **T104** [US1] Implement deterministic in-flight mapping, dependency graph,
      transitive/cycle blocking, availability validation, and uncertainty.
- [x] **T105** [US1] Implement stable ranking for critical work, priority,
      phase/wave, issue type, quick wins, staleness, and tie-breaks.
- [x] **T106** [US1] Implement top-action selection separately from the next new
      issue that is safe to start.
- [x] **T107** [US1] Add a git/gh/spec collection adapter that reports incomplete
      inventories and rate-limit/authentication failures without false certainty.
- [x] **T108** [US1] Add harness-neutral project-next configuration with schema,
      defaults, validation, and examples.
- [x] **T109** [US1] Update the Codex skill to call the deterministic core and
      render versioned `--brief`, compact, and `--full` outputs.
- [x] **T110** [P] [US1,US4] Add fixtures for active PRs, remote branches, dirty
      worktrees, reviews, CI failures, epics, priorities, dependency chains,
      cycles, ambiguity, and unsynchronized spec tasks.
- [x] **T111** [US1,US4] Add end-to-end fixture and dogfood tests against both
      power-pack repositories.
- [x] **T112** [US1] Reconcile or retire the conflicting generated/native
      `project-next` exception so only the documented ownership model remains.

**Checkpoint:** The deterministic fixtures select the expected top action and
next-startable issue with 100% accuracy; no in-flight or blocked issue leaks;
all three output modes pass; CxPP dogfood no longer needs a Claude rerun.

---

## Stage 2: Invocation and Metadata Normalization

- [x] **T201** [US2] Replace user-facing faux skill slash commands with
      `$skill-name` or `/skills` across CxPP skills, plugin manifests, README,
      AGENTS.md, and focused docs.
- [x] **T202** [US2] Add a migration table for historical CPP command syntax,
      current Codex explicit selection, and natural-language invocation.
- [x] **T203** [US2] Rewrite priority skill descriptions around user goals,
      trigger terms, boundaries, and negative cases; remove truncation and fixed
      repository names.
- [x] **T204** [US2] Validate that every plugin and skill `default_prompt`
      selects a capability bundled by that plugin.
- [x] **T205** [US2,US4] Establish the first curated implicit-entrypoint set from
      golden-prompt results; keep secondary/help/admin skills explicit unless
      measured evidence supports implicit use.
- [x] **T206** [P] [US2] Add per-plugin fresh-install prompt-inventory tests.
- [x] **T207** [P] [US2] Add recommended-profile and full-suite inventory,
      uniqueness, priority-preservation, and metadata-budget tests.
- [x] **T208** [US2,US6] Version plugin payloads and document the new-session or
      reinstall boundary required to pick up metadata changes.
- [x] **T209** [US2,US7] Align project-init skill, help, agent metadata, plugin
      manifest, and starter prompts to the explicit local Python scaffold.
- [x] **T210** [US2,US7] Add negative routing for existing-repository
      orientation, next-work analysis, publication, Spec Kit adoption, issue
      synchronization, and ordinary repository changes.
- [x] **T211** [US7] Present publication, adoption, synchronization, and
      persistent influence only as separately consented owning-workflow
      handoffs.

**Checkpoint:** All advertised invocation paths work in a fresh session, starter
prompts resolve, and priority skill activation meets the initial thresholds.

---

## Stage 3: Semantic Compatibility and Packaging Gates

- [ ] **T301** [US3] Implement cross-skill reference extraction and resolution
      against native Codex commands, packaged skills, and reviewed exclusions.
- [ ] **T302** [US3] Implement operational host/path detection for `.claude/`,
      Claude marketplace commands, Claude-only tools, fixed CPP runtime paths,
      and unsupported invocation syntax.
- [ ] **T303** [US3] Implement metadata validation for repository neutrality,
      trigger quality, truncation, starter prompts, and implicit policy.
- [ ] **T304** [US3] Reconcile source, packaged, marketplace, and installed
      inventories through `.agents/skill-contracts.json`.
- [ ] **T305** [US3] Require owner, rationale, replacement, and review date for
      every deliberate exclusion.
- [ ] **T306** [US3] Repair or explicitly retire the unpackaged/dangling
      `flow-repair`, `flow-auto_codex`, `cicd-woodpecker`, browser, and `cpp-*`
      references identified by the baseline.
- [ ] **T307** [P] [US3] Repair CI/CD skill state paths and runtime discovery so
      CxPP does not require a CPP checkout.
- [ ] **T308** [P] [US3] Repair flow help/runtime guidance and close or re-scope
      existing issue #140 based on verified target-repository resolution.
- [ ] **T309** [P] [US3] Repair repository-neutral GitHub metadata and examples.
- [ ] **T310** [US3] Resolve existing issue #135's completeness exit bar and
      record keep/adapt/exclude decisions for every affected surface.
- [ ] **T311** [US3,US4] Integrate semantic validation into `make verify` and CI
      while retaining hash-parity and focused harness-lint checks.
- [ ] **T312** [US3,US7] Pin official Spec Kit adoption to the reviewed release,
      record the installed version, preserve the Codex integration, and require
      path-level approval before any forced replacement.
- [ ] **T313** [US3,US7] Implement the CxPP readiness and issue-compilation
      boundary as an official Spec Kit extension without overriding core
      authoring templates.
- [ ] **T314** [US3,US7] Retire duplicate compilers from evaluate, project-init,
      project-next, generated payloads, and plugin payloads so `spec-sync` is
      the sole owner.
- [ ] **T315** [US7] Validate canonical task syntax and block missing artifacts,
      consistency errors, placeholders, vague paths, missing independent tests,
      unresolved dependencies, and absent approval.
- [ ] **T316** [US7] Implement explicit stage, story, and task grouping with
      independently deliverable stage/story groups as the default.
- [ ] **T317** [US1,US7] Render complete issue bodies with outcome, tasks,
      traceability, acceptance, dependencies, constraints, quality commands,
      immutable artifact links, and stable sync identity.
- [ ] **T318** [US1,US7] Synchronize idempotently across open and closed issues
      and write issue number, URL, state, and stable group identity back to the
      selected feature task ledger.
- [ ] **T319** [US7] Keep project-init limited to offering `spec-adopt` and
      `spec-sync` as separate handoffs; never create placeholder artifacts or
      GitHub issues automatically.
- [ ] **T320** [US1,US7] Replace project-next's task-ID synchronization heuristic
      with stable stage/story/task mappings, follow mapped dependencies, and
      report missing, stale, or ambiguous mappings as uncertainty.

**Checkpoint:** Every published family passes semantic validation; all links
resolve; operational host mismatches require narrow reviewed adaptations; the
source/package/marketplace inventory is complete.

---

## Stage 4: Activation and Outcome Evaluation Harness

- [ ] **T401** [US4] Implement evaluation-case parsing, validation, filtering,
      and machine-readable results.
- [ ] **T402** [US4] Add deterministic procedure and output-contract evaluators
      for `project-next` and other priority skills.
- [ ] **T403** [P] [US4] Add direct, indirect, negative, incomplete, and edge
      activation cases for every implicit entrypoint.
- [ ] **T404** [US4] Implement an isolated, bounded `codex exec --json` live lane
      that records selected skill and safe contract checkpoints.
- [ ] **T405** [US4] Classify results as unavailable, activation failure,
      procedure failure, runtime failure, output failure, or pass.
- [ ] **T406** [US4] Add timeout, case-count, model, cost/budget, redaction, and
      artifact-retention controls for live runs.
- [ ] **T407** [US4] Run deterministic evaluations on every PR and document the
      manual/scheduled live cadence and release-gating policy.
- [ ] **T408** [US4] Publish a concise baseline-versus-current scorecard for
      priority skills without storing prompts or data that contain secrets.
- [ ] **T409** [US2,US4,US7] Add direct project-init activation and negative
      orientation, publication-only, adoption-only, sync-only, and existing-repo
      activation cases.
- [ ] **T410** [US4,US7] Add local scaffold and separate-consent fixtures for
      publication, Spec Kit adoption, and declined handoffs.
- [ ] **T411** [US4,US7] Add canonical, malformed, multiline, placeholder,
      zero-task, multiple-feature, and dependency parser fixtures.
- [ ] **T412** [US4,US7] Add golden stage/story/task issue bodies, open/closed
      idempotency, mapping write-back, and stale-mapping repair fixtures.
- [ ] **T413** [US1,US4,US7] Add an isolated dry run from local scaffold through
      pinned adoption, readiness, preview, mapping, and project-next consumption.

**Checkpoint:** Direct recall is 100%, indirect recall is at least 90% for
implicit priority skills, negative precision is at least 95%, and evaluation
failures identify the failing contract layer.

---

## Stage 5: Consent-First Persistent Influence

- [ ] **T501** [US5] Author a concise outcome-based CxPP routing block for target
      repository `AGENTS.md`, with a documented byte budget.
- [ ] **T502** [US5] Add idempotent preview, approve, unchanged, skip, conflict,
      and removal behavior to `cxpp-init` and `cxpp-update`.
- [ ] **T503** [US5] Package the reviewed PostToolUse masking hook with the
      secrets plugin and use `${PLUGIN_ROOT}`-relative commands.
- [ ] **T504** [US5] Package only the reviewed friction-capture lifecycle hooks
      with the self-improvement plugin; keep codification and external writes
      explicit.
- [ ] **T505** [US5] Extend `cxpp-status` to report routing-block state, hook
      presence, trust/review state when exposed, enabled state, and drift without
      printing configuration contents.
- [ ] **T506** [P] [US5] Add clean install, decline, already-current, changed-hook,
      untrusted, disabled, removal, and plugin-uninstall tests.
- [ ] **T507** [P] [US5] Add security tests proving hooks fail open, mask output,
      avoid secrets, and never grant permissions or invoke shipping actions.
- [ ] **T508** [US5,US7] Prove project-init never installs persistent influence
      and that declining its `cxpp-init` handoff leaves only the local scaffold.

**Checkpoint:** Persistent influence is transparent, consent-first, trust-
reviewed, status-visible, and fully removable; declining it leaves the ordinary
skill workflow intact.

---

## Stage 6: Rollout, Documentation, and Closeout

- [ ] **T601** [US6] Update README, AGENTS.md, plugin help, architecture, and
      troubleshooting documentation to match the released invocation and
      influence model.
- [ ] **T602** [US6] Publish migration and rollback guidance covering explicit
      selection, implicit-policy changes, hook trust, new-session requirements,
      and persistent-guidance removal.
- [ ] **T603** [US6] Validate minimal, recommended, full, upgrade, and rollback
      installs at immutable commit SHAs or signed release tags.
- [ ] **T604** [US4,US6] Run at least 20 representative dogfood sessions and
      record aggregate activation and fidelity results.
- [ ] **T605** [US2,US4] Revisit the implicit-entrypoint set using measured
      precision, recall, catalogue budget, and user feedback.
- [ ] **T606** [US3,US6] Close, re-scope, or create follow-ups for #135, #140,
      exclusions, and any deferred family-specific repairs based on evidence.
- [ ] **T607** [US6] Cut the release, record resolved and rollback refs, and
      verify `cxpp-status` against the installed payload in a fresh session.
- [ ] **T608** [US6] Mark the wave complete only after all spec success criteria
      and repository quality gates pass.
- [ ] **T609** [US6,US7] Dogfood a clean project through local scaffold,
      optional publication, pinned adoption, readiness, stage/story sync,
      project-next, and flow-auto.
- [ ] **T610** [US6,US7] Verify adoption install and rollback against immutable
      Spec Kit and CxPP release refs.
- [ ] **T611** [US6,US7] Publish migration from duplicate compilers and one-line
      task issues, retaining task-granular sync only as an explicit option.
- [ ] **T612** [US6,US7] Include issue outcome, traceability, independent
      acceptance, dependency, command, and immutable-link quality in rollout
      evidence.

**Checkpoint:** Migration and rollback are proven, 20 dogfood sessions meet the
quality thresholds, and repository documentation matches an immutable released
payload.

---

## Dependency Graph

```text
Stage 0 baseline
    |
    +--> Stage 1 project-next vertical slice
    |
    +--> Stage 2 invocation and metadata
              |
              v
        Stage 3 semantic gates
              |
              v
        Stage 4 evaluation harness
              |
              v
        Stage 5 persistent influence
              |
              v
        Stage 6 rollout and closeout
```

- Stage 1 and the early metadata drafting in Stage 2 may proceed in parallel
  after Stage 0.
- Stage 3 needs the Stage 2 invocation contract so it validates the intended
  syntax rather than legacy prose.
- Stage 4 needs the Stage 1 output contract and Stage 2 activation cases.
- Stage 5 needs the semantic gate and evaluation taxonomy before adding
  persistent surfaces.
- Stage 6 depends on every earlier checkpoint.

---

## Issue Sync

> After this specification PR merges, use `$spec-sync` in preview mode and
> create one story issue per implementation stage. Do not create per-task
> micro-issues until the owning stage issue confirms that granularity is useful.

| Stage | Tasks | Issue | Status |
|-------|-------|-------|--------|
| Specification | spec.md, plan.md, tasks.md | #153 | complete |
| 0 - Baseline | T001-T006 | #157 | complete |
| Composition prerequisite | T090-T097 | #166 | in progress |
| 1 - project-next | T101-T112 | #158 | complete |
| 2 - Invocation/metadata | T201-T211 | #159 | open |
| 3 - Semantic gates | T301-T320 | #160 | open |
| 4 - Evaluations | T401-T413 | #161 | open |
| 5 - Persistent influence | T501-T508 | #162 | open |
| 6 - Rollout | T601-T612 | #163 | open |

Completion sequence: #157 and #158 are complete. #166 unlocks #159 and the
project-next mapping integration now assigned to #160; #159 unlocks #160; #160
unlocks #161; #160 and #161 jointly unlock #162; #158 through #162 plus #166
must close before #163 can close the wave.

---

## Notes

- Each stage is independently mergeable and must leave `make verify` green.
- Stage issues should cite the relevant specification user stories and copy the
  stage checkpoint into their acceptance criteria.
- Existing user changes and unrelated untracked files must not be included in
  implementation PRs.
- A live evaluation failure never authorizes bypassing deterministic safety,
  verification, approval, or release gates.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
