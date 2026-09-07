# Native cross-session transport proof (#198)

This is a bounded experiment and implementation handoff, not an installed wave
runtime. It consumes [contract v1.0](native-codex-wave-contract.md) from #197,
merged in `32129ac955a94238bb5b4bdcdf4a5bc30615aeac`; its SHA-256 is
`779c2aa4f1470ef66c5eb87b0b3bdb1e22386408a633bf5a31a99ff2c307ded5`.
Production durable events and delivery adapters remain #205/#206. Full
three-worker live acceptance remains #203.

## Experiment boundary

The coordinator approved five proof/evidence files and one exact `.gitignore`
exception for `cases.json`. The fixture never launches, resumes, or kills a
recipient. Individually launched disposable native Codex sessions participate
only in a fresh `cxpp-transport-proof-198-*` directory created mode 0700. Existing
wave workers, main, production gates, and the shared wave registry/mailbox are
not experimental inputs. Participant aliases must appear in the initial manifest.

The helper records the caller's Codex thread UUID and nearest Codex process
ancestor, including boot ID and process start time. The final helper refuses
namespace PID1 because it is not a stable host owner. These checks prevent an
accidental call from the wrong worker or stale generation. They do **not**
authenticate against another process controlled by the same OS user: the
thread environment and private files can be forged by that user. Queue text
is an event pointer, never an authority grant. Only a matching local manifest
record permits fixture actions; a `payload_only` event cannot grant authority.

## Reproduction

Run `make verify` first. Default tests use injected process identities and a
fake subprocess runner; they do not call Codex, contact a worker, or create live
sessions. Live execution requires a separately judged and scheduled experiment.

Set `PROBE` to the absolute path of
`tests/fixtures/native_wave_transport/probe.py` and `RUN` to a fresh private run
path. Below are example commands, not an unattended session launcher:

```bash
python3 "$PROBE" init "$RUN" coordinator worker-first worker-second
```

Individually start a disposable Codex terminal rooted at `$RUN`. Ask it to run
`python3 "$PROBE" register "$RUN" worker-first`, report ready, and end its
turn. The fixture reads its own thread/process identity. Do not reuse a live
worker's identity or resume an existing worker. After worker-first has registered,
the experiment coordinator registers itself; then launch worker-second, proving
the reverse contact order with another participant.

```bash
python3 "$PROBE" register "$RUN" coordinator
python3 "$PROBE" emit "$RUN" worker-first contact-first assignment
```

The returned event UUID is persisted before any wake. Use it with:

```bash
python3 "$PROBE" notify "$RUN" worker-first EVENT_UUID
```

`notify` runs installed `codex queue --thread <exact UUID> --message <pointer>`.
The recipient is instructed to run `read`, inspect the returned event, and then
explicitly run `ack` in its reasoning turn. The two commands are independent:
`recipient_read` is not acceptance, and queue success is neither one. A matching
assignment read moves the synthetic assignment from queued to read; its ACK
moves to accepted. Only a subsequent matching gate can increment the harmless
synthetic action counter. An early gate is rejected; replaying that rejected
ID returns its first disposition and does not gain later authority.

Emit `gate` instead of `assignment` to test action authorization. `--override`
accepts only the declared binding fields and provenance; use cases.json for
negative vectors. Re-notify the same event once to exercise duplicate delivery.
A second gate event after an action must not repeat that action. Reusing an
existing ID with different content returns `event_id_payload_conflict` without
replacing its original record.

For replacement, the coordinator explicitly runs `fence RUN ROLE`, holding old
assignments. Allow the disposable recipient to exit normally, then individually
launch a new recipient and register it under the same logical alias. Its new
thread/process/generation must reject old-generation controls. This proves safe
hold/fencing if observed; it does not claim resumed work or crash recovery.

## Bounds and observations

- Queue subprocess: 10 seconds maximum per call.
- ACK deadline: 120 seconds from the first notification attempt.
- Withheld wake observation: 30 seconds before an explicit notification.
- Retry: at most one, retaining the event ID with a new notification attempt.
- Live window: 15 minutes from run creation; no single blocking wait above 60s.
- No ACK means readiness unknown, never proof of death or permission to evict.
- `deadline RUN EVENT_UUID` records the result only after 120 seconds; late
  messages must still pass current generation/binding/state checks.

Record idle only after observing the recipient's prior turn finish. For busy
receipt, capture recipient `busy_start`/`busy_end` around a bounded harmless
operation and compare notification timing; a non-overlap is inconclusive.
Explicitly label manual initial instructions, queue notifications, and any
recovery wake. A hidden manual message cannot be evidence of automatic wake.

The private run holds exact identities; `export` publishes only allowlisted
logical aliases, event correlations, durations, dispositions and counter
observations. No prompts, arbitrary notes, environment, raw PID/boot/thread
identity or credentials are exported. Machine rows allowlist fields; separately reviewed operator observations are
marked attributed, and final reducer counters are marked fixture. A fixture decision invoked by a live recipient
is evidence of that fixture's behavior, not a native queue deduplication guarantee.

## Results and handoff

The scheduled run on 2026-09-07 completed at elapsed **895.365 seconds**.
[Sanitized JSONL](evidence/native-wave-transport/issue-198.jsonl) retains failed,
inconclusive and successful observations. Times below are seconds from the
original run start. Event labels are the final three digits of the full UUID;
join on `run_alias` and `event`, then order by `sequence` within a run.

| Case | Observed evidence | Conclusion and limit |
|---|---|---|
| Contact order | Primary coordinator registered 54.489, stable worker-second 191.246; event 004 read 310.877 / ACK 319.562. Control worker-first registered 542.602 before coordinator 581.836; event 030 read 604.393 / ACK 612.808. | Both registration orders delivered with correlated acceptance in the host-visible profile. The control reused worker-first's disposable process in a fresh namespace; it did not reset the original deadline. |
| Idle | Worker-second's registration turn had completed before 004; notification 295.756, read 310.877, ACK 319.562. | A new recipient reasoning turn followed the explicit queue pointer without polling or a manual recipient wake. Idle is an operator observation from terminal/task-complete records. |
| Busy | Event 006 notification followed busy-end: inconclusive. One repeat, 007: busy 473.694–503.733; notification 473.979; read 514.287; ACK 522.311. | Queue overlapped an active tool turn; recipient processed it after that turn, with ACK 48.332s after notification. No interrupt guarantee. |
| Replay/order | 003 assignment and 005 gate retries ACK idempotent; stable-first counter stayed 1. Early 021 gate rejected out_of_order before 020 acceptance; retry retained rejection; new 022 gate acted once. Conflicting content for ID 003 rejected. | Live recipients invoked the fixture reducer; native queue deduplication/ordering is not established. |
| Replacement | Worker-second generation 2 fenced 644.827 and exited; separately launched generation 3 registered 667.200 with the same sandbox settings. Old event 004 retry at 853.511 read 865.333 / ACK stale_generation 873.934. | Real process/thread replacement with explicit safe hold, old assignment counter 0. No resumed work or crash-recovery claim. |
| Timeout | 004 withheld 252.198–295.720 (43.522s), with no read until notification. Initial 001 had no ACK at deadline observation 185.219, 130.619s after first attempt. Initial 002 also remained unacknowledged. | Durable presence alone did not wake these recipients. Missing ACK means unknown readiness; the namespace failure explains this run, not a death detector. |
| Provenance | Events 010–018 rejected wave, assignment, revision, generation, coordinator, policy, plan, capability and payload-only controls. | No stale control authorized an action. Attribution relies on local identity/manifest and same-user trust, not native sender authentication. |

The runtime was Codex CLI **0.153.4**, `gpt-6-astra`, high effort, approval
`never`. Per-generation configuration is in `generation_capability` rows.
The first two recipients used `workspace-write`: their tool calls observed
namespace PID1 with changing process start times. Queue was accepted and
recipient reasoning resumed, but helper reads failed `participant_process_mismatch`
and no ACK was recorded. A disclosed diagnostic queue inspected that identity.
Those observations remain failures of this fixture's owner binding in that
profile. The replacements used `danger-full-access`, with stable host process
visibility. The final replacement compared two generations in that same profile;
changing sandbox alone is not counted as recovery evidence. All five disposable
terminals exited normally; no existing wave worker was resumed or killed.

Manual inputs were the individually authorized launch/registration instructions,
normal exits, one diagnostic queue, two disclosed busy preparation queues, and
the control-namespace registration queue. Event pointers themselves used native
queue only. For the nine negative controls, a bounded coordinator-side batch
persisted each event and notification attempt, sent one queue pointer containing
the nine IDs, and recorded its single queue result against each ID. The recipient
read all nine in one tool call, inspected them, then ACKed them in a separate
call. This batch is labeled `stale-controls`; it is not nine independent queue
latency measurements. These live negative gates followed the first synthetic
action; their rejection codes and absence of another action are observed.
Offline tests separately check every negative binding before any action.
No event exceeded two notification attempts. One malformed
operator CLI call omitted the recipient argument and failed before notifying;
the corrected call supplied it. No transport failure was hidden by that correction.

The observed live helper SHA-256 was
`d37c0c88cc72b85eb06143fd0e8a2f4f15c83f1227b58077d50228f8c8242c74`.
After the live window, offline-tested hardening rejects PID1 at identity capture,
checks the registration deadline, handles an unavailable queue executable, and
allowlists exported fields. These final changes were **not live rerun**. The
JSONL labels helper observations as observed, reducer summaries as fixture,
and human terminal/configuration interpretation as attributed; none is a signed
or adversarially authenticated transcript.

## Contract projection and completeness

This fixture projects the relevant bindings; it does not implement the full
contract envelope, immutable event log, production owner registry or compiler.
`wave`, `assignment`, `revision`, `generation`, `coordinator`, `policy`, `plan`,
and `capability` correspond respectively to `wave_id`, `assignment_id`,
`assignment_revision`, `owner_generation_id`, `coordinator_generation_id`,
`policy_revision`, `plan_digest`, and `capability_snapshot_id`. Synthetic
assignment names and plan/capability tokens are equality controls, not valid
production UUIDs/digest-addressed snapshots. Event UUIDs correlate reads/ACKs;
the full contract's independent correlation envelope is outside this fixture.

Delivered: all seven bounded cases have live observations above, plus offline
negative/identity tests and reproduction steps. In scope: coordinator review of
this exact proof and its limits. No acceptance is claimed for workspace-write
owner binding, arbitrary profiles, adversarial sender authentication, crash/resume
recovery, or native delivery guarantees beyond this run. If review requires those
for #198, keep the issue open; they are not silently reassigned. Production
implementation remains #205/#206 and the full three-worker wave remains #203.

The installed CLI observed during planning was 0.153.4. Its local `queue --help`
is command-availability evidence. The official CLI reference did not document
`codex queue` when inspected on 2026-09-07:
[OpenAI developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
There is no inferred wake, ordering, sender-attestation, or recovery guarantee.

#205 should consume generation and assignment bindings plus append-before-wake
and same-ID content conflict handling. #206 should consume measured queue
readiness and exact UUID targeting, preserve explicit ACK deadlines, and never
substitute a shell watcher exit for a recipient reasoning turn. This fixture
must not be installed as either production adapter. No mailbox fallback was
proved necessary for notification in the host-visible profile: the demonstrated
workspace-write gap was owner identity capture, which a mailbox alone cannot
repair. A future adapter must obtain a trustworthy stable owner observation or
hold that profile; it must not treat a private file read as a reasoning ACK.
