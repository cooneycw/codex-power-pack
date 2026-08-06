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
- Start with `--dry-run`. GitHub issue creation and ledger write-back are
  external/local writes and need explicit user confirmation after the preview.
- Re-runs are idempotent across open and closed issues using hidden stable
  identities; changed titles never create duplicates.
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
   and existing open/closed mapping. Ask for explicit approval.
5. After approval, re-run with `--approve` instead of `--dry-run`. Use `--repo
   OWNER/REPO` only when the user intentionally targets a repository other than
   `origin`.
6. Verify that the Issue Sync ledger in `tasks.md` contains issue number, URL,
   state, granularity, group ID, and stable identity for every synchronized
   group. Report partial writes as unresolved; never claim full synchronization.
7. Recommend `$flow-auto <issue>` in dependency order.

## Report

Report the artifact commit, selected task file, repository, granularity,
readiness result, created/skipped groups, ledger result, and unresolved
dependencies. State explicitly that created issues are label-free by design.
