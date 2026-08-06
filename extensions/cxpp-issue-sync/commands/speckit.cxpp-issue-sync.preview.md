---
description: "Validate approved Spec Kit artifacts and preview Flow issue groups"
---

# Preview Codex Power Pack Issue Synchronization

This extension adds readiness analysis and issue compilation after official
Spec Kit authoring. It does not replace or override constitution, specify,
clarify, plan, tasks, analyze, or implementation templates.

## User Input

$ARGUMENTS

## Procedure

1. Confirm the selected feature has `spec.md`, `plan.md`, and a non-empty
   canonical `tasks.md`.
2. Run the official consistency analysis and resolve every reported error.
3. Resolve the reviewed artifact commit to an immutable SHA.
4. Hand the selected task file and SHA to the installed `$spec-sync` skill in
   dry-run mode. Do not create issues or modify the ledger during this command.
5. Show the readiness result, proposed stage/story groups, dependencies, stable
   identities, and immutable artifact links.
6. State that GitHub writes require a separate explicit `$spec-sync` approval.

If the CxPP spec plugin or `$spec-sync` is unavailable, report that prerequisite
and stop. Never fall back to Spec Kit's per-task `taskstoissues` command or copy
another compiler into the project.
