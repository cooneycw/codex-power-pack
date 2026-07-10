---
name: "cxpp-update"
description: "Refresh Codex Power Pack host wiring additively and with explicit consent"
---

# CxPP Update

Use this skill for `/cxpp:update` when an installed Codex Power Pack setup needs
an additive refresh without overwriting user-managed configuration.

## Procedure

1. Run the read-only checks in `/cxpp:status` first and summarize missing,
   unhealthy, or drifted components.
2. Compare requested MCP pointers with `templates/config.toml.example` using
   `codex mcp get`; do not print or parse the full global configuration file.
3. For each change, show the precise additive action and ask for approval. Never
   delete a pointer, plugin, hook, rule, or user configuration entry.
4. Reinstall or upgrade plugins only from a signed release tag or immutable
   commit SHA after the user confirms the target ref. Keep the prior ref in the
   report for rollback.
5. Re-run `codex execpolicy check` before adding or changing any rule, and let
   Codex perform its normal hook-review flow for changed hook files.
6. Re-run the non-secret MCP checks and report whether a fresh Codex session is
   needed. Do not manage the lifecycle of an external host service.

## Report

Separate `updated`, `already current`, `skipped by user`, and `needs host
prerequisite`. Include the previous and requested pinned plugin refs whenever a
plugin changes.
