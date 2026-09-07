---
wayfinder:
  kind: ticket
  version: 1
  id: define-session-identity
  title: Define native Codex session identity and claims
  type: discussion
  interaction: agent
  status: closed
  blocked_by:
    - ./01-choose-first-milestone.md
  claim:
    owner: null
    claimed_at: null
---

# Define native Codex session identity and claims

## Question

What stable identity, generation, ownership, and liveness evidence must bind a
native Codex worker to a role, issue, branch, worktree, and claim in the chosen
milestone?

## Context

CPP currently falls back through Claude-specific session evidence and transient
process ancestry. Native Codex needs a contract that survives transcript
compaction and distinguishes a replaced process generation. A shared GitHub
assignee, tmux pane name, transient shell PID, or message payload's claimed
sender cannot by itself prove session ownership. The answer should identify the
trusted evidence and the safe behavior when it is unavailable.

## Resolution

The user's milestone decision fixes the product boundary: native waves ship in
CxPP, while Kyle and Sage implementation remain excluded. The authorized wave
coordinator settled the engineering details below at the issue #197 plan gate;
they are not attributed to a separate human selection.

The native Codex thread UUID is the durable session identity. Wave and role are
logical placement, not alternative session identities, and a terminal or tmux
label is display-only. Every OS process that claims a thread/role pair receives
a new opaque owner-generation UUID. A resumed thread therefore keeps its thread
UUID but cannot inherit the previous process generation's write authority.

Same-host liveness may use the host boot identity, PID, and process start
evidence for the registered generation. Heartbeat or readiness timeouts alone do
not prove death. Unknown liveness fails closed; replacement requires verified
process-generation evidence or an explicit coordinator takeover that fences the
old generation.

Assignments and state-changing events bind the wave, role, thread, worker owner
generation, coordinator generation, assignment, policy revision, and the plan or
PR head being authorized. A payload's claimed sender is not transport evidence.
Capabilities are immutable declared snapshots of the native runtime and remain
separate from the Claude-led `codex:auto` driver classification.

Compaction reconstructs state without changing identity. Process or coordinator
restart creates a new fenced generation; legitimate committed decisions may be
replayed for recovery, but an old process cannot append fresh authoritative
events. Cancellation is assignment-terminal, duplicate events apply once, and
external side effects are reconciled against Git, GitHub, and worktree evidence
before retry.

The normative field, authority, state, recovery, and provenance rules are in
[`docs/native-codex-wave-contract.md`](../../../native-codex-wave-contract.md).
Ticket 03 and issue #198 own bounded transport proof; they may refine supported
delivery capabilities without redefining native identity.
