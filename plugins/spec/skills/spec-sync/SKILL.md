---
name: spec-sync
description: Compile approved Spec Kit artifacts into dependency-aware, idempotent GitHub issues and ledger mappings for Flow.
---

# Spec Sync

Compile one approved Spec Kit feature into independently deliverable stage or
story issues. Per-task issues are an explicit compatibility mode. This is the
sole CxPP issue compiler: `gh` CLI only, no GitHub MCP server and no label
adapter.

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

The artifact check establishes that the reviewed commit and artifact paths
exist. It does not attest that working artifact bytes equal that commit; the
separate #223 handoff work owns that recorded limitation.
