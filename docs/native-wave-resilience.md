# Native wave resilience delivery and evidence

Tracking: [#229](https://github.com/cooneycw/codex-power-pack/issues/229).
Research refresh: [#230](https://github.com/cooneycw/codex-power-pack/issues/230).
Baseline reviewed September 12, 2026: `8dce719`, including identity/claims
(#200) and durable events (PR #217, #205). This document records disposition and
acceptance refinements; it does not claim the integration stages are shipped.

## Delivery ownership

| Proposal | Disposition and owner | Required evidence |
| --- | --- | --- |
| Recipient-only receipt | Accept. CPP #867/#868 own shared supervisor changes; CxPP #206 owns native enforcement. | A live notifier and successful queue cannot receipt-confirm an agent that never acknowledges. |
| Lost scan response | Implement in this #229 slice at the #205 API boundary; #206 consumes it. | Repeat exact scan after discarded output, later scans, service restart, and projection rebuild; same page, no second transition. |
| Session lifecycle-aware wake | Accept for #206. | Distinguish loaded idle, busy, unloaded, interrupted, approval-waiting, held, stopped, and cancelled targets; record actual input start and recipient acknowledgement separately. |
| Worker reconstruction | Accept for #201 with #223. | Reconstruct assignment revision, policy, generation, approved plan, and completed external actions after compaction/resume and before consequential actions. |
| Coordinator listening | Accept for #206 and #201. | Track unanswered gate requests and unacknowledged results independently of watcher health; recover a silent coordinator through fenced ownership. |
| Runtime-bound authority | Accept for #206 using #200/#205. | Bind routing and capabilities to thread UUID, host/server, current generation, and actual profile; give detached notifiers narrowly scoped authority. |
| Installed dependency chain | Accept for #202. | Fresh isolated install resolves all transitive helpers from its package and reports exact source, plugin, helper, CLI, and profile evidence. |
| Complete fault pilot | Accept for #203 after #202. | One coordinator and three independent workers exercise failures in both directions, with event lineage and remaining limits recorded. |

CPP issues: [#867](https://github.com/cooneycw/claude-power-pack/issues/867),
[#868](https://github.com/cooneycw/claude-power-pack/issues/868).
CxPP delivery issues: [#205](https://github.com/cooneycw/codex-power-pack/issues/205),
[#206](https://github.com/cooneycw/codex-power-pack/issues/206),
[#201](https://github.com/cooneycw/codex-power-pack/issues/201),
[#223](https://github.com/cooneycw/codex-power-pack/issues/223),
[#202](https://github.com/cooneycw/codex-power-pack/issues/202), and
[#203](https://github.com/cooneycw/codex-power-pack/issues/203).
These retain implementation ownership; #229 stays open until its combined
acceptance evidence exists. #230 remains evergreen afterward.

## Lost scan responses

`EventService.scan_and_advance` commits cursor progress before returning its
page. Retrying the exact command/event ID must return the original receipt,
events, scan endpoint, and historical cursor, including after service restart or
later scans. Recovery never rewinds the live cursor, appends a second scan, or
manufactures `assignment.read` or `assignment.accepted`.

New scan events record `scan_after_sequence` in their hashed validation facts.
Replay checks the start against the preceding cursor for the exact reader
identity and generation, and derives the expected resulting cursor from the
committed scan range. Older journals without this field recover their start
from preceding events; no journal rewrite is required.

Historical retrieval uses the existing registered-participant read boundary.
It grants no current-generation write authority: a resumed process may retrieve
history, but must register its new generation before issuing a fresh scan or
acting. Conflicting event-ID payloads and rejected scans return no event page.
A historical page cursor is a response snapshot, not a replacement for current
state. If the caller also lost the scan command identity, the adapter must
reconcile outstanding assignments independently of cursor progress (#206).

Recovery currently verifies the full wave journal and replays the prefix before
the scan. Returned pages remain bounded to 10,000 events; recovery work grows
with journal size. This is a recovery path, not a listener polling primitive.
The delivery matrix above records remaining integration and pilot requirements.

## Decisions and rejected alternatives

- Persist each authoritative event before notification. Retry its pointer with
  bounded backoff and coalesce wakes; reject recreating assignments on timeout
  because event durability and notification success are separate.
- Keep transport acceptance, agent receipt, assignment acceptance, progress,
  result submission, and verified completion distinct. A notifier's surfaced
  watermark cannot acknowledge on behalf of its recipient. Reject supervisor
  auto-consumption and socket-file-based readiness as evidence of agent receipt.
- Use repeatable scan retrieval at the existing API boundary. A separate
  fetch/ack API remains a possible future design, but is unnecessary for this
  fix and would require adapter migration. Assignment reconciliation is still
  required when command identity is lost; do not treat an empty scan as proof
  that no work remains.
- New scans persist an explicit start; old scans derive it from verified
  history. Reject resetting the live cursor to resend a page: a later scan may
  already have advanced it. The response carries its historical cursor.
- Keep historical reads available to registered wave participants, including a
  resumed thread. Reject equating historical read access with current-generation
  permission to write, accept work, approve gates, or merge.
- Model queue storage and wake separately. OpenAI's [maintainer response on
  #44491](https://github.com/openai/codex/issues/44491#issuecomment-5644292953)
  says queue intentionally persists without resuming an unloaded session.
  Resume only eligible targets and observe the already-persisted input starting;
  reject blindly adding a second instruction when wake status is unknown.
- Preserve held, stopped, cancelled, and approval-blocked states. Fallback
  transport must not evade policy denial. Silence means readiness unknown,
  not permission to evict a potentially live owner.
- Workers may suppress an unsafe next action locally; authoritative hold and
  release remain coordinator decisions. Reconcile worktree, branch, PR, exact
  head, checks, and merge evidence before repeating an external action.
- A detached notifier must not impersonate the coordinator's Codex process.
  Choose and prove a limited authority mechanism in #206. Do not broaden sandbox
  permissions to make the existing host-visible proof pass under another profile.
- Keep shared skill changes upstream in CPP and consume reviewed snapshots.
  Reject hand-editing generated skill copies or relying on a global helper that
  happens to work in the developer's checkout.

## Required failure scenarios

Deterministic adapter fixtures precede live tests. Record expected transitions,
observed transitions, event IDs, recipient identity/generation, and external
side effects for every scenario. A fixture is not evidence of native delivery.

| Scenario | Required result | Owner |
| --- | --- | --- |
| Response discarded after scan commit | Exact retry returns original page after restart/later scans, with no cursor regression or receipt/acceptance transition. | #205 / this slice |
| Old journal without scan start metadata | Recover from preceding reader history and validate the resulting cursor. | #205 / this slice |
| Conflicting retry, stale process, or unrelated thread | No payload for rejected/conflicting scans; fresh writes remain fenced; historical reads retain existing participant policy. | #205 / this slice |
| Incorrect scan metadata or corrupted journal | Recovery/rebuild fails closed before writing reconstructed state. | #205 / this slice |
| Dropped/duplicated worker notification | Original event remains outstanding; retries cannot duplicate assignment or gate. | #206 |
| Idle versus busy target | Record acceptance, actual delivery/start, and agent acknowledgement separately; bounded timeout reports unknown readiness. | #206 |
| Unloaded or interrupted target | Resume only eligible sessions; detect persisted input starting without submitting duplicate work. | #206 |
| Held, stopped, cancelled, or approval-waiting target | Preserve restriction; no automatic resume or fallback that bypasses it. | #206 / #201 |
| Worker replacement or compaction | Reconstruct current bindings and policy; suppress stale actions until coordinator reconciliation/rebinding. | #201 / #223 |
| Coordinator watcher alive but replies absent | Gate requests/results remain visibly unacknowledged; successor must acquire a new fenced generation. | #206 / #201 |
| PR creation or merge succeeds, callback disappears | Reconcile actual remote state and exact authorized head before any retry. | #201 |
| Helper/plugin/profile changes | Invalidate unproved readiness and exercise the fresh installed dependency chain. | #202 |
| Combined bidirectional failures | Complete bounded three-worker wave and account for delivered work and residuals. | #203 |

## Evidence boundaries and refresh

The initial implementation provides deterministic scan recovery evidence only.
It does not establish native listener behavior or full worker recovery. The
[transport proof](native-wave-transport-proof.md) is tied to CLI 0.153.4 and its
recorded profiles; it does not establish unloaded-thread recovery. Existing
fleets and production runtimes are outside the disposable acceptance scope.

Scan retries verify the full journal and replay its prefix, so recovery CPU and
memory scale with history even though the returned page is bounded. Future
optimization must preserve old-journal compatibility, validation, and identical
historical responses. Adapters should persist command identity across transport
retries and independently reconcile pending assignments after losing that identity.

Use #230 for monthly and release/incident-triggered research. Capture CLI/build,
app/server, sandbox/approval profile, plugin/helper sources, tool schemas and
observed capability changes. Recheck official documentation and source, submitted
Codex issues and maintainer dispositions, and community reports including Reddit.
Treat community reports as hypotheses until reproduced in the intended profile.
Map every material change to a delivery owner and rerun affected disposable
scenarios before advertising readiness. No scheduled automation is installed by
this change.
