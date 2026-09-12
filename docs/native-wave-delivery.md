# Native delivery adapter (#206)

**Status: deterministic foundation; native dispatch and live acceptance unsupported
on the inspected Codex 0.154.0 interface. #206 remains open.** No live participants
were launched for this implementation. Passing fake-transport tests is not native
support evidence.

## Authority and receipts

`lib/native_wave/events.py` remains the authority for assignments, reads,
acceptance, holds, gates and completion. Delivery never appends an authoritative
event. Persist the event through `EventService` first, then issue its notification
permit through `DeliveryService.issue`. A crash between those operations leaves
an authoritative event discoverable through `pending`.

The separate owner-private SQLite journal contains only immutable permits,
bounded notification attempts, fetch tokens and recipient receipts. A permit binds
the authoritative store identity, wave, exact event ID and verified digest,
issuer/recipient role, thread and owner generation, current policy, assignment
revision and capability snapshot, plus a local runtime/socket binding. Current
assignment details are revalidated from the referenced event and its projection.
Rejected controls cannot receive permits. Assignment-bearing coordinator events
route to the assigned worker; worker events route to the coordinator. Registry-bound
worker prose routes to the coordinator as information only. Generic coordinator
prose has no inferred recipient and appears as `issuer_route_unresolved`.

| Observation | Meaning |
| --- | --- |
| `queued` | A correlated submission was observed in the native queue. |
| `started` | Exact client ID and pointer appeared in a user-message history item. |
| `unknown` | Delivery could not be established; absence never proves non-delivery. |
| Fetch output | The verified event and stable fetch token were returned, without receipt. |
| Explicit recipient receipt | A freshly validated recipient confirmed that fetch token. |
| Assignment accepted | A separate authoritative `EventService` transition; delivery cannot grant it. |

Recipient fetch and receipt each require fresh native process evidence. A lost
fetch response can be fetched again without changing its token or confirming a
receipt. Receipt retry is idempotent. Receipts from replaced generations remain
historical and never establish readiness for the new owner. Recipient receipt
also works for coordinator-directed results, independent of notifier health.
As with #200/#205, local owner-private files and process observation prevent
accidental identity mixing; they do not authenticate against the same OS account.

## Recovery and bounds

Each event/recipient generation has one deterministic permit ID. Reissuing a
permit preserves the original deadline and attempt budget. The notifier commits
`external_started` before queue/add. After an uncertain response or crash it only
reconciles; it never resets that bit or blindly adds another submission. A crash
just before the external call can consequently leave a notification unknown even
when no queue entry exists. Authoritative pending work remains recoverable.

Leases fence stale notifier observations and coalesce competing attempts. Lease
expiry cannot authorize another queue/add once external execution may have
started. Immediately before dispatch, both actual owner processes are observed
again alongside current authority and lease checks; unchanged registry rows do
not excuse changed or unavailable process evidence. Reconciliation observes up
to three queue pages and one history page;
offset shifts, consumed entries, missing client IDs, incomplete history and
not-found errors never become proof of absence. No `queue/start`, resume,
interrupt, archive/delete, configuration mutation or fleet enumeration fallback
exists. Queue acceptance never receipts on behalf of the agent.

Limits: 1–5 attempts (default 3), deadline within 900 seconds, 30-second leases,
persisted exponential backoff capped at 30 seconds; ten seconds and 1 MiB per
proxy connection, 128 interleaved notifications per response, 50 entries per
transport page. Pending pages contain at most 100 authoritative events, up to
two observations per event, and 64 KiB. Journal records have explicit size bounds.
No authoritative SQLite transaction spans journal IO, RPC, sleeps or retries.

`pending` is independent of the #205 read cursor and does not advance it. Begin
at sequence zero for a fresh reconciliation, page using the returned sequence,
then restart from zero on a subsequent reconciliation. This is a bounded scan,
not a high-water mark indicating that earlier work was accepted. It exposes both
the recipient's work and the issuer's outstanding deliveries, including events
whose permit creation was lost. Current queued/read assignments appear as
`assignment_unaccepted`; accepted/implementing/PR-open and held assignments appear
as `assignment_unfinished` with their authoritative state, revision and restriction.
They remain visible even after every notification has an explicit receipt.
Completed/cancelled assignments produce no unfinished-work row; outstanding
delivery observations retain their terminal restriction. Stale revisions cannot
become current work.

Pending reconciliation validates a stored permit before accepting its receipt.
For example, a same-generation policy rebrief can make a previous result receipt
historical: `permit_binding_stale` explicitly reports unconfirmed current receipt
to both issuer and recipient. The original permit, deadline, attempts and receipt
are preserved. Reissue cannot change that permit's bindings or reset its budget.
The issuer must resolve the changed authoritative context explicitly; pending
never turns this into an automatic fresh notification ID or transferred receipt.
A corrupt, missing, wrong-ID or replaced
journal fails closed even when the requested event page is empty. Opening never
creates a replacement. Explicit journal recovery is operator-owned; loss of
attempt history is never permission to retry existing events automatically.

## Native protocol boundary

The backend uses only an explicit absolute executable and local Unix socket via
`codex app-server proxy --sock`. It checks actual `SO_PEERCRED`, machine/boot ID,
server PID/start tick, socket device/inode and executable SHA-256. Socket names,
initialize user-agent strings and a thread's creation-time `cliVersion` do not
prove the current server identity. No default/global socket fallback is allowed.
JSON-RPC server requests are distinguished from responses and notifications;
approval requests are never automatically answered. IO and proxy-child cleanup
are bounded; recipient/server processes are never signaled.

Loaded idle/busy status is necessary but insufficient. Direct-input eligibility,
independent supported origin, durable history, current model/effort/root and
permissions must be established. Approval/user-input waiting, unknown status,
ephemeral/sub-agent origins and missing history are restricted. A last interrupted
turn stays interrupted even if `ThreadStatus` says idle. Unloaded sessions are
explicitly unsupported: resume can automatically run queued work before the
response exposes permission metadata.

The read-only protocol gap is material: generated 0.154.0 `ClientRequest` contains
`thread/settings/update`, but no `thread/settings/read`. `thread/read` lacks
approval/sandbox/current resolved-permission fields. `config/read` is cwd-scoped;
profile discovery returns identifiers, not a current thread's resolved permission
envelope. Cached settings notifications do not prove an initial snapshot,
gap-free replay or freshness. Resume/settings mutation cannot be used to obtain
pre-action evidence safely. These observations are consistent with the
[official App Server documentation](https://learn.chatgpt.com/docs/app-server),
checked September 12, 2026. The queue methods additionally rely on locally
generated experimental schemas and pinned 0.154.0 source, not a stable API promise.

Accordingly the production backend reports `permissions_unverified` before any
queue/add. Its injected permission-evidence port exists for deterministic tests
and a future separately reviewed native implementation. The CLI has no override,
assume-safe flag or permission broadening option. A positive fake oracle cannot
be presented as native evidence. An exclusively controlled fresh participant
would require an amended design proving unchanged current restrictions and
invalidation after disconnect/configuration drift; that design is not included.

## Explicit CLI and verification

The CLI operates on an existing #205 authority; it never bootstraps a wave or
installs a daemon. Create only a new journal in an existing private directory:

```bash
python3 scripts/native-wave-delivery.py --journal /private/run/delivery.sqlite3 journal-create
```

For every subsequent operation supply `--journal`, its returned `--journal-id`,
and absolute `--authority`. `--help` documents these operations:

* `permit --wave W --event UUID --role ROLE --runtime binding.json --deadline EPOCH`
* `fetch --permit UUID`, inspect the returned event, then
  `receipt --permit UUID --fetch-token TOKEN` in a separate agent action
* `pending --wave W --role ROLE [--after-sequence N --limit 100]`
* `status --permit UUID`
* `notify --permit UUID --codex /absolute/pinned/codex`
* `stop --permit UUID` (fresh coordinator only; stops notification, not wave authority)

`binding.json` is the serialized `RuntimeBinding` type. It must describe observed
host/socket/process/executable coordinates, not guessed values or a session name.
Detached `notify` and `status` never manufacture a native identity. Permit/fetch/
receipt/pending/stop derive the caller thread from its environment and validate
the actual native ancestor through #200.

Run the two delivery test modules through `make test`, then `make verify`.
Fixtures exercise real authoritative and journal databases with fake runtime
evidence and local fake proxy subprocesses; they never call a model. Coverage
includes append/permit/call/receipt crash windows, duplicate and concurrent
attempts, stale leases, real policy/owner replacements, holds/cancellation,
rejected controls, symmetric pending recovery and bounded malformed RPC handling.
Regressions also cover stale receipts after real policy rebrief, process changes
for either party during transport inspection, and all-receipted unfinished
assignments reconstructed from accepted through PR-open/held states.

`tests/fixtures/native_wave_delivery/live_check.py` is opt-in preflight tooling
for a separately approved disposable experiment. It launches no participants,
queues no inputs and never returns live acceptance success. Its private manifest
only declares an experiment allowlist; it does not prove native freshness or
permissions. No live evidence artifact is generated or claimed by this change.
Idle and active independent native receipt/acceptance remain unfulfilled #206
criteria. #201/#223 own contextual worker/action lifecycle, #202 owns installed
skill/package acceptance, and #203 owns the combined three-worker pilot.
