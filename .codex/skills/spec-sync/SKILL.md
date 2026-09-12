---
name: spec-sync
description: Compile approved Spec Kit artifacts into dependency-aware, idempotent GitHub issues and ledger mappings for Flow.
---

# Spec Sync

Compile one approved Spec Kit feature into independently deliverable stage or
story issues. Per-task issues are an explicit compatibility mode. This is the
sole CxPP issue compiler: `gh` CLI only, no GitHub MCP server and no label
adapter.

## Route selection

Use the [canonical CxPP issue contract](https://github.com/cooneycw/codex-power-pack/blob/main/docs/agents/issue-contract.md)
to distinguish a short issue-first change from deliberately selected full-spec
compilation. `$github-issue-create` can author small work without spec/plan/tasks;
this compiler continues to require its full-spec artifacts and every readiness,
analysis, reviewed-commit/path, dependency, approval and recovery check. Link the
governing spec sections instead of copying an entire specification into issues.
Preserve project/user constraints and existing authority. A missing remote
reference should be reported without blocking otherwise authorized routine work
or inventing policy; it does not permit bypassing this compiler's checks.

## Safety Contract

- This skill never reads, prints, or persists credentials.
- It accepts only a GitHub `origin` remote and relies on the user's existing
  `gh` authentication; it never asks for or displays authentication data.
- Start with `--dry-run`. GitHub issue creation, dependency edits, and ledger write-back require
  approval after the preview. Follow the session's declared approval authority;
  an already authorized delegated workflow does not need another human round.
  Otherwise obtain explicit user confirmation.
- Re-runs are idempotent across open and closed issues using hidden stable
  identities scoped to the full repository, tasks path, and group; changed
  titles never create duplicates. Unscoped task titles are never authoritative.
- An empty, failed, malformed, or saturated (1,000 issues) lookup cannot prove
  that a mapping is absent. Stop and obtain complete evidence; do not retry
  creation blindly or treat lookup failure as an empty repository.
- Missing artifacts, dirty consistency analysis, placeholders, malformed task
  syntax, vague paths, missing checkpoints, unresolved dependencies, cycles,
  or absent approval fail loudly.

## Procedure

1. Confirm `gh` is installed and authenticated using `gh auth status`; report a
   missing login without displaying its details.
2. Select exactly one `.specify/specs/<feature>/tasks.md` and the reviewed
   immutable artifact commit. Confirm the official consistency analysis is
   clean.
3. Preview independently deliverable groups with the packaged helper:

   ```bash
   scripts/speckit-tasks-to-issues.sh --dry-run --analysis-clean \
     --artifact-commit <sha> --tasks <tasks.md>
   ```

   Use `--granularity story` when the approved boundary is user-story based, or
   `--granularity task` only when the user explicitly requests micro-issues.
4. Show every group, task, dependency, stable identity, immutable artifact ref,
   and existing open/closed mapping. Include old and proposed dependency edges,
   removals, and unresolved new prerequisite groups. Obtain approval under the
   active session authority; `--approve` also guards edit-only and ledger-only runs.
5. After approval, re-run with `--approve` instead of `--dry-run`. Use `--repo
   OWNER/REPO` only when the user intentionally targets a repository other than
   `origin`.
6. Verify that the Issue Sync ledger in `tasks.md` contains issue number, URL,
   state, granularity, group ID, and stable identity for every synchronized
   group. Report partial writes as unresolved; never claim full synchronization.
7. Recommend `$flow-auto <issue>` in dependency order.

## Report

Report the artifact commit, selected task file, repository, granularity,
readiness result, created/edited/skipped groups, ledger result, and unresolved
dependencies. State explicitly that created issues are label-free by design.


## Grouping and identity compatibility

Plain `T001` and bold `**T001**` checkbox IDs are accepted. Auto grouping remains
stage-first, then story; `--granularity task` remains explicit. Story checkpoints
can be declared under `## US1: Title` or `## User Story 1 - Title` headings.
Tasks under a story heading inherit that story if they have no tag; conflicting
tags fail. A stage checkpoint is reused for story mode only when exactly one
story owns the same complete task set. Mixed stories, story fragments across
stages, repeated owners, or conflicting checkpoints require explicit boundaries.
A checkpoint under a story subheading belongs to that story. Stage auto grouping
still requires a stage checkpoint; declare it at the stage heading before any
story subheadings.

Stable identity remains `spec-sync:v1:<owner/repo>:<tasks-path>:<group-id>`.
The compiler selects exact mappings before resolving local dependencies. It
validates the entire conversion, including collapsed group cycles and ledger
markers, before creating prerequisites in stable dependency order. A valid
within-group task dependency is not a group cycle. Closed exact mappings are
reused and may have their managed dependencies reconciled with approval.

## Dependency repair and legacy resolution

New bodies delimit compiler-managed dependency lines with
`spec-sync-dependencies:start sha256=...` / `spec-sync-dependencies:end` comments.
The checksum detects changes; it is not authentication or evidence of consent.
Only an unchanged managed span inside the unique exact issue mapping is eligible
for replacement. Text outside the span is preserved byte-for-byte, including
human-added edges. Custom or duplicate spans fail with a reconciliation
instruction. Preview the old and proposed edges before approving any removal.

An unmarked legacy section whose edges already match needs no edit or ownership
transfer. A mismatch stops the whole conversion before writes and reports the
issue, state, current section and desired edges. To resolve it:

1. Review the listed issue against the approved tasks and distinguish compiler
   prerequisites from human-added requirements. Never adopt by a task title.
2. Explicitly reconcile the section with the desired edges, retaining human
   requirements. If all prerequisite issue numbers exist, an exact matching
   unmarked section can remain unmarked. If prerequisites still need creation,
   explicitly delimit only the reviewed compiler lines as a managed span and
   leave human requirements outside it. To render a span locally, call
   `managed_dependencies(content)` from `scripts/spec_sync.py`; for example:

   ```bash
   python3 -c 'import runpy; compiler = runpy.run_path("scripts/spec_sync.py"); print(compiler["managed_dependencies"]("- Pending group `stage-2`"))'
   ```

   This prints text only. Applying it to the issue is a deliberate reconciliation
   under the existing approval authority, not automatic legacy adoption.
3. Run `--dry-run` again, review removals/additions and then use `--approve`.
   An unscoped legacy title/body candidate also needs explicit identity
   resolution before any new mapping can be created; even one candidate is
   ambiguous. A unique exact mapping outranks that heuristic.

Before each edit the compiler re-reads the target body, identity and state.
Intervening changes abort and require another preview. GitHub body edits are
not atomic compare-and-swap: a race after that final read remains possible.
On a later create/edit/ledger failure, the error includes completed actions and
the failed or uncertain operation with its stable identity/issue when known.
Do not claim full synchronization or retry an uncertain create blindly. Re-run
the preview using the current inventory; stable identities recover successful
creates, current managed bodies recover edits, and ledger write-back follows
only after every selected group succeeds. A converged rerun makes no issue edit.

The compiler reads frozen raw artifact objects and checks working bytes before
writes, permitting only a verified deterministic task-ledger successor. The
clean-analysis flag remains a caller assertion, not bound official-analysis proof.

## Governing context and coherent refresh (#223)

The compiler freezes regular Git object bytes for spec/plan/tasks at the reviewed
commit and checks local files before writes. `--repo` must match the trusted GitHub
origin; cross-repository attestation is refused. Only a validated deterministic ledger
successor may differ locally from reviewed tasks. Raw SHA256s never normalize newlines
or whitespace. A caller's `--analysis-clean` is not bound official-analysis evidence.

Generated issues carry `spec-sync-context/v1`: scoped source outcomes, acceptance,
constraints/plan decisions, exact task identity and immutable raw hashes. Unmapped,
unsupported or capped context is disclosed, never treated as complete/no constraints.
The 8 KiB extract is a cache, not approval or a second requirement store.

Changed governing source blocks the **whole** default synchronization before creates,
dependency repairs or ledger updates. Review `--refresh-context --dry-run`, then use
the existing `--approve` path. The complete owned governing view and separate owned
dependencies update together; human text/decisions outside remain byte-preserved.
Edited/damaged/overlapping regions refuse. Legacy unmarked bodies need explicit whole-
body reconciliation, not automatic adoption or a competing appended view. Ordinary
legacy analysis remains available. Preview provides a proposed replacement.

An optional `--revision-reference` names an existing decision to inspect; it grants no
authority. Material changes need the existing judge first, then actual newly bound text
and evidence. Old approvals/receipts retain their old binding. Reconcile incomplete or
uncertain writes from successful actions and actual issue state before retrying.

The standalone installed checker reconstructs governing TEXT and raw hashes before
flow planning and after stale/resumed context. This is retrieval evidence, not proof of
acknowledgement, comprehension, live compaction recovery or #201 admission. See the
[context contract](https://github.com/cooneycw/codex-power-pack/blob/main/docs/spec-sync-governing-context.md)
for ownership, source/mapping budgets, ledger rules, recovery and remaining acceptance.
