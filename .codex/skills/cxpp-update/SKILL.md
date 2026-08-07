---
name: "cxpp-update"
description: "Refresh Codex Power Pack host wiring additively and with explicit consent"
---

# CxPP Update

Use this skill for `$cxpp-update` when an installed Codex Power Pack setup needs
an additive refresh without overwriting user-managed configuration.

## Plugin Suite Profiles

When the marketplace is missing or published family plugins are absent, offer:

- **Minimal**: `cxpp` only.
- **Recommended**: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
  `security`, `agents-md`, `documentation`, `qa`, `self-improvement`, and
  `cxpp`, plus `claude`.
- **Full suite**: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
  `woodpecker`, `security`, `agents-md`, `documentation`, `qa`, `evaluate`,
  `second-opinion`, `self-improvement`, `cxpp`, and `claude`.
- **Custom**: one or more names from the full-suite list. Reject unknown names,
  de-duplicate in full-suite order, and treat an empty selection as `skipped by
  user`.

Suite approval covers only marketplace and plugin installation. It never
authorizes MCP pointers, credentials or provider setup, hooks, or
exec-policy rules. It also never authorizes external-service lifecycle changes;
retain their existing individual prompts.

## Procedure

1. Run the read-only checks in `$cxpp-status` first and summarize missing,
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
   resolved SHA, and exact marketplace/plugin commands. Codex 0.146.1 cannot
   retarget an existing marketplace source with another `marketplace add`; if
   the ref changes, preview the bounded `codex plugin marketplace remove
   codex-power-pack --json` followed immediately by the pinned `marketplace
   add` and plugin reinstalls. This replaces only the marketplace snapshot;
   it does not remove installed plugins or authorize any other deletion.
4. After explicit approval, expand an unchanged sparse marketplace snapshot,
   or perform the previewed marketplace-source replacement when the ref
   changes, then reinstall every preserved/selected family at the new snapshot.
   If the new snapshot cannot be added, restore the recorded previous ref;
   existing plugin installs remain in place during recovery. Preserve all
   other configuration and re-run `$cxpp-status` to verify the result.
5. Inspect optional target routing with the checkout
   `scripts/cxpp-influence.py` or installed
   `${PLUGIN_ROOT}/scripts/cxpp-influence.py`. For `absent` or `upgrade`,
   run `python3 HELPER preview TARGET` and require separate explicit approval
   before `python3 HELPER apply TARGET --approve`. Report `current` without
   writing. Stop on `conflict` rather than overwriting user edits. Require
   `python3 HELPER preview-remove TARGET` before `python3 HELPER remove TARGET
   --approve`; a decline runs `python3 HELPER decline TARGET` and writes
   nothing.
6. Compare requested MCP pointers with `templates/config.toml.example` using
   `codex mcp get`; do not print or parse the full global configuration file.
7. For each host change, show the precise additive action and ask for separate
   approval. Never delete a pointer, plugin, hook, rule, or user configuration
   entry.
8. Re-run `codex execpolicy check` before adding or changing any rule. Plugin
   installation does not authorize hook trust or enablement; use `/hooks` for
   exact-hash review, and require a new review whenever a hook changes.
9. Re-run the non-secret MCP checks and report whether a fresh Codex session is
   needed. Do not manage the lifecycle of an external host service.

## Report

Separate `updated`, `already current`, `skipped by user`, and
`needs host prerequisite`. Include the previous ref, requested signed tag or
immutable SHA, and resolved SHA whenever a marketplace or plugin changes so
rollback remains possible. Re-running an unchanged selection at the same
resolved SHA must be idempotent and report `already current`. Include target
routing state and hook trust/enabled state without printing file contents.
