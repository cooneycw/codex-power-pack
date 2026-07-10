---
name: spec-adopt
description: Install the official GitHub spec-kit workflow for Codex in the current project. Use when a repository needs upstream spec-kit authoring, Codex-flavored initialization, or a safe handoff from a feature spec to flow-auto.
---

# Spec Adopt

Adopt the official [github/spec-kit](https://github.com/github/spec-kit) workflow
in the current repository without replacing an existing specification workspace.

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
3. Explain the user-scoped install command and ask for approval:

   ```bash
   uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
   ```

   If `specify` is already installed, use the documented `uv tool upgrade`
   equivalent only after the user approves the upgrade.
4. After approval and a successful install, initialize the current project with
   the Codex integration:

   ```bash
   specify init --here --integration codex
   ```

   When `.specify/` already exists, do not add `--force` automatically. State
   the conflict and wait for an explicit `--force` request.
5. Verify the result without exposing secrets: check the `specify` version,
   list the created `.specify/` paths, and report the supported next steps:
   constitution → specify → clarify → plan → tasks → `$spec-sync` →
   `$flow-auto <issue>`.

## Report

Report `installed`, `already adopted`, `needs approval`, `needs uv`, or
`initialization failed`. Include the exact non-secret next command and clearly
separate spec adoption from GitHub issue creation.
