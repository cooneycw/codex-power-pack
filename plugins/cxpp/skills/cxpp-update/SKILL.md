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

   Resolve the hook-transition helper from checkout
   `scripts/cxpp-hook-transition.py` or installed
   `${PLUGIN_ROOT}/scripts/cxpp-hook-transition.py`. Before approval, run its
   read-only `preflight` operation with one `--family` argument for every
   preserved/selected family. If it reports unfinished recovery snapshots,
   stop before changing the marketplace and use the recovery procedure below.
   When `secrets` or `self-improvement` is selected, explain that the approved
   reinstall will retain byte-identical copies at every old versioned hook path;
   it will not symlink or repoint an already reviewed path to new bytes. Preview
   the single helper command as well as each `codex plugin add` it will execute.
4. After explicit approval, expand an unchanged sparse marketplace snapshot,
   or perform the previewed marketplace-source replacement when the ref
   changes. If any preserved/selected family is hook-bearing, reinstall the
   complete family union in one process with:

   ```text
   python3 HELPER reinstall --marketplace codex-power-pack \
     --family FAMILY [--family FAMILY ...] --approve
   ```

   The helper snapshots every existing `secrets` and `self-improvement` cache
   version before the first reinstall, runs each previewed `codex plugin add`,
   restores missing old roots before returning control to Codex, and rejects a
   reused version path whose bytes changed. Never replace this command with
   separate hook-family installs: the first missing `secrets` path could block
   the command that would restore it. If no hook-bearing family is selected,
   use the ordinary previewed plugin commands. If the new snapshot cannot be
   added, restore the recorded previous ref; existing plugin installs remain in
   place during recovery. Preserve all other configuration and re-run
   `$cxpp-status` to verify the result.
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
9. Re-run the non-secret MCP checks. Existing sessions continue using the exact
   old hook bytes restored at their original paths. If `secrets` or
   `self-improvement` changed, require a new Codex session plus `/hooks`
   exact-hash review before claiming the new hook bytes are active; other old
   sessions may finish normally and must not be told they are already running
   the new hook version. Report whether a fresh session is needed for other
   changes. Do not manage the lifecycle of an external host service.

## Recovery

The helper restores snapshots in `finally` on command failure, interruption,
SIGINT, or SIGTERM. A hard process or host failure can leave snapshots under the
Codex plugin retention directory. Run the same `preflight` command from an
external terminal. After reviewing the reported snapshot count, run `python3
HELPER recover --marketplace codex-power-pack --approve`; this recreates only
missing reviewed roots and digest-checks them. Do not manually recreate cache
files or point an old path at a new plugin version. If the active Secrets hook
prevents in-session commands, recovery must be launched from that external
terminal before the session is used again.

## Report

Separate `updated`, `already current`, `skipped by user`, and
`needs host prerequisite`. Include the previous ref, requested signed tag or
immutable SHA, and resolved SHA whenever a marketplace or plugin changes so
rollback remains possible. Re-running an unchanged selection at the same
resolved SHA must be idempotent and report `already current`. Include the number
of old reviewed hook roots retained/restored, whether recovery snapshots remain,
the new-session exact-hash review boundary, target routing state, and hook
trust/enabled state without printing file contents.
