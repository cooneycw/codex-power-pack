---
name: project-lite
description: Give a low-context orientation for the current repository, including repo identity, branch status, worktrees, key files, commands, and available project workflow skills. Use when starting a session, after context compaction, or when Codex needs quick project orientation without full issue triage.
---

# Project Lite

Summarize the current repository with minimal context.

## Procedure

1. Resolve basics:
   - Run `pwd`.
   - Run `git status --short --branch`.
   - Run `gh repo view --json nameWithOwner,defaultBranchRef,url` when GitHub context is available.
2. Read only the highest-signal local files:
   - `AGENTS.md`
   - `README.md`
   - `Makefile`
   - `.agents/plugins/marketplace.json`, when present
3. Inspect workflow shape:
   - Run `git worktree list --porcelain`.
   - Run `rg --files -g 'pyproject.toml' -g 'package.json' -g 'go.mod' -g 'Cargo.toml' -g '.codex/**' -g 'plugins/**'`.
4. Report:
   - Repository identity and current branch.
   - Dirty files or untracked files that matter.
   - Main commands to verify or ship work.
   - Available project workflow commands, especially `project-next`, `project-init`, and `flow-auto` when present.

Keep the report short. Do not scan all source files unless the user asks for deeper analysis.
