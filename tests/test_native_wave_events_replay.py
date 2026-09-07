"""Durable event, acknowledgement, projection, and replay witnesses for #205."""

from __future__ import annotations

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
    ProvenanceClass,
    ProvenanceEvidence,
    canonical_json_bytes,
    canonical_record,
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
    CapabilityRequirements,
    CapabilitySnapshot,
    ClaimId,
    CoordinatorGenerationId,
    ExpectedOwnerBindings,
    GrantId,
    GrantPurpose,
    LocalIdentityContext,
    OwnerGenerationId,
    PhysicalTargetKey,
    ProcessCoordinates,
    ProcessObservation,
    RepositoryKey,
    ReserveClaim,
    RoleId,
    ThreadId,
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


def test_cursor_merge_is_sparse_and_bounded_after_large_prefix() -> None:
    current = CursorState(WAVE, WORKER, WORKER_THREAD, WORKER_GENERATION, highest_contiguous=50_000)
    newer = advance_cursor(current, observed_sequences=(50_002,), scanned_through=50_002)
    merged = merge_cursor(current, newer)
    assert merged.highest_contiguous == 50_000
    assert merged.sparse_sequences == (50_002,)
    assert merged.gaps == (50_001,)


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

    report = verify_wave(store, WAVE)
    assert report.event_count == 7
    with store.transaction() as tx:
        kinds = {
            row[0]
            for row in tx._connection.execute(
                "SELECT projection_kind FROM projections WHERE wave_id=?", (str(WAVE),)
            )
        }
        tx._connection.execute("DELETE FROM projections WHERE wave_id=?", (str(WAVE),))
        tx._connection.execute("DELETE FROM cursors WHERE wave_id=?", (str(WAVE),))
        tx.commit()
    assert {"assignment", "capability", "claim", "grant", "owner", "wave"} <= kinds
    rebuilt = rebuild_projections(store, WAVE)
    assert rebuilt.event_count == 7
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
        assert tx.read_owner(WAVE, COORDINATOR).capability_snapshot_id == coordinator_snapshot.snapshot_id


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
