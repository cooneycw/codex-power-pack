# Codex Skill Invocation Migration

Codex Power Pack payload `0.2.0+codex.20260807012317` replaces historical
command-shaped guidance with the native Codex skill model. Installation makes a
skill available; it does not necessarily place that skill in every session's
implicit prompt inventory.

## Invocation mapping

| Historical CPP or faux syntax | Current explicit Codex selection | Natural-language example |
|---|---|---|
| `/flow:auto 159` or `/flow-auto 159` | `Use $flow-auto for issue 159.` | “Deliver GitHub issue 159 through its full reviewed lifecycle.” |
| `/project:next` or `/project-next` | `Use $project-next.` | “What is the safest useful thing to work on next here?” |
| `/project:init demo` or `/project-init demo` | `Use $project-init to create local Python project demo.` | Explicit selection is required because scaffolding writes files. |
| `/spec:adopt` or `/spec-adopt` | `Use $spec-adopt.` | Explicit selection is required before installing or initializing Spec Kit. |
| `/spec:sync` or `/spec-sync` | `Use $spec-sync.` | Explicit selection is required before issue-compilation review and approval. |
| Any other `/family:command` or `/skill-name` | Select `$skill-name` or open `/skills`. | Describe the bounded goal; implicit selection occurs only for eligible entrypoints. |

The slash spellings in the first column are migration references, not custom
Codex commands. Native Codex commands such as `/skills` retain their documented
meaning.

## Initial implicit entrypoints

Only `$flow-auto` and `$project-next` are implicitly eligible in this payload.
They are the two priority workflows with versioned golden cases and strong
safety boundaries. Help, administrative, and state-changing workflows remain
available through `$skill-name` and `/skills` without consuming the default
session inventory. In particular, `$project-init` is explicit-only.

The source of truth is
[`skill-invocation-policy.json`](../.agents/skill-invocation-policy.json).
Later releases may revise the set using measured activation precision and
recall; explicit selection remains backward compatible.

The v0.2.0 release review retained this two-entry set after 20 bounded dogfood
sessions reached 100% direct recall, indirect recall, and negative precision.
State-changing CxPP administration, project creation, and Spec Kit workflows
remain explicit-only.

## Upgrade and session boundary

Skill metadata is captured when plugins are installed and when a Codex session
starts. To receive this payload:

1. Upgrade or reinstall the affected plugins at the new signed tag or immutable
   commit.
2. End the existing Codex session.
3. Start a new session and use `codex debug prompt-input` when validating the
   inventory.

Starting a new session without upgrading retains the old installed metadata.
Upgrading a plugin without starting a new session leaves the current session's
already-built skill inventory unchanged. Rollback follows the same two-part
boundary: reinstall the previous immutable ref, then start a new session.

## Persistent routing and hooks

The optional CxPP `AGENTS.md` routing block is managed only through
`$cxpp-init` or `$cxpp-update`. Both show the exact diff and require separate
approval for add, upgrade, or removal. Use `$cxpp-status` to distinguish
`absent`, `current`, `upgrade`, and `conflict`; an edited managed block is never
overwritten.

The `secrets` and `self-improvement` plugins package reviewed hooks, but plugin
installation does not trust or enable them. Review exact hashes with `/hooks`.
Changed hooks require review again. Removing a plugin does not authorize
removing target routing, and removing routing does not authorize uninstalling a
plugin.

## Issue-compilation migration

`$spec-sync` is the sole CxPP compiler for approved Spec Kit artifacts. Retire
duplicate task-to-issue helpers and re-preview their feature with `$spec-sync`
at stage or story granularity. Existing one-line per-task issues keep their
history; do not recreate them. Use task granularity only when explicitly
requested for compatibility, and preserve stable ledger identities across open
and closed issues.

See `docs/wave-7-release-validation.md` for immutable install, rollback, and
clean-project evidence.
