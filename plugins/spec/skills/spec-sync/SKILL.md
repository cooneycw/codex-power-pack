---
name: spec-sync
description: Convert official spec-kit tasks.md entries into label-free GitHub issues with the gh CLI. Use when a completed spec-kit task list needs an idempotent issue wave for flow-auto.
---

# Spec Sync

Create one GitHub issue per `TNNN` task in a selected official spec-kit
`tasks.md` file. This is the Codex implementation of the approved Option-B
sync: `gh` CLI only, no GitHub MCP server and no label adapter.

## Safety Contract

- This skill never reads, prints, or persists credentials.
- It accepts only a GitHub `origin` remote and relies on the user's existing
  `gh` authentication; it never asks for or displays authentication data.
- Start with `--dry-run`. GitHub issue creation is an external write and needs
  explicit user confirmation after the dry-run shows the proposed issue titles.
- Re-runs are idempotent: existing `TNNN` titles are skipped across open and
  closed issues.

## Procedure

1. Confirm `gh` is installed and authenticated using `gh auth status`; report a
   missing login without displaying its details.
2. Select exactly one task file. The helper auto-detects a single
   `.specify/specs/*/tasks.md`, or the user may supply `--tasks PATH`.
3. Run the packaged helper in dry-run mode:

   ```bash
   scripts/speckit-tasks-to-issues.sh --dry-run --tasks <tasks.md>
   ```

4. Show the proposed `TNNN: description` titles and the count that will be
   skipped as existing. Ask for explicit approval before proceeding.
5. After approval, re-run the same command without `--dry-run`. Use `--repo
   OWNER/REPO` only when the user intentionally targets a repository other than
   `origin`.
6. Report created and skipped issue URLs, then recommend `$flow-auto <issue>`
   for each independently actionable issue.

## Report

Report the selected task file, target repository, dry-run result, created count,
and skipped count. State explicitly that the created issues have no labels by
design.
