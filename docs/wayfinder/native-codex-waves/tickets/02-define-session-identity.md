---
wayfinder:
  kind: ticket
  version: 1
  id: define-session-identity
  title: Define native Codex session identity and claims
  type: discussion
  interaction: human
  status: open
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

Pending human decision.
