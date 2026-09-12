---
name: spec-adopt
description: Install the official GitHub spec-kit workflow for Codex in the current project. Use when a repository needs upstream spec-kit authoring, Codex-flavored initialization, or a safe handoff from a feature spec to flow-auto.
---

# Spec Adopt

Adopt the official [github/spec-kit](https://github.com/github/spec-kit) workflow
in the current repository without replacing an existing specification workspace.

## Route selection

This is the explicitly selected fuller-spec route in the
[canonical CxPP issue contract](https://github.com/cooneycw/codex-power-pack/blob/main/docs/agents/issue-contract.md).
Routine small work can use a short issue through `$github-issue-create` and does
not need adoption or spec/plan/tasks. Use fuller specs when uncertainty,
architecture or coordination warrants them, and link governing spec sections
from issues. Preserve destination-project instructions and user authority. If
the reference is unavailable, report it and continue otherwise authorized work
without inventing policy. These routes do not relax any adoption boundaries below.

## Safety Contract

- This skill never reads, prints, or persists credentials.
- Installing the `specify` CLI changes the current user's tool environment; show
  the command and obtain explicit approval first.
- Initializing with `--force` can replace spec-kit scaffold files. Refuse that
  mode unless the user explicitly requests it after seeing the affected path.
- Do not create GitHub issues as a side effect of adoption. Use `$spec-sync` for
  the separate, confirmation-gated task-to-issue operation.

## Procedure

1. Confirm that the current directory is the intended project root with
   `git rev-parse --show-toplevel`. If it is not a Git repository, ask the user
   to confirm the target directory before continuing.
2. Inspect `.specify/` and `specify --version` without changing either. If a
   usable `.specify/` directory already exists, report that spec-kit appears
   adopted and stop unless the user requests a refresh.
3. Explain the reviewed, user-scoped install command and ask for approval. The
   release and resolved commit are part of the contract; never substitute a
   moving branch:

   ```bash
   uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.16.0
   ```

   If `specify` is already installed, use the documented `uv tool upgrade`
   equivalent pinned to `v0.16.0` only after the user approves the upgrade.
4. After approval and a successful install, initialize the current project with
   the Codex integration:

   ```bash
   specify init --here --integration codex
   ```

   When `.specify/` already exists, do not add `--force` automatically. First
   show the exact existing paths that initialization would affect, then wait for
   an explicit approval naming those paths before using `--force`.
5. Verify the result without exposing secrets: check the `specify` version,
   list the created `.specify/` paths, and record the reviewed boundary in
   `.specify/spec-kit-version.json` with release `v0.16.0`, commit
   `5dce710ce099067c7d3f2ef47a37b9a1c300b327`, integration `codex`, and the
   installation timestamp. Do not record mutable environment details.
6. Offer the packaged `cxpp-issue-sync` Spec Kit extension as a separate,
   explicitly approved installation. Preview its exact source and destination,
   then use `specify extension add --dev <spec-plugin>/extensions/cxpp-issue-sync`.
   Declining the extension leaves official authoring fully usable and makes no
   project change.
7. Report the supported next steps:
   constitution → specify → clarify → plan → tasks → `$spec-sync` →
   `$flow-auto <issue>`.

## Report

Report `installed`, `already adopted`, `needs approval`, `needs uv`, `version
drift`, or `initialization failed`. Include the recorded release and commit, the
exact non-secret next command, and clearly separate adoption from issue creation.
