"""Real #205 authority/journal crash windows; no live models or copied native identity."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from lib.native_wave.delivery import DeliveryService
from lib.native_wave.delivery_store import DeliveryStore
from lib.native_wave.delivery_types import DeliveryError, QueueEvidence, RuntimeBinding, RuntimeObservation
from lib.native_wave.event_types import EventDisposition, EventKind, PolicyRevisionChange, canonical_record
from lib.native_wave.events import EventService
from lib.native_wave.types import (
    ExpectedOwnerBindings,
    LocalIdentityContext,
    ObservationFailure,
    OwnerGenerationId,
    ProcessObservationUnavailable,
    RebriefOwner,
    ReplaceDeadOwner,
)
from tests.test_native_wave_events_replay import (
    COORDINATOR,
    COORDINATOR_GENERATION,
    COORDINATOR_PROCESS,
    COORDINATOR_THREAD,
    WAVE,
    WORKER,
    WORKER_GENERATION,
    WORKER_PROCESS,
    WORKER_THREAD,
    FakeClock,
    FakeIds,
    FakeProbe,
    actor,
    assignment_binding,
    bootstrap_and_register,
    command,
    create_store,
    snapshot,
)

COORD = LocalIdentityContext(COORDINATOR_THREAD)
RECIPIENT = LocalIdentityContext(WORKER_THREAD)


class Transport:
    def __init__(self, state: str = "idle") -> None:
        self.state = state
        self.added: list[str] = []
        self.lose_reply = False
        self.consume = False
        self.after_add = lambda: None

    def inspect(self, *args: object) -> RuntimeObservation:
        return RuntimeObservation(self.state)

    def enqueue(self, runtime: RuntimeBinding, thread: str, pointer: str, command_id: str, *, before_send) -> str:
        before_send()
        self.added.append(command_id)
        self.after_add()
        if self.lose_reply:
            raise DeliveryError("external_commit_reply_lost")
        return "queue-item-1"

    def reconcile(self, *args: object) -> QueueEvidence:
        return QueueEvidence("unknown" if self.consume else "queued", None if self.consume else "queue-item-1")


@pytest.fixture
def setup(tmp_path: Path):
    authority = create_store(tmp_path)
    probe = FakeProbe()
    events = EventService(authority, process_probe=probe, ids=FakeIds(), clock=FakeClock())
    capability = snapshot("worker")
    bootstrap_and_register(events, snapshot("coordinator"), capability)
    binding = assignment_binding(capability)
    assignment = command(4, EventKind.ASSIGNMENT_QUEUED,
                         actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION), assignment=binding)
    assert events.append(assignment, COORD).disposition == EventDisposition.APPLIED
    journal = DeliveryStore.create(tmp_path / "delivery.sqlite3")
    now = [1000]
    service = DeliveryService(authority, journal, probe, now=lambda: now[0])
    runtime = RuntimeBinding(str(tmp_path / "server.sock"), "test-host", str(UUID(int=3)), 9000, 10,
                             1, 2, "a" * 64, "1.0")
    return service, events, assignment, runtime, now


def issue(setup):
    service, _, assignment, runtime, _ = setup
    return service.issue(str(WAVE), str(assignment.event_id), str(COORDINATOR), COORD, runtime, deadline=1120)


@pytest.mark.parametrize("state", ["idle", "busy"])
def test_queue_fetch_receipt_never_accept_assignment(setup, state):
    service, _, assignment, _, _ = setup
    permit = issue(setup)
    result = service.notify(permit.permit_id, Transport(state))
    assert result["phase"] == "queued" and not result["receipt_confirmed"]
    fetched = service.fetch(permit.permit_id, RECIPIENT)
    assert fetched["event"] == assignment.canonical_bytes().decode()
    assert not service.status(permit.permit_id)["receipt_confirmed"]
    receipt = service.receipt(permit.permit_id, fetched["fetch_token"], RECIPIENT)
    assert service.receipt(permit.permit_id, fetched["fetch_token"], RECIPIENT) == receipt
    assert service.status(permit.permit_id)["receipt_confirmed"]
    with service.authority.transaction() as tx:
        assert not tx.read_assignment(assignment.assignment.ref).acknowledged
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) is None
    pending = service.pending(str(WAVE), str(WORKER), RECIPIENT)
    assert any(row["state"] == "assignment_unaccepted" for row in pending["events"])


def test_event_without_permit_survives_append_crash_and_lost_scan_id(setup):
    service, _, assignment, _, _ = setup
    first = service.pending(str(WAVE), str(WORKER), RECIPIENT)
    assert first["events"][0] == {"event_id": str(assignment.event_id), "state": "event_without_permit",
                                  "restriction": None}
    assert first["events"][1]["state"] == "assignment_unaccepted"
    assert first["cursor_advanced"] is False
    assert service.pending(str(WAVE), str(WORKER), RECIPIENT) == first
    issue(setup)
    assert service.pending(str(WAVE), str(WORKER), RECIPIENT)["events"][0]["state"] == "receipt_outstanding"


def test_concurrent_reissue_preserves_first_budget_and_receipts(setup):
    service, _, assignment, runtime, _ = setup
    permit = issue(setup)
    def reissue(_):
        return service.issue(str(WAVE), str(assignment.event_id), str(COORDINATOR), COORD, runtime,
                             deadline=1500, max_attempts=5)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(value == permit for value in pool.map(reissue, range(8)))
    token = service.fetch(permit.permit_id, RECIPIENT)["fetch_token"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: service.receipt(permit.permit_id, token, RECIPIENT), range(8)))
    assert all(value == receipts[0] for value in receipts)


@pytest.mark.parametrize("consume", [False, True])
def test_external_commit_lost_reply_never_reenqueues_after_restart(setup, consume):
    service, _, _, _, now = setup
    permit = issue(setup)
    transport = Transport()
    transport.lose_reply, transport.consume = True, consume
    assert service.notify(permit.permit_id, transport)["phase"] == "unknown"
    service.journal = DeliveryStore.open(service.journal.path, service.journal.store_id)
    now[0] += 3
    assert not service.notify(permit.permit_id, transport)["receipt_confirmed"]
    assert transport.added == [permit.permit_id]
    assert service.journal.read(permit.permit_id)[1]["attempts"] == 2


def test_crash_before_external_call_preserves_conservative_unknown(setup):
    service, _, _, _, now = setup
    permit = issue(setup)
    lease = service.journal.acquire(permit.permit_id, now[0])
    service.journal.record(lease, now[0], phase="enqueue_started")
    now[0] += 31
    transport = Transport()
    service.notify(permit.permit_id, transport)
    assert transport.added == []  # No negative evidence permits a blind retry.


def test_crash_after_permit_before_call_can_dispatch_once(setup):
    service, _, _, _, now = setup
    permit = issue(setup)
    service.journal.acquire(permit.permit_id, now[0])
    now[0] += 31
    transport = Transport()
    service.notify(permit.permit_id, transport)
    assert transport.added == [permit.permit_id]


def test_stale_lease_cannot_overwrite_new_attempt_or_enqueue_again(setup):
    service, _, _, _, now = setup
    permit = issue(setup)
    transport = Transport()
    def steal():
        now[0] += 31
        service.journal.acquire(permit.permit_id, now[0])
    transport.after_add = steal
    result = service.notify(permit.permit_id, transport)
    assert result["attempt_error"] == "stale_notifier_lease"
    assert service.journal.read(permit.permit_id)[1]["external_started"]
    now[0] += 31
    service.notify(permit.permit_id, transport)
    assert len(transport.added) == 1


def test_fetch_output_loss_does_not_create_receipt(setup):
    service, _, _, _, _ = setup
    permit = issue(setup)
    lost = service.fetch(permit.permit_id, RECIPIENT)
    recovered = service.fetch(permit.permit_id, RECIPIENT)
    assert lost == recovered
    assert service.status(permit.permit_id)["receipt_confirmed"] is False
    with pytest.raises(DeliveryError, match="fetch_token"):
        service.receipt(permit.permit_id, str(UUID(int=900)), RECIPIENT)


@pytest.mark.parametrize("operation", ["fetch", "receipt"])
def test_issuer_cannot_impersonate_recipient(setup, operation):
    service, _, _, _, _ = setup
    permit = issue(setup)
    token = service.fetch(permit.permit_id, RECIPIENT)["fetch_token"]
    with pytest.raises(DeliveryError):
        if operation == "fetch":
            service.fetch(permit.permit_id, COORD)
        else:
            service.receipt(permit.permit_id, token, COORD)


@pytest.mark.parametrize("state", ["unloaded", "interrupted", "approval_or_input_waiting", "unknown",
                                  "permissions_unverified", "origin_restricted"])
def test_restricted_runtime_never_dispatches_or_claims_receipt(setup, state):
    service, _, _, _, _ = setup
    permit = issue(setup)
    transport = Transport(state)
    result = service.notify(permit.permit_id, transport)
    assert state in result["detail"]
    assert not result["receipt_confirmed"] and transport.added == []


def test_restricted_observation_can_recover_before_any_external_call(setup):
    service, _, _, _, now = setup
    permit = issue(setup)
    transport = Transport("unknown")
    service.notify(permit.permit_id, transport)
    now[0] += 3
    transport.state = "idle"
    service.notify(permit.permit_id, transport)
    assert len(transport.added) == 1


def test_backoff_deadline_and_attempts_survive_reopen(setup):
    service, _, _, _, now = setup
    permit = issue(setup)
    transport = Transport("unknown")
    service.notify(permit.permit_id, transport)
    with pytest.raises(DeliveryError, match="backoff"):
        service.notify(permit.permit_id, transport)
    for _ in range(2):
        now[0] += 31
        service.journal = DeliveryStore.open(service.journal.path, service.journal.store_id)
        service.notify(permit.permit_id, transport)
    with pytest.raises(DeliveryError, match="budget_exhausted"):
        service.notify(permit.permit_id, transport)
    assert issue(setup).deadline == permit.deadline
    now[0] = permit.deadline
    with pytest.raises(DeliveryError, match="budget_exhausted"):
        service.notify(permit.permit_id, transport)


@pytest.mark.parametrize("damage", ["missing", "replaced", "corrupt", "identity", "permissions"])
def test_sidecar_damage_never_recreates_readiness_even_empty_page(setup, damage):
    service, _, _, _, _ = setup
    permit = issue(setup)
    path = service.journal.path
    if damage == "missing":
        path.unlink()
    elif damage == "replaced":
        path.rename(path.with_suffix(".old"))
        DeliveryStore.create(path)
    elif damage == "corrupt":
        path.write_bytes(b"not SQLite")
    elif damage == "identity":
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE meta SET id='other'")
    else:
        path.chmod(0o644)
    with pytest.raises(DeliveryError):
        service.status(permit.permit_id)
    with pytest.raises(DeliveryError):
        service.pending(str(WAVE), str(WORKER), RECIPIENT, after_sequence=4)
    if damage == "missing":
        assert not path.exists()


def test_worker_result_receipt_routes_to_coordinator_and_unroutable_prose_visible(setup):
    service, events, _, runtime, _ = setup
    result = command(30, EventKind.PROSE_MESSAGE, actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
                     payload={"text": "review result"})
    assert events.append(result, RECIPIENT).disposition == EventDisposition.OBSERVED
    permit = service.issue(str(WAVE), str(result.event_id), str(WORKER), RECIPIENT, runtime, deadline=1120)
    assert permit.recipient_role == "coordinator"
    assert any(row["event_id"] == str(result.event_id)
               for row in service.pending(str(WAVE), "coordinator", COORD)["events"])
    with pytest.raises(DeliveryError):
        service.fetch(permit.permit_id, RECIPIENT)
    token = service.fetch(permit.permit_id, COORD)["fetch_token"]
    service.receipt(permit.permit_id, token, COORD)
    generic = command(31, EventKind.PROSE_MESSAGE,
                      actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION), payload={"text": "unroutable"})
    events.append(generic, COORD)
    assert any(row["state"] == "issuer_route_unresolved"
               for row in service.pending(str(WAVE), "coordinator", COORD)["events"])
    with pytest.raises(DeliveryError, match="route_unresolved"):
        service.issue(str(WAVE), str(generic.event_id), "coordinator", COORD, runtime, deadline=1120)


def test_journal_calls_and_rpc_never_hold_authority_write_transaction(setup):
    service, _, _, _, _ = setup
    permit = issue(setup)
    transport = Transport()
    def competing_writer():
        with sqlite3.connect(service.authority.config.path, timeout=0) as connection:
            connection.execute("BEGIN IMMEDIATE")
    transport.after_add = competing_writer
    service.notify(permit.permit_id, transport)
    assert len(transport.added) == 1


def test_stopped_notification_has_no_effect_on_authority(setup):
    service, _, assignment, _, _ = setup
    permit = issue(setup)
    with pytest.raises(DeliveryError):
        service.stop(permit.permit_id, RECIPIENT)
    service.stop(permit.permit_id, COORD)
    with pytest.raises(DeliveryError, match="stopped"):
        service.notify(permit.permit_id, Transport())
    with service.authority.transaction() as tx:
        assert not tx.read_assignment(assignment.assignment.ref).acknowledged


@pytest.mark.parametrize("field,value", [("policy_revision", 2), ("recipient_generation", str(UUID(int=999))),
                                         ("authority_store_id", "other"), ("event_digest", "wrong"),
                                         ("capability_id", "wrong"), ("wave", "wrong-wave")])
def test_tampered_permit_bindings_refused_before_dispatch(setup, field, value):
    service, _, _, _, _ = setup
    permit = issue(setup)
    with pytest.raises(DeliveryError):
        service._validate(replace(permit, **{field: value}))


@pytest.mark.parametrize("kind,state,payload", [
    (EventKind.ASSIGNMENT_HELD, "held", {"conditions": ["review"], "reason": "hold", "resume_state": "queued"}),
    (EventKind.ASSIGNMENT_CANCELLED, "cancelled", {"reason": "cancel"}),
])
def test_authoritative_hold_cancel_fence_preexisting_permit(setup, kind, state, payload):
    service, events, assignment, _, _ = setup
    permit = issue(setup)
    control = command(50, kind, actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
                      assignment=assignment.assignment, payload=payload)
    assert events.append(control, COORD).disposition == EventDisposition.APPLIED
    transport = Transport()
    result = service.notify(permit.permit_id, transport)
    assert result["detail"] == "wave_" + state and transport.added == []
    assert service.fetch(permit.permit_id, RECIPIENT)["restriction"] == state


def test_real_policy_revision_fences_permit_and_old_receipt(setup):
    service, events, _, _, _ = setup
    permit = issue(setup)
    token = service.fetch(permit.permit_id, RECIPIENT)["fetch_token"]
    service.receipt(permit.permit_id, token, RECIPIENT)
    change = PolicyRevisionChange(1, 2)
    event = command(51, EventKind.POLICY_REVISED,
                    actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
                    payload={"operator_reason": "new policy"}, effect=canonical_record(change=change))
    assert events.append_policy_revision(event, COORD, change).disposition == EventDisposition.APPLIED
    assert not service.status(permit.permit_id)["receipt_confirmed"]
    with pytest.raises(DeliveryError, match="stale_policy"):
        service.receipt(permit.permit_id, token, RECIPIENT)


@pytest.mark.parametrize("received_before", [False, True])
def test_real_owner_replacement_fences_receipt_retry_and_preserves_history(setup, received_before):
    service, events, _, _, _ = setup
    permit = issue(setup)
    token = service.fetch(permit.permit_id, RECIPIENT)["fetch_token"]
    if received_before:
        service.receipt(permit.permit_id, token, RECIPIENT)
    with service.authority.transaction() as tx:
        old = tx.read_owner(WAVE, WORKER)
    probe = service.probe
    replacement_process = replace(WORKER_PROCESS, start_ticks=999)
    probe.processes[WORKER_THREAD] = replacement_process
    probe.observe_recorded = lambda process: replacement_process if process == WORKER_PROCESS else process
    generation = OwnerGenerationId(UUID(int=103))
    events.ids.owner_ids = iter((generation,))
    capability = snapshot("worker")
    intent = ReplaceDeadOwner(WAVE, WORKER, old.record_version, WORKER_GENERATION, capability.snapshot_id, 1)
    event = command(52, EventKind.OWNER_REPLACED, actor(WORKER, WORKER_THREAD, generation),
                    effect=canonical_record(intent=intent, snapshot=capability))
    assert events.append_owner_change(event, RECIPIENT, intent, capability).disposition == EventDisposition.APPLIED
    result = service.status(permit.permit_id)
    assert not result["receipt_confirmed"] and not result["current_binding"]
    assert bool(result["historical_receipt"]) == received_before
    with pytest.raises(DeliveryError):
        service.fetch(permit.permit_id, RECIPIENT)
    with pytest.raises(DeliveryError):
        service.receipt(permit.permit_id, token, RECIPIENT)
    with pytest.raises(DeliveryError):
        service.notify(permit.permit_id, Transport())


def test_rejected_control_event_cannot_mint_delivery_permit(setup):
    service, events, assignment, runtime, _ = setup
    early = command(53, EventKind.ASSIGNMENT_ACCEPTED, actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
                    assignment=assignment.assignment, correlation=4)
    assert events.append(early, RECIPIENT).disposition == EventDisposition.REJECTED
    with pytest.raises(DeliveryError, match="unresolved_or_rejected"):
        service.issue(str(WAVE), str(early.event_id), str(WORKER), RECIPIENT, runtime, deadline=1120)


def test_issuer_can_reconcile_own_lost_permit_without_recipient_watch(setup):
    service, _, assignment, _, _ = setup
    pending = service.pending(str(WAVE), str(COORDINATOR), COORD)
    assert any(row["event_id"] == str(assignment.event_id) and row["state"] == "event_without_permit"
               for row in pending["events"])


@pytest.mark.parametrize("limit", [0, 101, True])
def test_pending_budget_is_explicit(setup, limit):
    service, _, _, _, _ = setup
    with pytest.raises(DeliveryError, match="page limit"):
        service.pending(str(WAVE), str(WORKER), RECIPIENT, limit=limit)


def test_policy_rebrief_keeps_stale_result_receipt_visible_without_resetting_attempts(setup):
    service, events, _, runtime, now = setup
    result = command(60, EventKind.PROSE_MESSAGE, actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
                     payload={"text": "review result"})
    assert events.append(result, RECIPIENT).disposition == EventDisposition.OBSERVED
    permit = service.issue(str(WAVE), str(result.event_id), str(WORKER), RECIPIENT, runtime, deadline=1120)
    service.notify(permit.permit_id, Transport())
    service.receipt(permit.permit_id, service.fetch(permit.permit_id, COORD)["fetch_token"], COORD)
    before = service.journal.read(permit.permit_id)
    change = PolicyRevisionChange(1, 2)
    revised = command(61, EventKind.POLICY_REVISED,
                      actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
                      payload={"operator_reason": "rebrief"}, effect=canonical_record(change=change))
    assert events.append_policy_revision(revised, COORD, change).disposition == EventDisposition.APPLIED
    for n, role, thread, generation, context in [
        (62, COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION, COORD),
        (63, WORKER, WORKER_THREAD, WORKER_GENERATION, RECIPIENT),
    ]:
        with service.authority.transaction() as tx:
            owner = tx.read_owner(WAVE, role)
        expected = ExpectedOwnerBindings(WAVE, role, thread, generation, owner.capability_snapshot_id,
                                         1, owner.record_version)
        intent = RebriefOwner(expected, 2)
        event = command(n, EventKind.OWNER_REBRIEFED, actor(role, thread, generation),
                        effect=canonical_record(intent=intent))
        assert events.append_owner_change(event, context, intent).disposition == EventDisposition.APPLIED
    assert not service.status(permit.permit_id)["receipt_confirmed"]
    for role, context in [(COORDINATOR, COORD), (WORKER, RECIPIENT)]:
        rows = service.pending(str(WAVE), str(role), context)["events"]
        stale = next(row for row in rows if row["event_id"] == str(result.event_id))
        assert stale["state"] == "permit_binding_stale" and stale["receipt_confirmed"] is False
        assert stale["historical_receipt"] is True
    now[0] += 3
    with pytest.raises(DeliveryError, match="permit_id_payload_conflict"):
        service.issue(str(WAVE), str(result.event_id), str(WORKER), RECIPIENT, runtime,
                      deadline=1500, max_attempts=5)
    assert service.journal.read(permit.permit_id) == before


@pytest.mark.parametrize("party", [COORDINATOR_PROCESS, WORKER_PROCESS])
@pytest.mark.parametrize("unavailable", [False, True])
def test_process_change_during_inspection_fenced_before_queue_add(setup, party, unavailable):
    service, _, _, _, _ = setup
    permit = issue(setup)
    class ChangedTransport(Transport):
        def inspect(self, *args):
            changed = (ProcessObservationUnavailable(ObservationFailure.PROBE_UNAVAILABLE, "fixture probe loss")
                       if unavailable else replace(party, start_ticks=party.start_ticks + 1))
            service.probe.observe_recorded = lambda process: changed if process == party else process
            return super().inspect(*args)
    transport = ChangedTransport()
    result = service.notify(permit.permit_id, transport)
    assert transport.added == []
    assert result["phase"] == "unknown" and result["detail"] == "owner_process_changed_or_unknown"
    assert service.journal.read(permit.permit_id)[1]["external_started"]  # Never reset uncertain-call history.


@pytest.mark.parametrize("target", ["accepted", "implementing", "pr_open", "held", "completed", "cancelled"])
def test_fresh_reconciliation_recovers_nonterminal_work_after_all_delivery_receipts(setup, target):
    service, events, assignment, runtime, _ = setup
    coordinator = actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION)
    worker = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    binding = assignment.assignment
    def confirm(event, context):
        permit = service.issue(str(WAVE), str(event.event_id), str(event.actor.role_id), context,
                               runtime, deadline=1120)
        recipient = RECIPIENT if event.actor.role_id == COORDINATOR else COORD
        service.receipt(permit.permit_id, service.fetch(permit.permit_id, recipient)["fetch_token"], recipient)
    def append(event, context):
        assert events.append(event, context).disposition == EventDisposition.APPLIED
        confirm(event, context)
    confirm(assignment, COORD)
    append(command(70, EventKind.ASSIGNMENT_READ, worker, assignment=binding, correlation=4), RECIPIENT)
    append(command(71, EventKind.ASSIGNMENT_ACCEPTED, worker, assignment=binding, correlation=4), RECIPIENT)
    if target in {"implementing", "pr_open", "completed"}:
        append(command(72, EventKind.GATE_APPROVED, coordinator, assignment=binding,
                       payload={"gate_id": "implementation", "verdict": "approved"}), COORD)
        append(command(73, EventKind.ASSIGNMENT_IMPLEMENTING, worker, assignment=binding, correlation=72), RECIPIENT)
    if target in {"pr_open", "completed"}:
        binding = replace(binding, pr_base="1" * 40, pr_head="2" * 40)
        append(command(74, EventKind.ASSIGNMENT_PR_OPEN, worker, assignment=binding), RECIPIENT)
    if target == "completed":
        append(command(75, EventKind.MERGE_CLEARED, coordinator, assignment=binding), COORD)
        observed = command(76, EventKind.EXTERNAL_MERGE_OBSERVED, coordinator, assignment=binding,
                           payload={"merge_commit": "3" * 40})
        assert events.append(observed, COORD).disposition == EventDisposition.RECONCILED
        confirm(observed, COORD)
        append(command(79, EventKind.ASSIGNMENT_COMPLETED, coordinator, assignment=binding, correlation=76,
                       payload={"merge_commit": "3" * 40}), COORD)
    if target == "held":
        append(command(77, EventKind.ASSIGNMENT_HELD, coordinator, assignment=binding,
                       payload={"reason": "review", "conditions": ["review"], "resume_state": "accepted"}), COORD)
    if target == "cancelled":
        append(command(78, EventKind.ASSIGNMENT_CANCELLED, coordinator, assignment=binding,
                       payload={"reason": "cancel"}), COORD)
    assert all(delivery["receipt"] for _, delivery in service.journal.page())
    for role, context in [(WORKER, RECIPIENT), (COORDINATOR, COORD)]:
        result = service.pending(str(WAVE), str(role), context, after_sequence=0)
        if target in {"completed", "cancelled"}:
            assert result["events"] == []
        else:
            assert len(result["events"]) == 1
            row = result["events"][0]
            assert row["state"] == "assignment_unfinished" and row["assignment_state"] == target
            assert row["restriction"] == ("held" if target == "held" else None)
            assert row["assignment_id"] == str(binding.ref.assignment_id) and row["revision"] == 1
        assert not result["cursor_advanced"]
