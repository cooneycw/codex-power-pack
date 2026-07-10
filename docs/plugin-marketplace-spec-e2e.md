# Spec Plugin E2E Gate

Issue #83's dogfood gate confirms that the native `spec` marketplace package
delivers the Codex-owned workflow without bundling a GitHub MCP server or a
label adapter.

## Local package checks

1. Install the marketplace from a pinned release tag or immutable commit SHA
   with sparse paths `.agents` and `plugins/spec`.
2. Install the package with `codex plugin add spec@codex-power-pack`.
3. Start a fresh Codex session and invoke `$spec-adopt` in a disposable Git
   repository. Confirm that it first requests consent for the user-scoped
   `specify` installation and then uses `specify init --here --integration codex`.
4. Create a minimal `.specify/specs/example/tasks.md` containing `T001` and
   `T002` task entries. Invoke `$spec-sync` and confirm that it presents the
   dry-run before any GitHub write.
5. Run the bundled helper with `--dry-run --tasks <path>` and verify that it
   proposes label-free `TNNN: description` titles. Do not use a GitHub MCP
   server.

## Recorded result

On 2026-07-10, Codex ran `specify 0.12.5.dev0` in a disposable Git repository
with `specify init --here --integration codex --force`. The command created the
official `.specify/` scaffold and installed the Codex integration. Codex then
ran the bundled sync helper against a two-task miniature spec in `--dry-run`
mode; it proposed both `T001` and `T002` label-free issues without contacting
GitHub or requiring a GitHub MCP server.

The repository-level automated gate also covers package/source parity, the
consent-first adoption contract, and the helper's offline `--help` interface.
The live GitHub create step remains explicitly user-confirmed because it creates
external issues.
