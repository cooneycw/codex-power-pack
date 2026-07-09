# Codex Hooks Friction Telemetry Spike

> Issue: #94
> Scope: Epic E1, plugin marketplace modernization
> Status: recommended design for E2 implementation
> Verified against: Codex manual fetched from
> `https://developers.openai.com/codex/codex-manual.md` on 2026-07-09 and
> local `codex-cli 0.143.0`

## Purpose

Epic E needs Codex friction signals in the shared fleet ledger without turning
hooks, rules, or logs into a secret sink. This spike answers four questions:

- Which Codex lifecycle hooks can observe approval prompts, command failures,
  and tool errors?
- How do Codex rules under `rules/` interact with approval prompts?
- Where must masking happen before any event leaves the local process?
- Should E2 use hooks, wrappers, log tailing, or a combination?

## Current Codex Hook Surface

Codex hooks are enabled by default unless `[features].hooks = false` disables
them. They load from active config layers as either `hooks.json` files or inline
`[hooks]` tables, and from enabled plugin bundles. Project-local hooks load only
for trusted projects. Non-managed command hooks require user review and trust by
hash before they run; changed hook definitions must be reviewed again.

The current hook configuration shape is:

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hook.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Important operational details:

- Matching command hooks from multiple files all run.
- Multiple matching hooks for the same event run concurrently.
- Commands run with the session `cwd`.
- `timeout` is in seconds and defaults to 600 when omitted.
- Only `type: "command"` handlers run today. `prompt`, `agent`, and
  `async: true` handlers are parsed but skipped.
- Matchers are regex strings. Omitted, empty, or `"*"` match every supported
  occurrence.

The repo currently contains older hook examples that use object matchers such as
`{"tool_name": "Bash"}`. E2 should migrate Codex-owned hook templates to the
current regex matcher-group shape instead of copying those legacy examples.

## Event Observability

| Event | Matcher filters | Can see approval prompt? | Can see command failures / tool errors? | Use for E2 |
| --- | --- | --- | --- | --- |
| `SessionStart` | start source: `startup`, `resume`, `clear`, `compact` | No | No | Optional startup health note only. Do not capture friction. |
| `UserPromptSubmit` | ignored | No | No | Secret-shaped prompt guard only. Never store raw prompts. |
| `PreToolUse` | tool name, including `Bash`, `apply_patch`/`Edit`/`Write`, and MCP tool names | No | No, because the tool has not run | Optional local policy guard. Can block high-risk commands before execution. |
| `PermissionRequest` | tool name | Yes. It fires when Codex is about to ask for permission. | No | Primary source for `approval_prompt`. Capture request metadata, not approval outcome. |
| `PostToolUse` | tool name, including `Bash`, `apply_patch`/`Edit`/`Write`, and MCP tool names | No | Yes, after the tool returns | Primary source for command failure, tool error, and secret-mask-hit signals. |
| `PreCompact` | `manual` or `auto` | No | No | Optional flush checkpoint. |
| `PostCompact` | `manual` or `auto` | No | No | Optional compaction marker only. |
| `SubagentStart` | subagent type | No | No | Do not use for ledger capture beyond lifecycle counts. |
| `SubagentStop` | subagent type | No | Only aggregate subagent completion, not per-tool details | Optional aggregate lifecycle signal. |
| `Stop` | ignored | No | Only coarse turn completion | Flush local queue; do not infer missing granular events. |

Notes:

- `PermissionRequest` observes that a prompt was shown. It should not assume the
  user approved or denied the request unless Codex later exposes that decision
  in a documented payload.
- `PostToolUse` is the earliest general point where tool output and failure
  status can be inspected before a telemetry writer persists anything. It is the
  right hook for masking and result classification.
- `PreToolUse` can prevent execution. Treat a block as local enforcement, not as
  proof that the command would have required user approval.

## Rules And Approval Interplay

Codex rules live in `.rules` files under a `rules/` directory next to an active
config layer, for example `~/.codex/rules/default.rules` or project-local
`.codex/rules/*.rules` in a trusted project. Rules use Starlark
`prefix_rule()` entries over parsed command argv prefixes.

Rules decide whether a matching command outside the sandbox is:

- `allow`: run without prompting;
- `prompt`: ask before each invocation;
- `forbidden`: reject without prompting.

When multiple rules match, Codex applies the most restrictive decision:
`forbidden` wins over `prompt`, which wins over `allow`.

For shell wrappers such as `bash -lc`, Codex tries to split simple command
chains joined by `&&`, `||`, `;`, or `|` and evaluates each segment. If the
script contains advanced shell features such as redirection, environment
assignments, substitutions, wildcard expansion, or control flow, Codex treats
the whole shell invocation conservatively instead of splitting it.

Friction surfaces from rules this way:

- A `prompt` decision or sandbox escalation can produce a `PermissionRequest`
  hook event.
- A `forbidden` decision rejects the action without a user approval prompt. E2
  should capture this through `PreToolUse` only if a local hook makes the
  rejection, or through `PostToolUse` only if Codex reports a tool error for the
  rejected attempt.
- Rules do not replace telemetry. They reduce or forbid prompts; they are not an
  event store.
- `codex execpolicy check` is the deterministic way to test proposed rules
  before installing them.

## Masking-Before-Write Guard

E2 must treat every hook payload as raw sensitive input until it passes through
the writer. Hooks should never write directly to Postgres.

Recommended write path:

1. Hook adapter receives the raw Codex payload on stdin.
2. Adapter extracts only allowed event fields into a small internal event.
3. Adapter passes the event to a local writer module.
4. Writer validates the schema and rejects forbidden fields.
5. Writer masks every string field with `lib.creds.masking.OutputMasker`.
6. Writer applies exact-value masking for secrets registered by the secrets
   family before any pattern-only masking fallback.
7. Writer truncates oversized fields after masking.
8. Writer computes the event fingerprint after masking and normalization.
9. Writer writes to the shared ledger through secrets-resolved credentials.
10. If the ledger is unavailable, writer returns success to the hook and may
    append a minimal masked local queue item with mode `0600`.

Allowed event fields should stay aligned with the threat model:

- `harness`
- `repo`
- `branch`
- `issue`
- `event_type`
- `event_source`
- `severity`
- `summary`
- `fingerprint`
- `created_at`

Forbidden inputs include raw prompts, raw tool input, raw tool output, raw
environment variables, raw config files, raw session paths or contents, secret
names that identify production systems, and full stack traces that may include
headers, connection strings, or SDK payloads.

## Recommended Capture Architecture

Use hooks as the primary capture path, wrappers as a narrow supplement, and do
not use log tailing.

### Hook-Based Primary Path

Install a small set of Codex-native hooks:

- `PermissionRequest`: emit `approval_prompt` events. Capture tool name,
  normalized command prefix, permission class, repo, branch, and issue. Do not
  capture raw command strings beyond a masked, truncated summary.
- `PostToolUse`: emit `command_failure`, `tool_error`, and `secret_mask_hit`
  events. Use this hook to mask output before any ledger write or local queue
  write.
- `UserPromptSubmit`: scan for secret-shaped input and either block locally or
  emit only `secret_mask_hit` metadata. Never store the prompt text.
- `Stop` and `PreCompact`: flush any local queue opportunistically. Never block
  the turn on ledger availability.

Keep hook adapters thin. The durable logic belongs in a Python module that E2
can unit test without launching Codex.

### Wrapper Supplement

Wrappers are still useful for CxPP-owned commands that resolve secrets or call
external systems directly, such as secrets and Woodpecker workflows. Wrappers
should register exact secret values with the masking layer before invoking
subprocesses and then call the same writer interface as hooks.

Wrappers should not become the primary capture source for generic Codex
approval prompts. They cannot see actions initiated by arbitrary tools, MCP
servers, or generated commands outside the wrapper.

### Log Tailing Rejected

Do not tail Codex logs, session history, terminal scrollback, or transcript
files for primary friction capture.

Reasons:

- It is late: secrets may already be persisted before the tailer sees them.
- It is brittle across Codex versions and surfaces.
- It requires broad read access to state that the threat model treats as
  sensitive.
- It cannot reliably distinguish prompt shown, prompt approved, command blocked,
  command failed, and tool error without parsing display text.

## E2 Implementation Guidance

Build E2 around these components:

1. `lib/friction/` writer module with schema validation, masking, fingerprinting,
   fail-open ledger write, and optional local queue.
2. Codex hook adapters under a plugin or `cxpp:init` installed hook directory.
   Use current Codex matcher-group syntax.
3. Tests for malformed payloads, raw secret-shaped input, exact-value masking,
   oversized summaries, ledger outage, and `harness=codex`.
4. `codex execpolicy check` fixtures for recommended rules before they are
   written to `~/.codex/rules/default.rules`.
5. Migration cleanup for legacy `.codex/hooks.json` examples that still use
   Claude-shaped comments or outdated matcher objects.

Open uncertainty for E2 to verify with fixture hooks:

- The official manual documents event names, matcher behavior, hook loading, and
  trust flow, but it does not enumerate every JSON stdin field for every hook.
  E2 should keep payload parsing defensive and fixture-record only field names,
  not raw values.
- Current binary strings show internal names for hook input types and
  `PreToolUse` blocking messages, but the implementation should rely on the
  public manual where possible and treat binary-string observations as
  non-contractual.

## Conclusion

E1 remains necessary after Phase 0: the threat model says what must be safe, and
this spike says where Codex can observe the events. E2 should implement a
hook-first, mask-before-write writer with wrapper support for CxPP-owned secret
flows and no log tailing.
