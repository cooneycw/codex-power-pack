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

## Stage 1: `project-next` Fidelity Vertical Slice

- [ ] **T101** [US1] Write a shared `project-next` behavioral contract covering
      inputs, classification sets, ranking, top action, next startable issue,
      modes, uncertainty, and failure states.
- [ ] **T102** [US1] Decide and document the durable CPP/CxPP source-of-truth and
      generation boundary; create/link a CPP twin issue if required.
- [ ] **T103** [US1] Add structured repository-state and recommendation models
      under `lib/project_next/`.
- [ ] **T104** [US1] Implement deterministic in-flight mapping, dependency graph,
      transitive/cycle blocking, availability validation, and uncertainty.
- [ ] **T105** [US1] Implement stable ranking for critical work, priority,
      phase/wave, issue type, quick wins, staleness, and tie-breaks.
- [ ] **T106** [US1] Implement top-action selection separately from the next new
      issue that is safe to start.
- [ ] **T107** [US1] Add a git/gh/spec collection adapter that reports incomplete
      inventories and rate-limit/authentication failures without false certainty.
- [ ] **T108** [US1] Add harness-neutral project-next configuration with schema,
      defaults, validation, and examples.
- [ ] **T109** [US1] Update the Codex skill to call the deterministic core and
      render versioned `--brief`, compact, and `--full` outputs.
- [ ] **T110** [P] [US1,US4] Add fixtures for active PRs, remote branches, dirty
      worktrees, reviews, CI failures, epics, priorities, dependency chains,
      cycles, ambiguity, and unsynchronized spec tasks.
- [ ] **T111** [US1,US4] Add end-to-end fixture and dogfood tests against both
      power-pack repositories.
- [ ] **T112** [US1] Reconcile or retire the conflicting generated/native
      `project-next` exception so only the documented ownership model remains.

**Checkpoint:** The deterministic fixtures select the expected top action and
next-startable issue with 100% accuracy; no in-flight or blocked issue leaks;
all three output modes pass; CxPP dogfood no longer needs a Claude rerun.

---

## Stage 2: Invocation and Metadata Normalization

- [ ] **T201** [US2] Replace user-facing faux skill slash commands with
      `$skill-name` or `/skills` across CxPP skills, plugin manifests, README,
      AGENTS.md, and focused docs.
- [ ] **T202** [US2] Add a migration table for historical CPP command syntax,
      current Codex explicit selection, and natural-language invocation.
- [ ] **T203** [US2] Rewrite priority skill descriptions around user goals,
      trigger terms, boundaries, and negative cases; remove truncation and fixed
      repository names.
- [ ] **T204** [US2] Validate that every plugin and skill `default_prompt`
      selects a capability bundled by that plugin.
- [ ] **T205** [US2,US4] Establish the first curated implicit-entrypoint set from
      golden-prompt results; keep secondary/help/admin skills explicit unless
      measured evidence supports implicit use.
- [ ] **T206** [P] [US2] Add per-plugin fresh-install prompt-inventory tests.
- [ ] **T207** [P] [US2] Add recommended-profile and full-suite inventory,
      uniqueness, priority-preservation, and metadata-budget tests.
- [ ] **T208** [US2,US6] Version plugin payloads and document the new-session or
      reinstall boundary required to pick up metadata changes.

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
| Contract augmentation | project-init / Spec Kit | #166 | open |
| 1 - project-next | T101-T112 | #158 | open |
| 2 - Invocation/metadata | T201-T208 | #159 | open |
| 3 - Semantic gates | T301-T311 | #160 | open |
| 4 - Evaluations | T401-T408 | #161 | open |
| 5 - Persistent influence | T501-T507 | #162 | open |
| 6 - Rollout | T601-T608 | #163 | open |

Completion sequence: #157 is complete. The #158 core and #166 may proceed in
parallel; #166 unlocks #159 and the issue-mapping slice of #158; #159 unlocks
#160; #158 and #160 jointly unlock #161; #160 and #161 jointly unlock #162;
#158 through #162 plus #166 must close before #163 can close the wave.

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
