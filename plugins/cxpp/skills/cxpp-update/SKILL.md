---
name: "cxpp-update"
description: "Refresh Codex Power Pack host wiring additively and with explicit consent"
---

# CxPP Update

Use this skill for `/cxpp:update` when an installed Codex Power Pack setup needs
an additive refresh without overwriting user-managed configuration.

## Plugin Suite Profiles

When the marketplace is missing or published family plugins are absent, offer:

- **Minimal**: `cxpp` only.
- **Recommended**: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
  `security`, `agents-md`, `documentation`, `qa`, `self-improvement`, and
  `cxpp`.
- **Full suite**: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
  `woodpecker`, `security`, `agents-md`, `documentation`, `qa`, `evaluate`,
  `second-opinion`, `self-improvement`, and `cxpp`.
- **Custom**: one or more names from the full-suite list. Reject unknown names,
  de-duplicate in full-suite order, and treat an empty selection as `skipped by
  user`.

Suite approval covers only marketplace and plugin installation. It never
authorizes MCP pointers, credentials or provider setup, hooks, or
exec-policy rules. It also never authorizes external-service lifecycle changes;
retain their existing individual prompts.

## Procedure

1. Run the read-only checks in `/cxpp:status` first and summarize missing,
   unhealthy, or drifted components.
2. If the marketplace is missing or family plugins are absent, offer Minimal,
   Recommended, Full suite, and Custom. Build the desired family set as the
   union of already installed CxPP families and the selected profile so an
   update never drops an existing family. If the selected set and pinned ref
   are unchanged, report `already current` and perform no write.
3. Require a confirmed signed release tag or immutable commit SHA, resolve a
   tag to its commit SHA, and reject floating refs. Before approval, show the
   selected profile and plugins, every resulting sparse path (`.agents` plus
   `plugins/<family>` in full-suite order), the previous ref, requested ref,
   resolved SHA, and exact additive marketplace/plugin commands.
4. After explicit approval, expand the sparse marketplace snapshot and install
   only missing selected plugins. Preserve existing families and configuration.
   Re-run `/cxpp:status` to verify the result.
5. Compare requested MCP pointers with `templates/config.toml.example` using
   `codex mcp get`; do not print or parse the full global configuration file.
6. For each host change, show the precise additive action and ask for separate
   approval. Never delete a pointer, plugin, hook, rule, or user configuration
   entry.
7. Re-run `codex execpolicy check` before adding or changing any rule, and let
   Codex perform its normal hook-review flow for changed hook files.
8. Re-run the non-secret MCP checks and report whether a fresh Codex session is
   needed. Do not manage the lifecycle of an external host service.

## Report

Separate `updated`, `already current`, `skipped by user`, and
`needs host prerequisite`. Include the previous ref, requested signed tag or
immutable SHA, and resolved SHA whenever a marketplace or plugin changes so
rollback remains possible. Re-running an unchanged selection at the same
resolved SHA must be idempotent and report `already current`.
