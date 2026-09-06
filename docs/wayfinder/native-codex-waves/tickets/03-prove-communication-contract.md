---
wayfinder:
  kind: ticket
  version: 1
  id: prove-communication-contract
  title: Prove the native Codex communication contract
  type: research
  interaction: agent
  status: open
  blocked_by:
    - ./02-define-session-identity.md
  claim:
    owner: null
    claimed_at: null
---

# Prove the native Codex communication contract

## Question

Which available transports can prove delivery, wake-up, acknowledgement, origin,
replay handling, and stale-listener behavior for the session identities selected
by the map?

## Context

The candidate transports are Codex team messaging inside one collaboration tree,
native cross-session delivery such as `codex queue`, and CPP's filesystem mailbox
as a same-host fallback. CLI help or queue acceptance alone is not proof of
delivery, wake-up, acknowledgement, or sender provenance. Keep queue acceptance,
message read, assignment accepted, and work completed as distinct observed
states. Do not contact live workers or launch research agents without current
authorization; define an isolated test plan when live testing is unavailable.

## Resolution

Pending research after the human selects the milestone and identity boundary.
