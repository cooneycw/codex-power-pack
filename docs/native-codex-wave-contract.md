# Native Codex Wave Session, Assignment, and Gate Contract

- Status: Accepted for implementation
- Contract version: `1.0`
- Decision issue: [#197](https://github.com/cooneycw/codex-power-pack/issues/197)
- Parent wave: [#191](https://github.com/cooneycw/codex-power-pack/issues/191)
- Scenario corpus: [`tests/fixtures/native-codex-wave-contract-scenarios.json`](../tests/fixtures/native-codex-wave-contract-scenarios.json)

## Purpose

An independently launched Codex session must not gain authority from a mutable
terminal label, a shared GitHub author, a stale process, or prose that claims its
own sender. This contract defines the durable identities and append-only events
that let a coordinator assign work, judge a plan, recover after interruption,
and complete an exact reviewed change without repeating implementation or merge.

The contract separates four questions that are easy to blur:

1. Which Codex conversation is this?
2. Which current OS process owns that conversation's wave role?
3. Which exact assignment and policy revision may it act on?
4. Which durable evidence authorizes the next state transition?

## Decision provenance

The user selected CxPP-native wave delivery and later clarified that Kyle work
was feasibility-only. Kyle and Sage code, configuration, processes, issues, PRs,
merges, and deployment remain outside this contract's implementation scope.
Those human decisions are preserved in the Wayfinder
[`01-choose-first-milestone.md`](wayfinder/native-codex-waves/tickets/01-choose-first-milestone.md)
ticket.

The issue #197 implementation gate authorized the engineering rules in this
document: coordinator-only durable gate/hold/release/completion authority,
generation fencing, fail-closed local action suppression, evidence-based owner
replacement, and reconciliation before retrying external effects. These are
coordinator decisions under delegated CxPP delivery authority, not additional
human product selections.

The [official OpenAI developer-command reference](https://developers.openai.com/codex/cli/reference#codex-resume)
documents resuming a Codex session by UUID and permits model or sandbox
overrides on resume. The tested Codex CLI 0.153.4 also exposes
`codex queue --thread <UUID>`, but that command is not present in the official
command reference reviewed for this decision.
Consequently, resume-by-UUID informs native identity while queue delivery is a
detected runtime capability. A successful queue call proves enqueue acceptance
only.

## Non-goals and ownership boundaries

This issue defines a contract and deterministic scenario corpus. It does not:

- implement the role registry or worktree ownership adapter owned by #200;
- implement the wave planner, gate lifecycle, or exact-head CI adapter owned by
  #201;
- implement the durable event store owned by #205;
- select or implement delivery and wake adapters owned by #198 and #206;
- change the `project-next` 1.3 classification/ranking contract;
- compile Spec Kit artifacts or introduce an issue compiler beside `spec-sync`;
- claim the complete three-worker live acceptance owned by #203; or
- change Makefiles, CI, generated inventories, plugins, global state, Kyle, or
  Sage.

## Identity model

| Field | Meaning | Lifetime and authority |
|---|---|---|
| `wave_id` | Stable namespace for one orchestration run | Created by the coordinator; never inferred from a terminal label |
| `role_id` | Logical role inside a wave, such as `coordinator` or `worker-B` | May move only through an atomic owner replacement |
| `thread_id` | Native Codex session UUID | Durable across transcript compaction and `codex resume`; a session name is display metadata |
| `owner_generation_id` | Opaque UUID minted for one OS-process claim on a worker thread/role | Changes whenever another process resumes, replaces, or takes over the role |
| `coordinator_generation_id` | Opaque UUID for the current coordinator process claim | Fences every authoritative coordinator event and changes on coordinator replacement |
| `capability_snapshot_id` | Digest-addressed immutable declaration of a native runtime configuration | An owner record points atomically to its current snapshot; changing that pointer does not itself change OS-process generation |
| `assignment_id` | UUID for one logical attempt to deliver a work item | Stable through ordinary recovery; cancellation is terminal and later work uses a new ID |
| `assignment_revision` | Monotonic revision of assignment bindings | Increments when the worker generation, file lane, policy, or requirements change |
| `event_id` | UUID for one durable event | Globally unique within the wave and applied at most once |
| `correlation_id` | ID joining a request with its acknowledgement or verdict | Never substitutes for `event_id` or assignment binding |

`thread_id` answers which Codex conversation owns continuity. It does not prove
that the process currently sending bytes owns a wave role. That proof belongs to
the current `owner_generation_id` and its registered process evidence.

The worker and coordinator generations are symmetric fences. A new coordinator
may reconstruct legitimate decisions already committed by an old generation,
but the old process loses authority to append approvals, holds, releases,
completion, cancellation, or takeovers as soon as the successor generation is
atomically installed.

## Process evidence, liveness, and readiness

A same-host owner claim records:

- a stable host-instance identifier and OS boot identifier;
- PID and process start time (or an equivalent non-reusable process handle);
- `thread_id`, role, generation, registration time, and last verified evidence;
- branch, worktree, issue, and exact file lane when assigned; and
- the immutable capability snapshot.

Liveness has exactly three results: `alive`, `dead`, or `unknown`. PID existence
without matching boot/start evidence is not enough because PIDs are reused.
Replacement is automatic only after evidence proves the registered generation
dead. When evidence is missing or contradictory, liveness is `unknown` and
ownership changes fail closed.

Heartbeat, mailbox cursor progress, queue availability, and listener/watch
status measure readiness, not OS-process liveness. A timeout may mark a worker
`not_ready` or `readiness_unknown`; it never proves death and never authorizes
eviction. An explicit coordinator takeover may replace an unknown or live owner
only by atomically installing a new generation and fencing the old generation
before the successor can write.

The coordinator role follows the same rule. Coordinator recovery must acquire a
new generation through compare-and-swap against durable ownership. A stale
coordinator process can read history but cannot append new authoritative events.

## Capability declarations

Capabilities describe the native session that will execute the assignment, not
the Claude-led `codex:auto` driver classification. A snapshot records at least:

- Codex CLI/runtime version and native model identifier;
- reasoning effort, sandbox, approval policy, workspace roots, and added writable
  directories;
- enabled tool families, web mode, apps/plugins required for the assignment;
- supported delivery/wake mechanisms and their measured evidence level; and
- capture time plus a digest of the normalized declaration.

Snapshot contents never mutate. The owner record holds a
`current_capability_snapshot_id` pointer that is atomically replaced after a
same-process configuration change. Replacing that pointer does not mint a new
owner generation: generation represents OS-process ownership, while the
snapshot represents effective runtime configuration.

The wave planner compares assignment requirements with the current snapshot
before queueing work. The separate `flow_driver` field may say `flow:auto`,
`codex:auto`, or another lifecycle driver, but it cannot add or remove native
runtime capability. When a capability change affects assigned requirements, the
coordinator appends a new assignment revision bound to the new snapshot and the
worker must rebrief and acknowledge it before acting. An irrelevant capability
change may update the owner pointer without revising unrelated assignments.

Queue support is capability-checked. Even when available, queue acceptance does
not establish read, acknowledgement, sender identity, or completion.

## Assignment record

The coordinator durably appends an assignment before attempting a wake. The
record contains:

- `wave_id`, `assignment_id`, `assignment_revision`, issue/task identity, and
  dependency snapshot;
- assigned `role_id`, `thread_id`, `owner_generation_id`, and required
  `capability_snapshot_id`;
- authoring `coordinator_generation_id` and `policy_revision`;
- branch, worktree, exact file lane, acceptance conditions, and exclusions;
- gate requirements and the digest algorithm used for the proposed plan;
- creation/deadline timestamps and the originating event ID; and
- cancellation or supersession linkage when applicable.

Changing the bound worker generation, lane, capability requirements, or policy
does not mutate prior history. The coordinator appends a new assignment revision
and requires the worker to acknowledge it. A cancelled assignment is never
revised back into service; a fresh attempt receives a fresh `assignment_id`.

## Event envelope and provenance

Every event has a base envelope containing:

- `event_id`, event kind, durable sequence, and timestamp;
- `wave_id`, actor role plus actor worker/coordinator generation, payload digest,
  and provenance evidence; and
- causation/correlation event IDs when the event responds to another event.

Assignment-bearing events additionally contain:

- assignment ID, assignment revision, and policy revision;
- addressed role/thread/generation where applicable;
- `plan_digest`, PR base/head, or external evidence IDs required by the event;
- the bound capability snapshot where requirements depend on it; and
- provenance classification and evidence sufficient for that transition.

Pre-assignment wave/role registration events omit assignment fields (or encode
them as explicit `null` in a fixed-width serialization) and instead carry the
role, thread, capability snapshot, and claimed owner generation. Coordinator
takeover events likewise omit assignment fields and carry the old and new
coordinator generations plus fencing evidence. Consumers must select the schema
by event kind; `null` assignment data never grants assignment authority.

The durable store validates authority and current generations atomically with
append. Sequence order is assigned by the store, not trusted from a sender. A
same-ID retry whose canonical payload digest matches returns the original
disposition and adds no second transition. Reusing an `event_id` with different
canonical content or digest is rejected and surfaced as
`event_id_payload_conflict`; it is never treated as a successful duplicate.

Provenance classifications are:

| Class | Meaning | State-changing authority |
|---|---|---|
| `transport_observed` | A transport supplied and verified an actor identity | Only after that identity maps to the current registered generation |
| `registry_bound_local` | A trusted local adapter verified the current process generation and appended on its behalf | Allowed for the transition authorities below |
| `payload_only` | The body or `from` field merely claims an actor | Never allowed to change authoritative state |

Native queue delivery targets a thread but does not, by command success alone,
attest the sender. The host-local mailbox is inspectable but same-user file
access is not cryptographic authentication. Both may carry a pointer to a
durable event; the event store and current registry binding establish authority.

## Assignment states and transition authority

The canonical states are `queued`, `read`, `accepted`, `implementing`,
`pr_open`, `held`, `completed`, and `cancelled`. `read` and `accepted` remain
separate even when one interaction produces acknowledgements close together.

| Resulting state | Required prior state | Authority and evidence |
|---|---|---|
| `queued` | none | Current coordinator generation appends the complete assignment before notification |
| `read` | `queued` | Bound worker generation acknowledges the exact durable event/cursor; no work acceptance is implied |
| `accepted` | `read` | Bound worker generation explicitly accepts the exact assignment revision, policy, lane, and capability requirements |
| `implementing` | `accepted` | Bound worker generation cites a current coordinator gate matching assignment revision, worker/coordinator generations, policy revision, and plan digest |
| `pr_open` | `implementing` | Bound worker generation records PR URL, base branch/SHA, and exact head SHA |
| `held` | any nonterminal state | Current coordinator generation records reason, prior state, and release conditions |
| `completed` | `pr_open` or approved non-code terminal path | Current coordinator generation records reconciled exact-head merge or accepted non-code evidence |
| `cancelled` | any nonterminal state | Current coordinator generation records cancellation; future work needs a new assignment ID |

A coordinator release from `held` names the prior state and revalidates worker
generation, policy, plan gate, PR head, dependencies, and capability snapshot.
It cannot restore a stale condition merely because `resume_state` was recorded.

### Local action suppression is not a durable hold

A worker must refuse action locally when a gate is stale or mismatched,
ownership is unknown, a prerequisite failed, or the coordinator required for a
new decision is unavailable. Refusal does not wait for coordinator availability.
The worker may append a non-authoritative `worker.action_suppressed` observation
or report it later, while the durable assignment remains in its last validated
state.

Only the coordinator can convert that condition into authoritative `held` and
later release it. This separation ensures a worker can always stop safely while
preventing it from granting its own release.

## Gate binding

A plan gate records `gate_id`, `assignment_id`, `assignment_revision`, worker and
coordinator generations, `policy_revision`, normalized `plan_digest`, verdict,
conditions, and authoring event ID. Every field must match the current durable
assignment at the moment `implementing` is appended.

An approval for an old assignment, old revision, old worker generation, stale
coordinator generation, superseded policy, or different plan is retained for
audit and rejected for authorization. A plan edit changes the digest and needs a
new coordinator verdict. No invocation flag, issue trailer, or conversational
memory bypasses this binding.

PR review and merge clearance use the same shape with exact base and head SHAs.
Any head change invalidates prior review and CI evidence and requires an
authoritative hold or renewed clearance before completion.

## Acknowledgements and delivery

Notification and state are separate:

1. Append the authoritative event.
2. Attempt one or more detected wake mechanisms with the event pointer.
3. Record transport acceptance as an observation.
4. Let the addressed generation append a correlated read acknowledgement.
5. Require a distinct acceptance or verdict event before changing work state.

An unobserved wake is recoverable because the event already exists. A read
cursor records the highest contiguous sequence plus explicit gaps; advancing it
cannot manufacture acceptance. Timeouts leave the event queued and readiness
unknown. Recovery re-notifies the current generation but does not recreate the
assignment event.

## Restart, compaction, takeover, and cancellation

- Transcript compaction keeps thread and process-generation identity. The
  worker reconstructs current assignment, policy, gate, and acknowledgements
  from durable events before acting.
- A resumed thread in a new OS process keeps `thread_id` and registers a new
  owner generation. It cannot use old-generation write authority. The
  coordinator may rebind the assignment through a new revision after inspecting
  branch/worktree effects and may explicitly carry forward a still-valid plan
  decision through a new current-generation event.
- Coordinator restart uses a new fenced coordinator generation. Already
  committed verdicts remain evidence; recovery replay does not let the old
  process append anything new.
- Verified-dead replacement or explicit takeover fences the old generation
  before the new one accepts work. Unknown liveness never becomes implicit
  permission to evict.
- Cancellation is assignment-terminal. Delayed reads, acceptances, gates, or
  completions for that ID are rejected. Continuing the same issue requires a
  new assignment ID linked to the cancelled one.

## Replay and external side effects

Event-ID deduplication provides apply-once durable transitions. It cannot make
Git edits, pushes, PR creation, or remote merge exactly once across a crash.
Before retrying any external action, recovery reconciles observed state:

- branch and worktree existence, claim owner, dirtiness, and commit graph;
- remote branch and PR identity, base, exact head, review, and checks;
- GitHub merge state and merge commit SHA; and
- the last durable event describing the intended action.

If a merge succeeded remotely before `assignment.completed` was recorded,
recovery verifies that the merged PR carried the authorized exact head and then
appends completion; it never invokes merge again. If implementation stopped with
an existing branch/worktree, a new owner remains locally suppressed until the
coordinator inspects those effects and appends a rebound assignment revision or
an authoritative hold. Unknown or conflicting evidence fails closed.

## Acceptance evidence

The scenario corpus is deterministic contract evidence. Its negative cases pin
generation, provenance, policy, cancellation, ordering, and crash boundaries,
but it does not claim a runtime adapter exists.

Issue #198 must provide bounded delivery/read/ack observations and issue #206
must implement the selected wake path. Issue #203 owns a completed live run with
one coordinator and three independent workers. Three workers being registered,
or this contract containing a three-worker fixture, is not that proof; the
fixture is explicitly marked `future_required_unproved` until #203 records the
observable run.

## Downstream handoff

- #200 consumes identities, capability snapshots, owner generations, liveness,
  and atomic fencing.
- #205 consumes event envelopes, acknowledgements, deduplication, durable
  reconstruction, and external-effect reconciliation boundaries.
- #198/#206 determine and implement measured transports without weakening
  provenance.
- #199 maps `spec-sync` identities and dependencies into assignment inputs while
  preserving the `project-next` 1.3 contract and sole compiler boundary.
- #201 consumes the resulting APIs for judged plans, holds, exact-head CI, and
  coordinator-only completion.
