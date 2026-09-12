"""Durable event, acknowledgement, projection, and replay witnesses for #205."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from lib.native_wave.cursors import advance_cursor, merge_cursor
from lib.native_wave.event_types import (
    ActorBinding,
    AssignmentBinding,
    AssignmentState,
    CanonicalRecord,
    CursorState,
    EventDisposition,
    EventId,
    EventKind,
    EventPayload,
    EventValidationError,
    NativeCommand,
    PolicyRevisionChange,
    ProvenanceClass,
    ProvenanceEvidence,
    canonical_json_bytes,
    canonical_record,
    command_from_bytes,
    digest_bytes,
)
from lib.native_wave.events import EventAuthorizationError, EventService, _project_command
from lib.native_wave.replay import rebuild_projections, verify_wave
from lib.native_wave.storage import SQLiteWaveStore, StoreConfig
from lib.native_wave.types import (
    AssignmentRef,
    BootstrapGrantSpec,
    BootstrapRequest,
    CapabilityEvidence,
    CapabilityField,
    CapabilityFieldRequirement,
    CapabilityRequirements,
    CapabilitySnapshot,
    ClaimId,
    CoordinatorGenerationId,
    CorruptStore,
    ExpectedOwnerBindings,
    GrantId,
    GrantPurpose,
    LocalIdentityContext,
    OwnerGenerationId,
    PhysicalTargetKey,
    ProcessCoordinates,
    ProcessObservation,
    RebriefOwner,
    ReplaceDeadOwner,
    RepositoryKey,
    ReserveClaim,
    RoleId,
    ThreadId,
    UpdateCapability,
    WaveId,
    WorktreeEvidence,
)

NOW = datetime(2026, 9, 7, 18, 0, tzinfo=timezone.utc)
WAVE = WaveId("test-wave")
COORDINATOR = RoleId("coordinator")
WORKER = RoleId("worker-A")
COORDINATOR_THREAD = ThreadId(UUID(int=1))
WORKER_THREAD = ThreadId(UUID(int=2))
COORDINATOR_GENERATION = OwnerGenerationId(UUID(int=101))
WORKER_GENERATION = OwnerGenerationId(UUID(int=102))
COORDINATOR_PROCESS = ProcessCoordinates("test-host", UUID(int=3), 4001, 101)
WORKER_PROCESS = ProcessCoordinates("test-host", UUID(int=3), 4002, 102)
REPOSITORY = RepositoryKey("test-host", "/repos/codex-power-pack/.git")
TARGET = PhysicalTargetKey("test-host", "/worktrees/issue-205")
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
BASE = "1" * 40
HEAD = "2" * 40


class FakeClock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic_ns(self) -> int:
        return 200


class FakeIds:
    def __init__(self) -> None:
        self.owner_ids = iter((COORDINATOR_GENERATION, WORKER_GENERATION))

    def new_owner_generation_id(self) -> OwnerGenerationId:
        return next(self.owner_ids)

    def new_claim_id(self) -> ClaimId:
        return ClaimId(UUID(int=201))


class FakeProbe:
    def __init__(self) -> None:
        self.processes = {
            COORDINATOR_THREAD: COORDINATOR_PROCESS,
            WORKER_THREAD: WORKER_PROCESS,
        }

    def observe_self(self, context: LocalIdentityContext) -> ProcessObservation:
        return ProcessObservation(
            context.thread_id,
            self.processes[context.thread_id],
            100,
            "test-process",
        )

    def revalidate(self, candidate: ProcessObservation) -> ProcessObservation:
        return replace(candidate, observed_monotonic_ns=110)

    def observe_recorded(self, process: ProcessCoordinates) -> ProcessCoordinates:
        return process


def snapshot(model: str) -> CapabilitySnapshot:
    return CapabilitySnapshot.create(
        schema_version=1,
        cli_version="1.0",
        runtime_version="python-3.11",
        model=model,
        reasoning_effort="high",
        sandbox_mode="danger-full-access",
        approval_policy="never",
        workspace_roots=("/repos",),
        tool_families=("mailbox", "shell"),
        required_plugins=("flow",),
        delivery_mechanisms=("mailbox",),
        wake_mechanisms=("watch",),
        web_mode="disabled",
        captured_at=NOW,
        evidence=(CapabilityEvidence(CapabilityField.MODEL, "runtime", "fixture"),),
    )


def actor(role: RoleId, thread: ThreadId, generation: OwnerGenerationId) -> ActorBinding:
    if role == COORDINATOR:
        return ActorBinding(role, thread, CoordinatorGenerationId(generation.value))
    return ActorBinding(role, thread, generation)


def event_id(value: int) -> EventId:
    return EventId(UUID(int=value))


def command(
    value: int,
    kind: EventKind,
    event_actor: ActorBinding,
    *,
    assignment: AssignmentBinding | None = None,
    correlation: int | None = None,
    causation: int | None = None,
    payload: dict[str, object] | None = None,
    effect: CanonicalRecord = CanonicalRecord(),
) -> NativeCommand:
    return NativeCommand(
        event_id(value),
        kind,
        WAVE,
        event_actor,
        ProvenanceEvidence(ProvenanceClass.REGISTRY_BOUND_LOCAL, "fixture"),
        assignment=assignment,
        correlation_id=event_id(correlation) if correlation is not None else None,
        causation_id=event_id(causation) if causation is not None else None,
        payload=EventPayload.from_mapping(payload or {}),
        effect=effect,
    )


def create_store(tmp_path: Path) -> SQLiteWaveStore:
    tmp_path.chmod(0o700)
    return SQLiteWaveStore.create(StoreConfig(tmp_path / "wave.sqlite3", busy_timeout_ms=100))


def bootstrap_and_register(
    service: EventService,
    coordinator_snapshot: CapabilitySnapshot,
    worker_snapshot: CapabilitySnapshot,
) -> tuple[NativeCommand, NativeCommand]:
    coordinator_grant = GrantId(UUID(int=11))
    worker_grant = GrantId(UUID(int=12))
    request = BootstrapRequest(
        WAVE,
        REPOSITORY,
        1,
        (
            BootstrapGrantSpec(
                COORDINATOR,
                COORDINATOR_THREAD,
                GrantPurpose.REGISTER,
                coordinator_grant,
                NOW + timedelta(hours=1),
            ),
            BootstrapGrantSpec(
                WORKER,
                WORKER_THREAD,
                GrantPurpose.REGISTER,
                worker_grant,
                NOW + timedelta(hours=1),
            ),
        ),
        NOW,
    )
    bootstrap = command(
        1,
        EventKind.WAVE_BOOTSTRAPPED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        payload={"operator_reason": "test bootstrap"},
        effect=canonical_record(request=request),
    )
    assert service.bootstrap(bootstrap, request).disposition is EventDisposition.APPLIED

    from lib.native_wave.types import RegisterOwner

    coordinator_intent = RegisterOwner(
        WAVE,
        COORDINATOR,
        coordinator_snapshot.snapshot_id,
        1,
        coordinator_grant,
    )
    coordinator_registration = command(
        2,
        EventKind.OWNER_REGISTERED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        payload={"grant_id": str(coordinator_grant)},
        effect=canonical_record(intent=coordinator_intent, snapshot=coordinator_snapshot),
    )
    assert (
        service.append_owner_change(
            coordinator_registration,
            LocalIdentityContext(COORDINATOR_THREAD),
            coordinator_intent,
            coordinator_snapshot,
        ).disposition
        is EventDisposition.APPLIED
    )

    worker_intent = RegisterOwner(WAVE, WORKER, worker_snapshot.snapshot_id, 1, worker_grant)
    worker_registration = command(
        3,
        EventKind.OWNER_REGISTERED,
        actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
        payload={"grant_id": str(worker_grant)},
        effect=canonical_record(intent=worker_intent, snapshot=worker_snapshot),
    )
    assert (
        service.append_owner_change(
            worker_registration,
            LocalIdentityContext(WORKER_THREAD),
            worker_intent,
            worker_snapshot,
        ).disposition
        is EventDisposition.APPLIED
    )
    return coordinator_registration, worker_registration


def assignment_binding(worker_snapshot: CapabilitySnapshot) -> AssignmentBinding:
    return AssignmentBinding(
        AssignmentRef(UUID(int=20), 1, DIGEST_A),
        205,
        WORKER,
        WORKER_THREAD,
        WORKER_GENERATION,
        CoordinatorGenerationId(COORDINATOR_GENERATION.value),
        worker_snapshot.snapshot_id,
        CapabilityRequirements.create(()),
        (),
        1,
        plan_digest=DIGEST_B,
    )


def test_canonical_payload_and_effect_are_immutable() -> None:
    nested: dict[str, object] = {"conditions": ["one"]}
    payload = EventPayload.from_mapping(nested)
    nested["conditions"] = ["changed"]
    assert payload.get("conditions") == ("one",)

    with pytest.raises(EventValidationError, match="effect schema"):
        command(
            1,
            EventKind.WAVE_BOOTSTRAPPED,
            actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
            payload={"operator_reason": "missing effect"},
        )


@pytest.mark.parametrize("invalid", ["not-a-uuid", 1, True, None])
def test_event_id_rejects_non_uuid_constructor_values(invalid: object) -> None:
    with pytest.raises(EventValidationError, match="UUID"):
        EventId(invalid)  # type: ignore[arg-type]


def test_event_id_parser_rejects_noncanonical_uppercase_spelling() -> None:
    with pytest.raises(EventValidationError, match="canonical lowercase"):
        EventId.parse("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA")


def test_authority_versions_reject_boolean_aliases_in_constructors_and_parser() -> None:
    binding = assignment_binding(snapshot("worker-model"))
    with pytest.raises(EventValidationError, match="assignment issue"):
        replace(binding, issue=True)

    valid = command(
        90,
        EventKind.ASSIGNMENT_QUEUED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        assignment=binding,
    )
    with pytest.raises(EventValidationError, match="schema version"):
        replace(valid, schema_version=True)
    payload = json.loads(valid.canonical_bytes())
    payload["schema_version"] = True
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(EventValidationError, match="schema version"):
        command_from_bytes(encoded)


def test_cursor_merge_is_sparse_and_bounded_after_large_prefix() -> None:
    current = CursorState(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION, highest_contiguous=50_000)
    newer = advance_cursor(current, observed_sequences=(50_002,), scanned_through=50_002)
    merged = merge_cursor(current, newer)
    assert merged.highest_contiguous == 50_000
    assert merged.sparse_sequences == (50_002,)
    assert merged.gaps == (50_001,)
    with pytest.raises(EventValidationError, match="endpoint must be an integer"):
        advance_cursor(current, observed_sequences=(), scanned_through=True)
    with pytest.raises(EventValidationError, match="outside the scanned range"):
        advance_cursor(current, observed_sequences=(True,), scanned_through=50_001)


def test_full_journal_cursor_progresses_across_bounded_ten_thousand_event_pages(
    tmp_path: Path,
) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    bootstrap_and_register(service, snapshot("coordinator-model"), snapshot("worker-model"))
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)

    with store.transaction() as tx:
        for offset in range(10_002):
            prose = command(
                1_000 + offset,
                EventKind.PROSE_MESSAGE,
                worker_actor,
                payload={"text": f"irrelevant-{offset}"},
            )
            tx.append_event(prose, disposition=EventDisposition.OBSERVED, reason=None, committed_at=NOW)
            tx._audit_record = None  # bounded fixture construction; production append stays one event/tx
        tx.commit()

    first_scan = command(
        50_000,
        EventKind.CURSOR_ADVANCED,
        worker_actor,
        payload={"cursor_highest_contiguous": 10_000, "cursor_sparse": ()},
    )
    _, first_page = service.scan_and_advance(first_scan, LocalIdentityContext(WORKER_THREAD))
    assert len(first_page.events) == 10_000
    assert first_page.cursor.highest_contiguous == 10_000

    second_scan = command(
        50_001,
        EventKind.CURSOR_ADVANCED,
        worker_actor,
        payload={"cursor_highest_contiguous": 10_006, "cursor_sparse": ()},
    )
    _, second_page = service.scan_and_advance(second_scan, LocalIdentityContext(WORKER_THREAD))
    assert tuple(event.sequence for event in second_page.events) == tuple(range(10_001, 10_007))
    assert second_page.cursor.highest_contiguous == 10_006

    rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        replayed = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
        assert replayed is not None
        assert replayed.highest_contiguous == 10_006
        owner_before_corruption = tx.get_projection(WAVE, "owner", str(WORKER))
        cursor_before_corruption = replayed
        tx._connection.execute(
            "UPDATE events SET command_bytes=? WHERE wave_id=? AND sequence=?",
            (b"{}", str(WAVE), 10_001),
        )
        tx.commit()

    with pytest.raises(CorruptStore, match="command|event"):
        verify_wave(store, WAVE)
    with pytest.raises(CorruptStore, match="command|event"):
        rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        assert tx.get_projection(WAVE, "owner", str(WORKER)) == owner_before_corruption
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == cursor_before_corruption


def test_bootstrap_registration_assignment_claim_and_replay(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    coordinator_snapshot = snapshot("coordinator-model")
    worker_snapshot = snapshot("worker-model")
    coordinator_registration, _ = bootstrap_and_register(service, coordinator_snapshot, worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    coordinator_actor = actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)

    queued = command(4, EventKind.ASSIGNMENT_QUEUED, coordinator_actor, assignment=binding)
    queued_receipt = service.append(queued, LocalIdentityContext(COORDINATOR_THREAD))
    assert queued_receipt.disposition is EventDisposition.APPLIED
    read = command(5, EventKind.ASSIGNMENT_READ, worker_actor, assignment=binding, correlation=4)
    assert service.append(read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    accepted = command(
        6,
        EventKind.ASSIGNMENT_ACCEPTED,
        worker_actor,
        assignment=binding,
        correlation=4,
        causation=5,
    )
    assert service.append(accepted, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED

    with store.transaction() as tx:
        worker_owner = tx.read_owner(WAVE, WORKER)
        assert worker_owner is not None
    expected = ExpectedOwnerBindings(
        WAVE,
        WORKER,
        WORKER_THREAD,
        WORKER_GENERATION,
        worker_snapshot.snapshot_id,
        1,
        worker_owner.record_version,
        assignment=binding.ref,
    )
    reserve = ReserveClaim(
        expected,
        TARGET,
        REPOSITORY,
        205,
        "issue-205",
        binding.ref,
        DIGEST_B,
    )
    worktree = WorktreeEvidence(TARGET, REPOSITORY, False, None, 300, "fixture")
    claim_command = command(
        7,
        EventKind.CLAIM_RESERVED,
        worker_actor,
        payload={
            "claim_id": str(ClaimId(UUID(int=201))),
            "file_lane_digest": DIGEST_B,
            "worktree_evidence_digest": digest_bytes(canonical_json_bytes(worktree)),
        },
        effect=canonical_record(intent=reserve, worktree=worktree),
    )
    assert (
        service.append_claim_change(
            claim_command,
            LocalIdentityContext(WORKER_THREAD),
            reserve,
            worktree,
        ).disposition
        is EventDisposition.APPLIED
    )

    cursor_command = command(
        8,
        EventKind.CURSOR_ADVANCED,
        worker_actor,
        payload={"cursor_highest_contiguous": 7, "cursor_sparse": ()},
    )
    cursor_receipt, page = service.scan_and_advance(
        cursor_command,
        LocalIdentityContext(WORKER_THREAD),
    )
    assert cursor_receipt.disposition is EventDisposition.APPLIED
    assert tuple(event.sequence for event in page.events) == tuple(range(1, 8))
    assert page.cursor.highest_contiguous == 7

    report = verify_wave(store, WAVE)
    assert report.event_count == 8
    with store.transaction() as tx:
        tx._connection.execute(
            "DELETE FROM owners WHERE wave_id=? AND role_id=?",
            (str(WAVE), str(WORKER)),
        )
        tx.commit()
    with pytest.raises(CorruptStore, match="runtime owner authority"):
        verify_wave(store, WAVE)
    rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        assert tx.read_owner(WAVE, WORKER) is not None
        assert tx.read_claim(ClaimId(UUID(int=201))) is not None
        assert tx.read_preexisting_grant(GrantId(UUID(int=12))) is not None
        assert tx.read_assignment(binding.ref) is not None

    with store.transaction() as tx:
        kinds = {
            row[0]
            for row in tx._connection.execute("SELECT projection_kind FROM projections WHERE wave_id=?", (str(WAVE),))
        }
        tx._connection.execute("DELETE FROM projections WHERE wave_id=?", (str(WAVE),))
        tx._connection.execute("DELETE FROM cursors WHERE wave_id=?", (str(WAVE),))
        tx.commit()
    assert {"assignment", "capability", "claim", "grant", "owner", "wave"} <= kinds
    rebuilt = rebuild_projections(store, WAVE)
    assert rebuilt.event_count == 8
    verify_wave(store, WAVE)

    historical = service.get_receipt(
        WAVE,
        coordinator_registration.event_id,
        LocalIdentityContext(COORDINATOR_THREAD),
    )
    assert historical is not None


def test_changed_owner_mutation_reusing_event_id_conflicts(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    coordinator_snapshot = snapshot("coordinator-model")
    worker_snapshot = snapshot("worker-model")
    original, _ = bootstrap_and_register(service, coordinator_snapshot, worker_snapshot)

    from lib.native_wave.types import RegisterOwner

    changed_snapshot = snapshot("changed-model")
    changed_intent = RegisterOwner(
        WAVE,
        COORDINATOR,
        changed_snapshot.snapshot_id,
        1,
        GrantId(UUID(int=11)),
    )
    changed = replace(
        original,
        effect=canonical_record(intent=changed_intent, snapshot=changed_snapshot),
    )
    receipt = service.append_owner_change(
        changed,
        LocalIdentityContext(COORDINATOR_THREAD),
        changed_intent,
        changed_snapshot,
    )
    assert receipt.disposition is EventDisposition.REJECTED
    assert receipt.reason == "event_id_payload_conflict"
    assert receipt.sequence is None
    with store.transaction() as tx:
        owner = tx.read_owner(WAVE, COORDINATOR)
        assert owner is not None
        assert owner.capability_snapshot_id == coordinator_snapshot.snapshot_id


def test_policy_rebrief_is_explicit_and_does_not_acknowledge_assignment(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    probe = FakeProbe()
    service = EventService(store, process_probe=probe, ids=FakeIds(), clock=FakeClock())
    coordinator_snapshot = snapshot("coordinator-model")
    worker_snapshot = snapshot("worker-model")
    bootstrap_and_register(service, coordinator_snapshot, worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    queued = command(
        40,
        EventKind.ASSIGNMENT_QUEUED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        assignment=binding,
    )
    assert service.append(queued, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED

    change = PolicyRevisionChange(1, 2)
    revision_command = command(
        41,
        EventKind.POLICY_REVISED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        payload={"operator_reason": "new wave policy"},
        effect=canonical_record(change=change),
    )
    assert (
        service.append_policy_revision(
            revision_command,
            LocalIdentityContext(COORDINATOR_THREAD),
            change,
        ).disposition
        is EventDisposition.APPLIED
    )

    with store.transaction() as tx:
        coordinator_owner = tx.read_owner(WAVE, COORDINATOR)
        worker_owner = tx.read_owner(WAVE, WORKER)
        assert coordinator_owner is not None and worker_owner is not None
    coordinator_expected = ExpectedOwnerBindings(
        WAVE,
        COORDINATOR,
        COORDINATOR_THREAD,
        coordinator_owner.generation_id,
        coordinator_owner.capability_snapshot_id,
        1,
        coordinator_owner.record_version,
    )
    coordinator_rebrief = RebriefOwner(coordinator_expected, 2)
    coordinator_rebrief_command = command(
        42,
        EventKind.OWNER_REBRIEFED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        effect=canonical_record(intent=coordinator_rebrief),
    )
    assert (
        service.append_owner_change(
            coordinator_rebrief_command,
            LocalIdentityContext(COORDINATOR_THREAD),
            coordinator_rebrief,
        ).disposition
        is EventDisposition.APPLIED
    )

    worker_expected = ExpectedOwnerBindings(
        WAVE,
        WORKER,
        WORKER_THREAD,
        worker_owner.generation_id,
        worker_owner.capability_snapshot_id,
        1,
        worker_owner.record_version,
    )
    worker_rebrief = RebriefOwner(worker_expected, 2)
    worker_rebrief_command = command(
        43,
        EventKind.OWNER_REBRIEFED,
        actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
        effect=canonical_record(intent=worker_rebrief),
    )
    assert (
        service.append_owner_change(
            worker_rebrief_command,
            LocalIdentityContext(WORKER_THREAD),
            worker_rebrief,
        ).disposition
        is EventDisposition.APPLIED
    )
    with store.transaction() as tx:
        current_worker = tx.read_owner(WAVE, WORKER)
        stored_assignment = tx.read_assignment(binding.ref)
        assert current_worker is not None and stored_assignment is not None
        assert current_worker.generation_id == WORKER_GENERATION
        assert current_worker.capability_snapshot_id == worker_snapshot.snapshot_id
        assert current_worker.policy_revision == 2
        assert current_worker.record_version == worker_owner.record_version + 1
        assert stored_assignment.policy_revision == 1
        assert not stored_assignment.acknowledged

    for value, kind in ((46, EventKind.ASSIGNMENT_READ), (47, EventKind.ASSIGNMENT_ACCEPTED)):
        stale_ack = command(value, kind, actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
                            assignment=binding, correlation=40)
        refused = service.append(stale_ack, LocalIdentityContext(WORKER_THREAD))
        assert refused.disposition is EventDisposition.REJECTED and refused.reason == "stale_policy"
    rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        assert tx.read_assignment(binding.ref) == stored_assignment
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) is None

    stale_cas = command(
        44,
        EventKind.OWNER_REBRIEFED,
        actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
        effect=canonical_record(intent=worker_rebrief),
    )
    stale_receipt = service.append_owner_change(
        stale_cas,
        LocalIdentityContext(WORKER_THREAD),
        worker_rebrief,
    )
    assert stale_receipt.disposition is EventDisposition.REJECTED
    assert stale_receipt.reason == "stale_owner_version"

    with store.transaction() as tx:
        current_worker = tx.read_owner(WAVE, WORKER)
        assert current_worker is not None
    next_expected = ExpectedOwnerBindings(
        WAVE,
        WORKER,
        WORKER_THREAD,
        current_worker.generation_id,
        current_worker.capability_snapshot_id,
        2,
        current_worker.record_version,
    )
    stale_process_rebrief = RebriefOwner(next_expected, 3)
    probe.processes[WORKER_THREAD] = ProcessCoordinates("test-host", UUID(int=3), 4012, 202)
    stale_process_command = command(
        45,
        EventKind.OWNER_REBRIEFED,
        actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
        effect=canonical_record(intent=stale_process_rebrief),
    )
    stale_process_receipt = service.append_owner_change(
        stale_process_command,
        LocalIdentityContext(WORKER_THREAD),
        stale_process_rebrief,
    )
    assert stale_process_receipt.disposition is EventDisposition.REJECTED
    assert stale_process_receipt.reason == "owner_mismatch"


def test_capability_relevance_controls_assignment_revision_and_ack(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker-model")
    bootstrap_and_register(service, snapshot("coordinator-model"), worker_snapshot)
    coordinator_actor = actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    irrelevant_binding = assignment_binding(worker_snapshot)
    relevant_requirements = CapabilityRequirements.create(
        (CapabilityFieldRequirement(CapabilityField.MODEL, ("worker-model",)),)
    )
    relevant_binding = replace(
        irrelevant_binding,
        ref=AssignmentRef(UUID(int=22), 1, DIGEST_B),
        capability_requirements=relevant_requirements,
    )
    irrelevant_queue = command(
        60,
        EventKind.ASSIGNMENT_QUEUED,
        coordinator_actor,
        assignment=irrelevant_binding,
    )
    relevant_queue = command(
        61,
        EventKind.ASSIGNMENT_QUEUED,
        coordinator_actor,
        assignment=relevant_binding,
    )
    assert (
        service.append(irrelevant_queue, LocalIdentityContext(COORDINATOR_THREAD)).disposition
        is EventDisposition.APPLIED
    )
    assert (
        service.append(relevant_queue, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    )

    with store.transaction() as tx:
        worker_owner = tx.read_owner(WAVE, WORKER)
        assert worker_owner is not None
    changed_snapshot = snapshot("changed-model")
    expected = ExpectedOwnerBindings(
        WAVE,
        WORKER,
        WORKER_THREAD,
        WORKER_GENERATION,
        worker_snapshot.snapshot_id,
        1,
        worker_owner.record_version,
    )
    update = UpdateCapability(expected, changed_snapshot.snapshot_id)
    update_command = command(
        62,
        EventKind.OWNER_CAPABILITY_UPDATED,
        worker_actor,
        effect=canonical_record(intent=update, snapshot=changed_snapshot),
    )
    assert (
        service.append_owner_change(
            update_command,
            LocalIdentityContext(WORKER_THREAD),
            update,
            changed_snapshot,
        ).disposition
        is EventDisposition.APPLIED
    )

    irrelevant_read = command(
        63,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=irrelevant_binding,
        correlation=60,
    )
    assert service.append(irrelevant_read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    relevant_read = command(
        64,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=relevant_binding,
        correlation=61,
    )
    relevant_receipt = service.append(relevant_read, LocalIdentityContext(WORKER_THREAD))
    assert relevant_receipt.disposition is EventDisposition.REJECTED
    assert relevant_receipt.reason == "capability_requirements_unsatisfied"
    with store.transaction() as tx:
        relevant_assignment = tx.read_assignment(relevant_binding.ref)
        relevant_projection = tx.get_projection(
            WAVE,
            "assignment",
            str(relevant_binding.ref.assignment_id),
        )
        assert relevant_assignment is not None and not relevant_assignment.acknowledged
        assert relevant_projection is not None
        assert relevant_projection["state"] == AssignmentState.QUEUED.value

    conditions = ("capability revision",)
    hold = command(
        65,
        EventKind.ASSIGNMENT_HELD,
        coordinator_actor,
        assignment=relevant_binding,
        payload={"conditions": conditions, "reason": "relevant capability changed", "resume_state": "queued"},
    )
    assert service.append(hold, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    changed_requirements = CapabilityRequirements.create(
        (CapabilityFieldRequirement(CapabilityField.MODEL, ("changed-model",)),)
    )
    rebound_binding = replace(
        relevant_binding,
        ref=AssignmentRef(relevant_binding.ref.assignment_id, 2, DIGEST_A),
        capability_snapshot_id=changed_snapshot.snapshot_id,
        capability_requirements=changed_requirements,
    )
    rebound = command(
        66,
        EventKind.ASSIGNMENT_REBOUND,
        coordinator_actor,
        assignment=rebound_binding,
        payload={"reason": "coordinator-authored relevant revision"},
    )
    assert service.append(rebound, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    rebound_read = command(
        67,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=rebound_binding,
        correlation=66,
    )
    assert service.append(rebound_read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    rebound_accept = command(
        68,
        EventKind.ASSIGNMENT_ACCEPTED,
        worker_actor,
        assignment=rebound_binding,
        correlation=66,
        causation=67,
    )
    assert service.append(rebound_accept, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    with store.transaction() as tx:
        rebound_assignment = tx.read_assignment(rebound_binding.ref)
        assert rebound_assignment is not None and rebound_assignment.acknowledged


def test_receipt_lookup_does_not_disclose_event_existence(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    probe = FakeProbe()
    foreign_thread = ThreadId(UUID(int=99))
    probe.processes[foreign_thread] = ProcessCoordinates("test-host", UUID(int=3), 4099, 199)
    service = EventService(store, process_probe=probe, ids=FakeIds(), clock=FakeClock())
    bootstrap_and_register(service, snapshot("coordinator-model"), snapshot("worker-model"))

    with pytest.raises(EventAuthorizationError, match="historical receipt"):
        service.get_receipt(WAVE, event_id(1), LocalIdentityContext(foreign_thread))
    with pytest.raises(EventAuthorizationError, match="historical receipt"):
        service.get_receipt(WAVE, event_id(999), LocalIdentityContext(foreign_thread))


def test_generic_append_refuses_typed_mutation_kind(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    registration, _ = bootstrap_and_register(
        service,
        snapshot("coordinator-model"),
        snapshot("worker-model"),
    )
    generic_bypass = replace(registration, event_id=event_id(99))
    with pytest.raises(EventValidationError, match="typed atomic mutation"):
        service.append(generic_bypass, LocalIdentityContext(COORDINATOR_THREAD))
    with store.transaction() as tx:
        assert tx.lookup_event(WAVE, event_id(99)) is None


def test_reducer_rejects_wrong_base_and_preserves_hold_during_rebrief() -> None:
    binding = assignment_binding(snapshot("worker-model"))
    coordinator_actor = actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    queued = command(30, EventKind.ASSIGNMENT_QUEUED, coordinator_actor, assignment=binding)
    projection = _project_command(queued, None).current
    assert projection is not None
    read = command(31, EventKind.ASSIGNMENT_READ, worker_actor, assignment=binding, correlation=30)
    projection = _project_command(read, projection).current
    assert projection is not None
    accepted = command(32, EventKind.ASSIGNMENT_ACCEPTED, worker_actor, assignment=binding, correlation=30)
    projection = _project_command(accepted, projection).current
    assert projection is not None
    gate = command(
        33,
        EventKind.GATE_APPROVED,
        coordinator_actor,
        assignment=binding,
        payload={"gate_id": "gate-1", "verdict": "approved"},
    )
    projection = _project_command(gate, projection).current
    assert projection is not None
    implementing = command(
        34,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        worker_actor,
        assignment=binding,
        correlation=33,
    )
    projection = _project_command(implementing, projection).current
    assert projection is not None
    pr_binding = replace(binding, pr_base=BASE, pr_head=HEAD)
    opened = command(35, EventKind.ASSIGNMENT_PR_OPEN, worker_actor, assignment=pr_binding)
    projection = _project_command(opened, projection).current
    assert projection is not None

    wrong_base = replace(pr_binding, pr_base="3" * 40)
    clearance = command(36, EventKind.MERGE_CLEARED, coordinator_actor, assignment=wrong_base)
    decision = _project_command(clearance, projection)
    assert not decision.accepted
    assert decision.reason == "assignment_binding_mismatch"

    held = command(
        37,
        EventKind.ASSIGNMENT_HELD,
        coordinator_actor,
        assignment=pr_binding,
        payload={"conditions": ("review",), "reason": "replacement", "resume_state": "pr_open"},
    )
    held_projection = _project_command(held, projection).current
    assert held_projection is not None
    rebound_binding = replace(
        pr_binding,
        ref=AssignmentRef(pr_binding.ref.assignment_id, 2, DIGEST_B),
        worker_generation=OwnerGenerationId(UUID(int=103)),
    )
    rebound = command(
        38,
        EventKind.ASSIGNMENT_REBOUND,
        coordinator_actor,
        assignment=rebound_binding,
        payload={"reason": "new owner"},
    )
    rebound_projection = _project_command(rebound, held_projection).current
    assert rebound_projection is not None
    assert rebound_projection["state"] == AssignmentState.HELD.value
    assert rebound_projection["brief_state"] == AssignmentState.QUEUED.value


def test_correlations_and_hold_rebind_require_fresh_coordinator_release(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker-model")
    bootstrap_and_register(service, snapshot("coordinator-model"), worker_snapshot)
    coordinator_actor = actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    binding = assignment_binding(worker_snapshot)
    unrelated_binding = replace(
        binding,
        ref=AssignmentRef(UUID(int=21), 1, DIGEST_B),
    )

    queue = command(100, EventKind.ASSIGNMENT_QUEUED, coordinator_actor, assignment=binding)
    assert service.append(queue, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    unrelated_queue = command(
        101,
        EventKind.ASSIGNMENT_QUEUED,
        coordinator_actor,
        assignment=unrelated_binding,
    )
    assert (
        service.append(unrelated_queue, LocalIdentityContext(COORDINATOR_THREAD)).disposition
        is EventDisposition.APPLIED
    )

    rejected_queue = command(102, EventKind.ASSIGNMENT_QUEUED, coordinator_actor, assignment=binding)
    rejected_queue_receipt = service.append(
        rejected_queue,
        LocalIdentityContext(COORDINATOR_THREAD),
    )
    assert rejected_queue_receipt.disposition is EventDisposition.REJECTED
    assert rejected_queue_receipt.reason == "assignment_already_exists"
    rejected_predecessor_read = command(
        103,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=binding,
        correlation=102,
    )
    rejected_read_receipt = service.append(
        rejected_predecessor_read,
        LocalIdentityContext(WORKER_THREAD),
    )
    assert rejected_read_receipt.disposition is EventDisposition.REJECTED
    assert rejected_read_receipt.reason == "correlation_event_not_successful"
    cross_assignment_read = command(
        104,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=binding,
        correlation=101,
    )
    cross_read_receipt = service.append(cross_assignment_read, LocalIdentityContext(WORKER_THREAD))
    assert cross_read_receipt.disposition is EventDisposition.REJECTED
    assert cross_read_receipt.reason == "correlation_assignment_mismatch"
    with store.transaction() as tx:
        projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        stored = tx.read_assignment(binding.ref)
        cursor_before_read = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
        assert projection is not None and projection["state"] == AssignmentState.QUEUED.value
        assert stored is not None and not stored.acknowledged
        assert cursor_before_read is None

    prose = command(
        105,
        EventKind.PROSE_MESSAGE,
        worker_actor,
        payload={"text": "not assignment evidence"},
    )
    assert service.append(prose, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.OBSERVED
    read = command(
        106,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=binding,
        correlation=100,
    )
    assert service.append(read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    with store.transaction() as tx:
        cursor_after_read = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
        projection_after_read = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        assert cursor_after_read is not None
        assert projection_after_read is not None
        assert projection_after_read["state"] == AssignmentState.READ.value

    unrelated_acceptance = command(
        107,
        EventKind.ASSIGNMENT_ACCEPTED,
        worker_actor,
        assignment=binding,
        correlation=105,
        causation=106,
    )
    wrong_acceptance_receipt = service.append(
        unrelated_acceptance,
        LocalIdentityContext(WORKER_THREAD),
    )
    assert wrong_acceptance_receipt.disposition is EventDisposition.REJECTED
    assert wrong_acceptance_receipt.reason == "correlation_kind_mismatch"
    with store.transaction() as tx:
        projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        stored = tx.read_assignment(binding.ref)
        assert projection is not None and projection["state"] == AssignmentState.READ.value
        assert stored is not None and not stored.acknowledged
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == cursor_after_read

    accepted = command(
        108,
        EventKind.ASSIGNMENT_ACCEPTED,
        worker_actor,
        assignment=binding,
        correlation=100,
        causation=106,
    )
    assert service.append(accepted, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    gate = command(
        109,
        EventKind.GATE_APPROVED,
        coordinator_actor,
        assignment=binding,
        payload={"gate_id": "gate-v1", "verdict": "approved"},
    )
    assert service.append(gate, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    implementing = command(
        110,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        worker_actor,
        assignment=binding,
        correlation=109,
    )
    assert service.append(implementing, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    pr_binding = replace(binding, pr_base=BASE, pr_head=HEAD)
    opened = command(111, EventKind.ASSIGNMENT_PR_OPEN, worker_actor, assignment=pr_binding)
    assert service.append(opened, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    conditions = ("fresh gate", "same head")
    hold = command(
        112,
        EventKind.ASSIGNMENT_HELD,
        coordinator_actor,
        assignment=pr_binding,
        payload={"conditions": conditions, "reason": "owner rebind", "resume_state": "pr_open"},
    )
    assert service.append(hold, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED

    worker_release = command(
        113,
        EventKind.ASSIGNMENT_RELEASED,
        worker_actor,
        assignment=pr_binding,
        payload={"conditions": conditions, "previous_state": "pr_open", "reason": "self release"},
    )
    worker_release_receipt = service.append(worker_release, LocalIdentityContext(WORKER_THREAD))
    assert worker_release_receipt.disposition is EventDisposition.REJECTED
    assert worker_release_receipt.reason == "coordinator_authority_required"

    rebound_binding = replace(
        pr_binding,
        ref=AssignmentRef(pr_binding.ref.assignment_id, 2, DIGEST_B),
    )
    rebound = command(
        114,
        EventKind.ASSIGNMENT_REBOUND,
        coordinator_actor,
        assignment=rebound_binding,
        payload={"reason": "fresh owner binding"},
    )
    assert service.append(rebound, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    with store.transaction() as tx:
        worker_owner = tx.read_owner(WAVE, WORKER)
        assert worker_owner is not None
    stale_expected = ExpectedOwnerBindings(
        WAVE,
        WORKER,
        WORKER_THREAD,
        WORKER_GENERATION,
        worker_owner.capability_snapshot_id,
        worker_owner.policy_revision,
        worker_owner.record_version,
        assignment=binding.ref,
    )
    stale_reserve = ReserveClaim(
        stale_expected,
        TARGET,
        REPOSITORY,
        205,
        "stale-revision",
        binding.ref,
        DIGEST_B,
    )
    worktree = WorktreeEvidence(TARGET, REPOSITORY, False, None, 300, "fixture")
    stale_claim = command(
        130,
        EventKind.CLAIM_RESERVED,
        worker_actor,
        payload={
            "claim_id": str(ClaimId(UUID(int=201))),
            "file_lane_digest": DIGEST_B,
            "worktree_evidence_digest": digest_bytes(canonical_json_bytes(worktree)),
        },
        effect=canonical_record(intent=stale_reserve, worktree=worktree),
    )
    stale_claim_receipt = service.append_claim_change(
        stale_claim,
        LocalIdentityContext(WORKER_THREAD),
        stale_reserve,
        worktree,
    )
    assert stale_claim_receipt.disposition is EventDisposition.REJECTED
    assert stale_claim_receipt.reason == "stale_assignment"
    with store.transaction() as tx:
        assert tx.read_claim(ClaimId(UUID(int=201))) is None

    rebound_read = command(
        115,
        EventKind.ASSIGNMENT_READ,
        worker_actor,
        assignment=rebound_binding,
        correlation=114,
    )
    assert service.append(rebound_read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    rebound_accept = command(
        116,
        EventKind.ASSIGNMENT_ACCEPTED,
        worker_actor,
        assignment=rebound_binding,
        correlation=114,
        causation=115,
    )
    assert service.append(rebound_accept, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    current_expected = replace(stale_expected, assignment=rebound_binding.ref)
    current_reserve = ReserveClaim(
        current_expected,
        TARGET,
        REPOSITORY,
        205,
        "current-revision",
        rebound_binding.ref,
        DIGEST_B,
    )
    current_claim = replace(
        stale_claim,
        event_id=event_id(131),
        effect=canonical_record(intent=current_reserve, worktree=worktree),
    )
    assert (
        service.append_claim_change(
            current_claim,
            LocalIdentityContext(WORKER_THREAD),
            current_reserve,
            worktree,
        ).disposition
        is EventDisposition.APPLIED
    )
    with store.transaction() as tx:
        held_projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        rebound_assignment = tx.read_assignment(rebound_binding.ref)
        assert held_projection is not None
        assert held_projection["state"] == AssignmentState.HELD.value
        assert held_projection["brief_state"] == AssignmentState.ACCEPTED.value
        assert rebound_assignment is not None and rebound_assignment.acknowledged

    stale_gate = command(
        117,
        EventKind.GATE_APPROVED,
        coordinator_actor,
        assignment=pr_binding,
        payload={"gate_id": "stale-gate", "verdict": "approved"},
    )
    stale_gate_receipt = service.append(stale_gate, LocalIdentityContext(COORDINATOR_THREAD))
    assert stale_gate_receipt.disposition is EventDisposition.REJECTED
    assert stale_gate_receipt.reason == "assignment_binding_mismatch"
    fresh_gate = command(
        118,
        EventKind.GATE_APPROVED,
        coordinator_actor,
        assignment=rebound_binding,
        payload={"gate_id": "gate-v2", "verdict": "approved"},
    )
    assert service.append(fresh_gate, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED

    changed_head_binding = replace(rebound_binding, pr_head="3" * 40)
    changed_head_release = command(
        119,
        EventKind.ASSIGNMENT_RELEASED,
        coordinator_actor,
        assignment=changed_head_binding,
        payload={"conditions": conditions, "previous_state": "pr_open", "reason": "wrong head"},
    )
    changed_head_receipt = service.append(
        changed_head_release,
        LocalIdentityContext(COORDINATOR_THREAD),
    )
    assert changed_head_receipt.disposition is EventDisposition.REJECTED
    assert changed_head_receipt.reason == "assignment_binding_mismatch"
    release = command(
        120,
        EventKind.ASSIGNMENT_RELEASED,
        coordinator_actor,
        assignment=rebound_binding,
        payload={"conditions": conditions, "previous_state": "pr_open", "reason": "conditions met"},
    )
    release_receipt = service.append(release, LocalIdentityContext(COORDINATOR_THREAD))
    assert release_receipt.disposition is EventDisposition.APPLIED, release_receipt.reason

    clearance = command(121, EventKind.MERGE_CLEARED, coordinator_actor, assignment=rebound_binding)
    assert service.append(clearance, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    observed = command(
        122,
        EventKind.EXTERNAL_MERGE_OBSERVED,
        coordinator_actor,
        assignment=rebound_binding,
        payload={"merge_commit": "4" * 40},
    )
    assert service.append(observed, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.RECONCILED
    completed = command(
        123,
        EventKind.ASSIGNMENT_COMPLETED,
        coordinator_actor,
        assignment=rebound_binding,
        correlation=122,
        payload={"merge_commit": "4" * 40},
    )
    assert service.append(completed, LocalIdentityContext(COORDINATOR_THREAD)).disposition is EventDisposition.APPLIED
    with store.transaction() as tx:
        final_projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        assert final_projection is not None
        assert final_projection["state"] == AssignmentState.COMPLETED.value
    verify_wave(store, WAVE)


@pytest.mark.parametrize("restart", [False, True])
def test_scan_response_loss_recovers_original_page_without_ack_or_cursor_regression(
    tmp_path: Path,
    restart: bool,
) -> None:
    store = create_store(tmp_path)
    probe = FakeProbe()
    service = EventService(store, process_probe=probe, ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker")
    bootstrap_and_register(service, snapshot("coordinator"), worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    queued = command(
        4,
        EventKind.ASSIGNMENT_QUEUED,
        actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION),
        assignment=binding,
    )
    service.append(queued, LocalIdentityContext(COORDINATOR_THREAD))
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    scan = command(
        5, EventKind.CURSOR_ADVANCED, worker_actor, payload={"cursor_highest_contiguous": 4, "cursor_sparse": ()}
    )
    original = service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD))
    # Simulate discarding the response. A later scan must not change the retry's page.
    later = command(
        6, EventKind.CURSOR_ADVANCED, worker_actor, payload={"cursor_highest_contiguous": 5, "cursor_sparse": ()}
    )
    service.scan_and_advance(later, LocalIdentityContext(WORKER_THREAD))
    if restart:
        store = SQLiteWaveStore.open(StoreConfig(tmp_path / "wave.sqlite3", busy_timeout_ms=100))
        rebuild_projections(store, WAVE)
        service = EventService(store, process_probe=probe, ids=FakeIds(), clock=FakeClock())
    before = verify_wave(store, WAVE)
    assert service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD)) == original
    assert service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD)) == original
    assert verify_wave(store, WAVE) == before
    with store.transaction() as tx:
        cursor = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
        assert cursor is not None and cursor.highest_contiguous == 5
        assignment = tx.read_assignment(binding.ref)
        assert assignment is not None and not assignment.acknowledged
        projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        assert projection is not None and projection["state"] == "queued"


def test_scan_retry_preserves_historical_access_but_not_new_write_authority(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    probe = FakeProbe()
    service = EventService(store, process_probe=probe, ids=FakeIds(), clock=FakeClock())
    bootstrap_and_register(service, snapshot("coordinator"), snapshot("worker"))
    scan = command(
        4,
        EventKind.CURSOR_ADVANCED,
        actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
        payload={"cursor_highest_contiguous": 3, "cursor_sparse": ()},
    )
    original = service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD))
    # The same registered thread is now a different process: history is readable,
    # but it cannot write using the old process generation.
    probe.processes[WORKER_THREAD] = replace(WORKER_PROCESS, start_ticks=999)
    assert service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD)) == original
    fresh = replace(
        scan,
        event_id=event_id(5),
        payload=EventPayload.from_mapping({"cursor_highest_contiguous": 4, "cursor_sparse": ()}),
    )
    refused, page = service.scan_and_advance(fresh, LocalIdentityContext(WORKER_THREAD))
    assert refused.disposition == EventDisposition.REJECTED
    assert not page.events
    assert service.scan_and_advance(fresh, LocalIdentityContext(WORKER_THREAD))[0] == refused
    conflict = replace(scan, payload=fresh.payload)
    refused, page = service.scan_and_advance(conflict, LocalIdentityContext(WORKER_THREAD))
    assert refused.reason == "event_id_payload_conflict" and not page.events
    outsider = ThreadId(UUID(int=999))
    probe.processes[outsider] = replace(WORKER_PROCESS, pid=4999)
    with pytest.raises(EventAuthorizationError, match="historical receipt"):
        service.scan_and_advance(scan, LocalIdentityContext(outsider))
    with store.transaction() as tx:
        cursor = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
        assert cursor is not None and cursor.highest_contiguous == 3


@pytest.mark.parametrize("start", [None, 0, 1, True, "0"])
def test_scan_recovery_validates_metadata_and_supports_legacy_journals(tmp_path: Path, start: object) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    bootstrap_and_register(service, snapshot("coordinator"), snapshot("worker"))
    scan = command(
        4,
        EventKind.CURSOR_ADVANCED,
        actor(WORKER, WORKER_THREAD, WORKER_GENERATION),
        payload={"cursor_highest_contiguous": 3, "cursor_sparse": ()},
    )
    cursor = CursorState(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION, highest_contiguous=3)
    facts: dict[str, object] = {"cursor": cursor}
    if start is not None:
        facts["scan_after_sequence"] = start
    # Construct old-format or semantically invalid, correctly hashed journal records.
    with store.transaction() as tx:
        original_events = tx.read_event_page(WAVE)
        receipt = tx.append_event(
            scan,
            disposition=EventDisposition.APPLIED,
            reason=None,
            validation_facts=canonical_record(**facts),
            committed_at=NOW,
        )
        assert receipt.sequence is not None
        tx.put_cursor(cursor, receipt.sequence)
        tx.commit()
    if start is None or (type(start) is int and start == 0):
        recovered_receipt, page = service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD))
        assert recovered_receipt == receipt and page.events == original_events and page.cursor == cursor
        rebuild_projections(store, WAVE)
        assert verify_wave(store, WAVE).event_count == 4
    else:
        with pytest.raises(CorruptStore, match="scan recovery"):
            service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD))
        with pytest.raises(CorruptStore):
            rebuild_projections(store, WAVE)


def test_recovered_scan_with_sparse_preceding_cursor_and_corrupt_page(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker")
    bootstrap_and_register(service, snapshot("coordinator"), worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    queued = command(4, EventKind.ASSIGNMENT_QUEUED,
                     actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION), assignment=binding)
    service.append(queued, LocalIdentityContext(COORDINATOR_THREAD))
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    read = command(5, EventKind.ASSIGNMENT_READ, worker_actor, assignment=binding, correlation=4)
    service.append(read, LocalIdentityContext(WORKER_THREAD))
    # Closing gaps 1..3 also advances through the already-read sequences 4 and 5.
    scan = command(6, EventKind.CURSOR_ADVANCED, worker_actor,
                   payload={"cursor_highest_contiguous": 3, "cursor_sparse": ()})
    original = service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD))
    assert original[1].cursor.highest_contiguous == 5
    assert len(original[1].events) == 3
    rebuild_projections(store, WAVE)
    assert service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD)) == original
    # A correct cached receipt must not hide corruption in the original page.
    with store.transaction() as tx:
        tx._connection.execute("UPDATE events SET command_bytes=? WHERE wave_id=? AND sequence=2",
                               (b"{}", str(WAVE)))
        tx.commit()
    with pytest.raises(CorruptStore, match="verification"):
        service.scan_and_advance(scan, LocalIdentityContext(WORKER_THREAD))


@pytest.mark.parametrize("kind", [EventKind.ASSIGNMENT_READ, EventKind.ASSIGNMENT_ACCEPTED])
@pytest.mark.parametrize(
    ("mismatch", "reason"),
    [
        ("actor_generation", "stale_owner_generation"),
        ("worker_generation", "assigned_worker_authority_required"),
        ("coordinator_generation", "stale_coordinator_generation"),
        ("policy", "stale_policy"),
        ("wave", None),
    ],
)
def test_acknowledgement_binding_refusals_preserve_durable_state(
    tmp_path: Path, kind: EventKind, mismatch: str, reason: str | None,
) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker")
    bootstrap_and_register(service, snapshot("coordinator"), worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    queue = command(4, EventKind.ASSIGNMENT_QUEUED,
                    actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION), assignment=binding)
    service.append(queue, LocalIdentityContext(COORDINATOR_THREAD))
    if kind == EventKind.ASSIGNMENT_ACCEPTED:
        read = command(5, EventKind.ASSIGNMENT_READ, worker_actor, assignment=binding, correlation=4)
        assert service.append(read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED

    with store.transaction() as tx:
        before_projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        before_assignment = tx.read_assignment(binding.ref)
        before_cursor = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
    before_report = verify_wave(store, WAVE)
    bad_binding = binding
    bad_actor = worker_actor
    if mismatch == "actor_generation":
        bad_actor = replace(worker_actor, generation_id=OwnerGenerationId(UUID(int=99)))
    elif mismatch == "worker_generation":
        bad_binding = replace(binding, worker_generation=OwnerGenerationId(UUID(int=99)))
    elif mismatch == "coordinator_generation":
        bad_binding = replace(binding, coordinator_generation=CoordinatorGenerationId(UUID(int=98)))
    elif mismatch == "policy":
        bad_binding = replace(binding, policy_revision=2)
    acknowledgement = command(6, kind, bad_actor, assignment=bad_binding, correlation=4)
    if mismatch == "wave":
        acknowledgement = replace(acknowledgement, wave_id=WaveId("unregistered-wave"))
        with pytest.raises(EventAuthorizationError, match="historical receipt"):
            service.append(acknowledgement, LocalIdentityContext(WORKER_THREAD))
        assert verify_wave(store, WAVE) == before_report
        with store.transaction() as tx:
            assert tx.lookup_event(acknowledgement.wave_id, acknowledgement.event_id) is None
    else:
        receipt = service.append(acknowledgement, LocalIdentityContext(WORKER_THREAD))
        assert receipt.disposition is EventDisposition.REJECTED
        assert receipt.reason == reason
        assert service.append(acknowledgement, LocalIdentityContext(WORKER_THREAD)) == receipt
        assert verify_wave(store, WAVE).event_count == before_report.event_count + 1

    store = SQLiteWaveStore.open(store.config)
    rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        assert tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id)) == before_projection
        assert tx.read_assignment(binding.ref) == before_assignment
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == before_cursor
    verify_wave(store, WAVE)


def test_out_of_order_acceptance_retry_stays_rejected_after_read_and_rebuild(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker")
    bootstrap_and_register(service, snapshot("coordinator"), worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    queue = command(4, EventKind.ASSIGNMENT_QUEUED,
                    actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION), assignment=binding)
    service.append(queue, LocalIdentityContext(COORDINATOR_THREAD))
    early = command(5, EventKind.ASSIGNMENT_ACCEPTED, worker_actor, assignment=binding, correlation=4)
    refused = service.append(early, LocalIdentityContext(WORKER_THREAD))
    assert refused.disposition is EventDisposition.REJECTED
    assert refused.reason == "accept_requires_read"
    with store.transaction() as tx:
        assignment = tx.read_assignment(binding.ref)
        projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        assert assignment is not None and not assignment.acknowledged
        assert projection is not None and projection["state"] == "queued"
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) is None

    read = command(6, EventKind.ASSIGNMENT_READ, worker_actor, assignment=binding, correlation=4)
    assert service.append(read, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.APPLIED
    before_retry = verify_wave(store, WAVE)
    with store.transaction() as tx:
        read_cursor = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
        read_projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        read_assignment = tx.read_assignment(binding.ref)
    assert service.append(early, LocalIdentityContext(WORKER_THREAD)) == refused
    assert verify_wave(store, WAVE) == before_retry
    store = SQLiteWaveStore.open(store.config)
    rebuild_projections(store, WAVE)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    assert service.append(early, LocalIdentityContext(WORKER_THREAD)) == refused
    assert verify_wave(store, WAVE) == before_retry
    with store.transaction() as tx:
        assert tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id)) == read_projection
        assert tx.read_assignment(binding.ref) == read_assignment
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == read_cursor

    fresh = replace(early, event_id=event_id(7))
    accepted = service.append(fresh, LocalIdentityContext(WORKER_THREAD))
    assert accepted.disposition is EventDisposition.APPLIED
    assert service.append(fresh, LocalIdentityContext(WORKER_THREAD)) == accepted
    assert service.append(early, LocalIdentityContext(WORKER_THREAD)) == refused
    assert verify_wave(store, WAVE).event_count == before_retry.event_count + 1
    rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        assignment = tx.read_assignment(binding.ref)
        projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        assert assignment is not None and assignment.acknowledged
        assert projection is not None and projection["state"] == "accepted"
        assert projection["last_event_id"] == str(fresh.event_id)
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == read_cursor


@pytest.mark.parametrize("kind", [EventKind.ASSIGNMENT_READ, EventKind.ASSIGNMENT_ACCEPTED])
def test_delayed_acknowledgement_from_replaced_worker_generation_is_fenced(
    tmp_path: Path, kind: EventKind,
) -> None:
    class ReplacementProbe(FakeProbe):
        def observe_recorded(self, process: ProcessCoordinates) -> ProcessCoordinates:
            if process == WORKER_PROCESS:
                return self.processes[WORKER_THREAD]
            return process

    probe = ReplacementProbe()
    ids = FakeIds()
    replacement_generation = OwnerGenerationId(UUID(int=103))
    ids.owner_ids = iter((COORDINATOR_GENERATION, WORKER_GENERATION, replacement_generation))
    store = create_store(tmp_path)
    service = EventService(store, process_probe=probe, ids=ids, clock=FakeClock())
    worker_snapshot = snapshot("worker")
    bootstrap_and_register(service, snapshot("coordinator"), worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    old_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    service.append(command(4, EventKind.ASSIGNMENT_QUEUED,
                           actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION), assignment=binding),
                   LocalIdentityContext(COORDINATOR_THREAD))
    if kind == EventKind.ASSIGNMENT_ACCEPTED:
        service.append(command(5, EventKind.ASSIGNMENT_READ, old_actor, assignment=binding, correlation=4),
                       LocalIdentityContext(WORKER_THREAD))
    delayed = command(7, kind, old_actor, assignment=binding, correlation=4)
    with store.transaction() as tx:
        old_owner = tx.read_owner(WAVE, WORKER)
        before_assignment = tx.read_assignment(binding.ref)
        before_projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        before_cursor = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
    assert old_owner is not None
    # Reusing a PID with a different start tick proves the recorded process generation is dead.
    probe.processes[WORKER_THREAD] = replace(WORKER_PROCESS, start_ticks=999)
    intent = ReplaceDeadOwner(WAVE, WORKER, old_owner.record_version, WORKER_GENERATION,
                              worker_snapshot.snapshot_id, 1)
    new_actor = actor(WORKER, WORKER_THREAD, replacement_generation)
    replacement = command(6, EventKind.OWNER_REPLACED, new_actor,
                          effect=canonical_record(intent=intent, snapshot=worker_snapshot))
    assert service.append_owner_change(replacement, LocalIdentityContext(WORKER_THREAD),
                                       intent, worker_snapshot).disposition is EventDisposition.APPLIED
    refused = service.append(delayed, LocalIdentityContext(WORKER_THREAD))
    assert refused.disposition is EventDisposition.REJECTED and refused.reason == "stale_owner_generation"
    # Updating only the sender still cannot accept the old assignment generation.
    wrong_assignment = replace(delayed, event_id=event_id(8), actor=new_actor)
    refused_binding = service.append(wrong_assignment, LocalIdentityContext(WORKER_THREAD))
    assert refused_binding.disposition is EventDisposition.REJECTED
    assert refused_binding.reason == "assigned_worker_authority_required"
    store = SQLiteWaveStore.open(store.config)
    rebuild_projections(store, WAVE)
    service = EventService(store, process_probe=probe, ids=ids, clock=FakeClock())
    before_retry = verify_wave(store, WAVE)
    assert service.append(delayed, LocalIdentityContext(WORKER_THREAD)) == refused
    assert verify_wave(store, WAVE) == before_retry
    with store.transaction() as tx:
        owner = tx.read_owner(WAVE, WORKER)
        assert owner is not None and owner.generation_id == replacement_generation
        assert tx.read_assignment(binding.ref) == before_assignment
        assert tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id)) == before_projection
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == before_cursor
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, replacement_generation) is None


@pytest.mark.parametrize("invalid", ["verdict", "provenance", "assignment"])
def test_malformed_gate_cannot_turn_prose_into_authority(tmp_path: Path, invalid: str) -> None:
    store = create_store(tmp_path)
    service = EventService(store, process_probe=FakeProbe(), ids=FakeIds(), clock=FakeClock())
    worker_snapshot = snapshot("worker")
    bootstrap_and_register(service, snapshot("coordinator"), worker_snapshot)
    binding = assignment_binding(worker_snapshot)
    coordinator_actor = actor(COORDINATOR, COORDINATOR_THREAD, COORDINATOR_GENERATION)
    worker_actor = actor(WORKER, WORKER_THREAD, WORKER_GENERATION)
    queue = command(4, EventKind.ASSIGNMENT_QUEUED, coordinator_actor, assignment=binding)
    service.append(queue, LocalIdentityContext(COORDINATOR_THREAD))
    for value, kind in ((5, EventKind.ASSIGNMENT_READ), (6, EventKind.ASSIGNMENT_ACCEPTED)):
        service.append(command(value, kind, worker_actor, assignment=binding, correlation=4),
                       LocalIdentityContext(WORKER_THREAD))
    with store.transaction() as tx:
        before_projection = tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id))
        before_assignment = tx.read_assignment(binding.ref)
        before_cursor = tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION)
    before_report = verify_wave(store, WAVE)
    gate = command(7, EventKind.GATE_APPROVED, coordinator_actor, assignment=binding,
                   payload={"gate_id": "review", "verdict": "approved"})
    raw = json.loads(gate.canonical_bytes())
    if invalid == "verdict":
        raw["payload"]["verdict"] = "rejected"
    elif invalid == "provenance":
        raw["provenance"]["classification"] = "payload_only"
    else:
        raw["assignment"] = None
    encoded = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(EventValidationError):
        service.append(command_from_bytes(encoded), LocalIdentityContext(COORDINATOR_THREAD))
    assert verify_wave(store, WAVE) == before_report

    prose = command(8, EventKind.PROSE_MESSAGE, worker_actor,
                    payload={"text": encoded.decode()})
    prose = replace(prose, provenance=ProvenanceEvidence(ProvenanceClass.PAYLOAD_ONLY, "body"))
    assert service.append(prose, LocalIdentityContext(WORKER_THREAD)).disposition is EventDisposition.OBSERVED
    attempted = command(9, EventKind.ASSIGNMENT_IMPLEMENTING, worker_actor, assignment=binding, correlation=8)
    refused = service.append(attempted, LocalIdentityContext(WORKER_THREAD))
    assert refused.disposition is EventDisposition.REJECTED and refused.reason == "correlation_kind_mismatch"
    rebuild_projections(store, WAVE)
    with store.transaction() as tx:
        assert tx.get_projection(WAVE, "assignment", str(binding.ref.assignment_id)) == before_projection
        assert tx.read_assignment(binding.ref) == before_assignment
        assert tx.read_cursor(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION) == before_cursor
    verify_wave(store, WAVE)
