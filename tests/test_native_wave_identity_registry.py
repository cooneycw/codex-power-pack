"""Offline identity/ownership negative corpus for issue #200."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest

from lib.native_wave.claims import LocalWorktreeEvidenceProbe, prepare_claim_change, prepare_claim_reconciliation
from lib.native_wave.identity import LinuxHostProcessProbe, accept_process_evidence
from lib.native_wave.registry import (
    check_liveness,
    check_owner,
    evaluate_assignment_capabilities,
    prepare_owner_change,
    provision_recovery_delegation,
    provision_wave_bootstrap,
)
from lib.native_wave.types import (
    AcceptedProcessEvidence,
    AssignmentRef,
    AuthorizedTakeover,
    BootstrapGrantSpec,
    BootstrapRequest,
    CapabilityEvidence,
    CapabilityField,
    CapabilityFieldRequirement,
    CapabilityRequirements,
    CapabilitySnapshot,
    CapabilitySnapshotId,
    ClaimId,
    ClaimState,
    CoordinatorGenerationId,
    DurableRecordRef,
    ExpectedOwnerBindings,
    FinalizeClaim,
    GrantId,
    GrantPurpose,
    Liveness,
    LocalIdentityContext,
    MarkReconciliationRequired,
    ObservationFailure,
    OwnerGenerationId,
    OwnershipRefusal,
    PhysicalTargetKey,
    ProcessCoordinates,
    ProcessObservation,
    ProcessObservationUnavailable,
    RebindClaimIntent,
    RebriefOwner,
    RecoverCoordinator,
    RecoveryDelegationRequest,
    RefusalCode,
    RegisterOwner,
    ReleaseClaim,
    ReplaceDeadOwner,
    RepositoryKey,
    ReserveClaim,
    RoleId,
    RoleOwner,
    SerializationConflict,
    StoredAssignment,
    StoredGrant,
    StoredReconciliation,
    ThreadId,
    TransactionClosedError,
    TransactionMismatchError,
    UpdateCapability,
    WaveId,
    WorktreeClaim,
    WorktreeEvidence,
    WorktreeEvidenceUnavailable,
)

NOW = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)
WAVE = WaveId("cxpp-completion")
WORKER = RoleId("worker-B")
COORDINATOR = RoleId("coordinator")
THREAD = ThreadId(UUID(int=1))
OTHER_THREAD = ThreadId(UUID(int=2))
GENERATION = OwnerGenerationId(UUID(int=3))
COORDINATOR_GENERATION = CoordinatorGenerationId(UUID(int=4))
BOOT = UUID(int=5)
PROCESS = ProcessCoordinates("0123456789abcdef", BOOT, 4200, 900)
OTHER_PROCESS = ProcessCoordinates("0123456789abcdef", BOOT, 4201, 901)
ASSIGNMENT_REF = AssignmentRef(UUID(int=6), 2, "sha256:" + "a" * 64)
RECORD_REF = DurableRecordRef(UUID(int=7), "sha256:" + "b" * 64)
TARGET = PhysicalTargetKey("0123456789abcdef", "/worktrees/issue-200")
REPOSITORY = RepositoryKey("0123456789abcdef", "/repos/codex-power-pack/.git")


def snapshot(
    *,
    model: str = "gpt-5",
    tools: tuple[str, ...] = ("shell", "mailbox"),
    web_mode: str = "disabled",
    captured_at: datetime = NOW,
) -> CapabilitySnapshot:
    return CapabilitySnapshot.create(
        schema_version=1,
        cli_version="1.0",
        runtime_version="python-3.11",
        model=model,
        reasoning_effort="high",
        sandbox_mode="danger-full-access",
        approval_policy="never",
        workspace_roots=("/repos",),
        additional_writable_roots=("/run/user/1000",),
        tool_families=tools,
        required_apps=(),
        required_plugins=("flow",),
        delivery_mechanisms=("mailbox",),
        wake_mechanisms=("watch",),
        web_mode=web_mode,
        captured_at=captured_at,
        evidence=(CapabilityEvidence(CapabilityField.MODEL, "runtime", "native-context"),),
    )


def requirements(*items: tuple[CapabilityField, tuple[str, ...]]) -> CapabilityRequirements:
    return CapabilityRequirements.create(
        tuple(CapabilityFieldRequirement(field, tuple(sorted(values))) for field, values in items)
    )


def observation(
    thread: ThreadId = THREAD,
    process: ProcessCoordinates = PROCESS,
    observed: int = 100,
) -> ProcessObservation:
    return ProcessObservation(thread, process, observed, "fixture-native-process")


def evidence(tx_id: UUID, thread: ThreadId = THREAD, process: ProcessCoordinates = PROCESS) -> AcceptedProcessEvidence:
    return AcceptedProcessEvidence(tx_id, observation(thread, process), 101)


class FakeProbe:
    def __init__(self) -> None:
        self.self_result: ProcessObservation | ProcessObservationUnavailable = observation()
        self.revalidated: ProcessObservation | ProcessObservationUnavailable = observation(observed=110)
        self.recorded: ProcessCoordinates | ProcessObservationUnavailable = PROCESS
        self.recorded_calls = 0
        self.assert_active: FakeTransaction | None = None

    def observe_self(self, context: LocalIdentityContext):
        del context
        return self.self_result

    def revalidate(self, candidate: ProcessObservation):
        del candidate
        return self.revalidated

    def observe_recorded(self, process: ProcessCoordinates):
        del process
        self.recorded_calls += 1
        if self.assert_active is not None:
            assert self.assert_active.is_active
        return self.recorded


class FakeClock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic_ns(self) -> int:
        return 200


class FakeIds:
    def __init__(self) -> None:
        self.owner_value = 100
        self.claim_value = 200

    def new_owner_generation_id(self) -> OwnerGenerationId:
        self.owner_value += 1
        return OwnerGenerationId(UUID(int=self.owner_value))

    def new_claim_id(self) -> ClaimId:
        self.claim_value += 1
        return ClaimId(UUID(int=self.claim_value))


class FakeTransaction:
    def __init__(self) -> None:
        self.transaction_id = UUID(int=300)
        self.is_active = True
        self.base_store_revision = 10
        self.policy_revision = 2
        self.owners: dict[tuple[WaveId, RoleId], RoleOwner] = {}
        self.capabilities: dict[CapabilitySnapshotId, CapabilitySnapshot] = {}
        self.grants: dict[GrantId, StoredGrant] = {}
        self.assignments: dict[AssignmentRef, StoredAssignment] = {}
        self.reconciliations: dict[DurableRecordRef, StoredReconciliation] = {}
        self.claims: dict[ClaimId, WorktreeClaim] = {}
        self.staged_owners = []
        self.staged_claims = []
        self.assignment_reads = 0

    def read_owner(self, wave_id: WaveId, role_id: RoleId):
        return self.owners.get((wave_id, role_id))

    def read_policy_revision(self, wave_id: WaveId):
        return self.policy_revision if wave_id == WAVE else 0

    def read_capability(self, snapshot_id: CapabilitySnapshotId):
        return self.capabilities.get(snapshot_id)

    def read_preexisting_grant(self, grant_id: GrantId):
        return self.grants.get(grant_id)

    def read_assignment(self, assignment: AssignmentRef):
        self.assignment_reads += 1
        return self.assignments.get(assignment)

    def read_reconciliation(self, record: DurableRecordRef):
        return self.reconciliations.get(record)

    def read_claim(self, claim_id: ClaimId):
        return self.claims.get(claim_id)

    def read_active_claim_for_target(self, target: PhysicalTargetKey):
        return next(
            (
                claim
                for claim in self.claims.values()
                if claim.target == target and claim.state is not ClaimState.RELEASED
            ),
            None,
        )

    def stage_owner_change(self, change):
        if not self.is_active:
            raise TransactionClosedError("cannot stage on closed fake transaction")
        if change.transaction_id != self.transaction_id:
            raise TransactionMismatchError("prepared owner change belongs to another fake transaction")
        self.staged_owners.append(change)

    def stage_claim_change(self, change):
        if not self.is_active:
            raise TransactionClosedError("cannot stage on closed fake transaction")
        if change.transaction_id != self.transaction_id:
            raise TransactionMismatchError("prepared claim change belongs to another fake transaction")
        self.staged_claims.append(change)

    def fork(self, transaction_id: UUID) -> FakeTransaction:
        other = FakeTransaction()
        other.transaction_id = transaction_id
        other.base_store_revision = self.base_store_revision
        other.policy_revision = self.policy_revision
        other.owners = self.owners
        other.capabilities = self.capabilities
        other.grants = self.grants
        other.assignments = self.assignments
        other.reconciliations = self.reconciliations
        other.claims = self.claims
        return other

    def commit(self) -> None:
        if not self.is_active:
            raise TransactionClosedError("fake transaction already closed")
        # Validate the complete batch before changing owners or grants. This is
        # a deterministic CAS witness, not a second product store.
        for change in self.staged_owners:
            key = (change.replacement.wave_id, change.replacement.role_id)
            current = self.owners.get(key)
            if change.expected_owner_version is None:
                if current is not None:
                    raise SerializationConflict("owner appeared before commit")
            elif current is None or current.record_version != change.expected_owner_version:
                raise SerializationConflict("owner CAS lost before commit")
            if change.consumed_grant_id is not None:
                current_grant = self.grants.get(change.consumed_grant_id)
                if current_grant is None or current_grant.consumed:
                    raise SerializationConflict("grant CAS lost before commit")
        for change in self.staged_owners:
            key = (change.replacement.wave_id, change.replacement.role_id)
            self.owners[key] = change.replacement
            if change.consumed_grant_id is not None:
                self.grants[change.consumed_grant_id] = dataclasses.replace(
                    self.grants[change.consumed_grant_id], consumed=True
                )
        self.is_active = False


class FakeBootstrapTransaction:
    def __init__(self, entry: Literal["bootstrap", "recovery"] = "bootstrap") -> None:
        self.transaction_id = UUID(int=400)
        self.is_active = True
        self.base_store_revision = 10
        self.administrative_entry = entry
        self.exists = False
        self.owners: dict[tuple[WaveId, RoleId], RoleOwner] = {}
        self.staged = []

    def wave_exists(self, wave_id: WaveId) -> bool:
        assert wave_id == WAVE
        return self.exists

    def read_owner(self, wave_id: WaveId, role_id: RoleId):
        return self.owners.get((wave_id, role_id))

    def stage_bootstrap(self, change):
        self.staged.append(change)

    def stage_recovery_delegation(self, change):
        self.staged.append(change)


def owner(
    *,
    role: RoleId = WORKER,
    thread: ThreadId = THREAD,
    process: ProcessCoordinates = PROCESS,
    generation: OwnerGenerationId = GENERATION,
    capability: CapabilitySnapshotId | None = None,
    version: int = 3,
) -> RoleOwner:
    return RoleOwner(WAVE, role, thread, generation, process, capability or snapshot().snapshot_id, 2, version)


def assignment(
    *,
    capability: CapabilitySnapshotId,
    required: CapabilityRequirements | None = None,
    generation: OwnerGenerationId = GENERATION,
    acknowledged: bool = True,
) -> StoredAssignment:
    return StoredAssignment(
        ASSIGNMENT_REF,
        WAVE,
        WORKER,
        generation,
        capability,
        required or requirements((CapabilityField.TOOL_FAMILIES, ("shell",))),
        (),
        2,
        acknowledged,
    )


def expected(current: RoleOwner, *, assignment_ref: AssignmentRef | None = None, claim_id: ClaimId | None = None):
    return ExpectedOwnerBindings(
        current.wave_id,
        current.role_id,
        current.thread_id,
        current.generation_id,
        current.capability_snapshot_id,
        current.policy_revision,
        current.record_version,
        assignment_ref,
        claim_id,
    )


def worktree(*, exists: bool = False, branch: str | None = None, repository: RepositoryKey = REPOSITORY):
    return WorktreeEvidence(TARGET, repository, exists, branch, 200, "fixture-filesystem-observation")


def grant(
    grant_id: GrantId,
    *,
    purpose: GrantPurpose = GrantPurpose.REGISTER,
    created_revision: int = 9,
    consumed: bool = False,
    authorized_by: CoordinatorGenerationId | None = None,
    target_generation: OwnerGenerationId | None = None,
    target_version: int | None = None,
    role: RoleId = WORKER,
    thread: ThreadId = THREAD,
) -> StoredGrant:
    return StoredGrant(
        grant_id,
        WAVE,
        role,
        thread,
        purpose,
        2,
        created_revision,
        NOW - timedelta(minutes=1),
        NOW + timedelta(minutes=5),
        consumed,
        authorized_by,
        target_generation,
        target_version,
    )


def assert_refusal(result: object, code: RefusalCode) -> OwnershipRefusal:
    assert isinstance(result, OwnershipRefusal)
    assert result.code is code
    return result


def prepared_owner_tx(snapshot_value: CapabilitySnapshot | None = None):
    tx = FakeTransaction()
    current_snapshot = snapshot_value or snapshot()
    current = owner(capability=current_snapshot.snapshot_id)
    tx.capabilities[current_snapshot.snapshot_id] = current_snapshot
    tx.owners[(WAVE, WORKER)] = current
    return tx, current_snapshot, current


def test_identifier_and_snapshot_values_are_deeply_immutable() -> None:
    value = WaveId("wave-1")
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        value.value = "wave-2"  # type: ignore[misc]
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        value.extra = "mutable"  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        PhysicalTargetKey("host", "relative/path")
    with pytest.raises(ValueError):
        CapabilitySnapshotId("not-a-digest")
    with pytest.raises(ValueError):
        PhysicalTargetKey("host", "//worktrees/issue-200")
    with pytest.raises(ValueError):
        RepositoryKey("host", "/repos/bad\0path")


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: AssignmentRef(UUID(int=800), True, "sha256:" + "8" * 64),
        lambda: ProcessCoordinates("host", BOOT, True, 1),
        lambda: ProcessCoordinates("host", BOOT, 2, 1.5),
        lambda: dataclasses.replace(owner(), record_version=True),
        lambda: CapabilitySnapshot.create(
            schema_version=True,
            cli_version="1",
            runtime_version="python",
            model="gpt",
            reasoning_effort="high",
            sandbox_mode="danger-full-access",
            approval_policy="never",
            web_mode="disabled",
            captured_at=NOW,
        ),
    ],
)
def test_authority_numbers_are_strict_integers_excluding_bool_and_fraction(constructor) -> None:
    with pytest.raises(ValueError):
        constructor()


def test_capability_capture_time_and_security_modes_are_validated_and_digested() -> None:
    first = snapshot(captured_at=NOW)
    later = snapshot(captured_at=NOW + timedelta(seconds=1))
    assert first.snapshot_id != later.snapshot_id
    with pytest.raises(ValueError, match="aware UTC"):
        snapshot(captured_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="sandbox_mode"):
        dataclasses.replace(first, sandbox_mode="magic-root")
    with pytest.raises(ValueError, match="approval_policy"):
        dataclasses.replace(first, approval_policy="trust-everything")


def test_bootstrap_request_rejects_mutable_or_untyped_grants() -> None:
    grant_spec = BootstrapGrantSpec(
        WORKER,
        THREAD,
        GrantPurpose.REGISTER,
        GrantId(UUID(int=801)),
        NOW + timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="immutable tuple"):
        BootstrapRequest(WAVE, REPOSITORY, 2, [grant_spec], NOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="BootstrapGrantSpec"):
        BootstrapRequest(WAVE, REPOSITORY, 2, ("forged",), NOW)  # type: ignore[arg-type]


def test_capability_normalization_is_order_independent_and_rejects_tampering() -> None:
    left = snapshot(tools=("shell", "mailbox"))
    right = snapshot(tools=("mailbox", "shell", "shell"))
    assert left == right
    with pytest.raises(ValueError, match="does not match"):
        dataclasses.replace(left, model="different")


def test_typed_capability_requirements_distinguish_irrelevant_change() -> None:
    assigned_snapshot = snapshot(web_mode="disabled")
    current_snapshot = snapshot(web_mode="enabled")
    stored = assignment(capability=assigned_snapshot.snapshot_id)
    result = evaluate_assignment_capabilities(current_snapshot, stored)
    assert result.satisfied
    assert result.evaluated_snapshot_id == current_snapshot.snapshot_id
    assert stored.capability_snapshot_id == assigned_snapshot.snapshot_id


def test_relevant_capability_change_requires_assignment_revision_and_ack() -> None:
    assigned_snapshot = snapshot(tools=("shell", "mailbox"))
    current_snapshot = snapshot(tools=("mailbox",))
    tx, _, current = prepared_owner_tx(current_snapshot)
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=assigned_snapshot.snapshot_id)
    result = check_owner(tx, evidence(tx.transaction_id), expected(current, assignment_ref=ASSIGNMENT_REF))
    assert not result.allowed
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.CAPABILITY_REQUIREMENTS_UNSATISFIED


def test_irrelevant_change_keeps_assignment_but_stale_owner_snapshot_still_fails() -> None:
    assigned_snapshot = snapshot(web_mode="disabled")
    current_snapshot = snapshot(web_mode="enabled")
    tx, _, current = prepared_owner_tx(current_snapshot)
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=assigned_snapshot.snapshot_id)
    assert check_owner(tx, evidence(tx.transaction_id), expected(current, assignment_ref=ASSIGNMENT_REF)).allowed
    stale_expected = dataclasses.replace(expected(current), capability_snapshot_id=assigned_snapshot.snapshot_id)
    result = check_owner(tx, evidence(tx.transaction_id), stale_expected)
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.STALE_CAPABILITY


def test_unacknowledged_assignment_cannot_authorize_owner_check() -> None:
    tx, current_snapshot, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(
        capability=current_snapshot.snapshot_id,
        acknowledged=False,
    )
    result = check_owner(tx, evidence(tx.transaction_id), expected(current, assignment_ref=ASSIGNMENT_REF))
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.ASSIGNMENT_NOT_ACKNOWLEDGED


def test_process_evidence_is_revalidated_after_transaction_opens() -> None:
    tx = FakeTransaction()
    probe = FakeProbe()
    result = accept_process_evidence(tx, observation(), probe)
    assert isinstance(result, AcceptedProcessEvidence)
    assert result.transaction_id == tx.transaction_id
    probe.revalidated = observation(process=OTHER_PROCESS, observed=120)
    changed = accept_process_evidence(tx, observation(), probe)
    assert isinstance(changed, ProcessObservationUnavailable)
    assert changed.reason is ObservationFailure.IDENTITY_CHANGED


def test_transaction_bound_evidence_cannot_cross_or_outlive_transaction() -> None:
    tx = FakeTransaction()
    other = FakeTransaction()
    other.transaction_id = UUID(int=301)
    current_snapshot = snapshot()
    current = owner(capability=current_snapshot.snapshot_id)
    other.capabilities[current_snapshot.snapshot_id] = current_snapshot
    other.owners[(WAVE, WORKER)] = current
    with pytest.raises(TransactionMismatchError):
        check_owner(other, evidence(tx.transaction_id), expected(current))
    tx.is_active = False
    with pytest.raises(TransactionClosedError):
        accept_process_evidence(tx, observation(), FakeProbe())


def test_liveness_is_pid_reuse_safe_and_unknown_fails_closed() -> None:
    probe = FakeProbe()
    assert check_liveness(PROCESS, probe) is Liveness.ALIVE
    probe.recorded = OTHER_PROCESS
    assert check_liveness(PROCESS, probe) is Liveness.UNKNOWN
    probe.recorded = ProcessCoordinates(PROCESS.host_instance_id, PROCESS.boot_id, PROCESS.pid, 901)
    assert check_liveness(PROCESS, probe) is Liveness.DEAD
    probe.recorded = ProcessCoordinates("foreign-host", PROCESS.boot_id, PROCESS.pid, 900)
    assert check_liveness(PROCESS, probe) is Liveness.UNKNOWN
    probe.recorded = ProcessObservationUnavailable(ObservationFailure.PROBE_UNAVAILABLE, "permission denied")
    assert check_liveness(PROCESS, probe) is Liveness.UNKNOWN
    probe.recorded = ProcessObservationUnavailable(ObservationFailure.PROCESS_MISSING, "gone")
    assert check_liveness(PROCESS, probe) is Liveness.DEAD


def test_never_registered_claimant_needs_preexisting_one_use_grant() -> None:
    tx = FakeTransaction()
    cap = snapshot()
    tx.capabilities[cap.snapshot_id] = cap
    gid = GrantId(UUID(int=20))
    intent = RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, gid)
    missing = prepare_owner_change(tx, evidence(tx.transaction_id), intent, FakeProbe(), FakeIds(), FakeClock())
    assert_refusal(missing, RefusalCode.GRANT_MISSING)
    assert tx.assignment_reads == 0, "registration must not require history-read authority"
    tx.grants[gid] = grant(gid, created_revision=tx.base_store_revision + 1)
    same_tx = prepare_owner_change(tx, evidence(tx.transaction_id), intent, FakeProbe(), FakeIds(), FakeClock())
    assert_refusal(same_tx, RefusalCode.GRANT_NOT_PREEXISTING)
    tx.grants[gid] = grant(gid, created_revision=tx.base_store_revision)
    immediate_next = prepare_owner_change(
        tx, evidence(tx.transaction_id), intent, FakeProbe(), FakeIds(), FakeClock()
    )
    assert not isinstance(immediate_next, OwnershipRefusal)


def test_registration_prepares_generation_and_grant_consumption_without_staging() -> None:
    tx = FakeTransaction()
    cap = snapshot()
    tx.capabilities[cap.snapshot_id] = cap
    gid = GrantId(UUID(int=21))
    tx.grants[gid] = grant(gid)
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(result, OwnershipRefusal)
    assert result.consumed_grant_id == gid
    assert result.replacement.thread_id == THREAD
    assert result.replacement.record_version == 1
    assert not tx.staged_owners


def test_worker_first_and_coordinator_first_registration_have_equivalent_owners() -> None:
    def run(order: tuple[RoleId, ...]) -> dict[RoleId, tuple[ThreadId, CapabilitySnapshotId, int]]:
        shared = FakeTransaction()
        cap = snapshot()
        shared.capabilities[cap.snapshot_id] = cap
        identities = {
            WORKER: (THREAD, PROCESS, GrantId(UUID(int=810))),
            COORDINATOR: (OTHER_THREAD, OTHER_PROCESS, GrantId(UUID(int=811))),
        }
        for role, (thread, _, gid) in identities.items():
            shared.grants[gid] = grant(gid, role=role, thread=thread)
        ids = FakeIds()
        for index, role in enumerate(order, start=1):
            thread, process, gid = identities[role]
            tx = shared.fork(UUID(int=820 + index))
            prepared = prepare_owner_change(
                tx,
                evidence(tx.transaction_id, thread, process),
                RegisterOwner(WAVE, role, cap.snapshot_id, 2, gid),
                FakeProbe(),
                ids,
                FakeClock(),
            )
            assert not isinstance(prepared, OwnershipRefusal)
            tx.stage_owner_change(prepared)
            tx.commit()
        return {
            role: (registered.thread_id, registered.capability_snapshot_id, registered.policy_revision)
            for (wave, role), registered in shared.owners.items()
            if wave == WAVE
        }

    assert run((WORKER, COORDINATOR)) == run((COORDINATOR, WORKER))


def test_exact_duplicate_registration_preserves_generation_and_does_not_reconsume_grant() -> None:
    shared = FakeTransaction()
    cap = snapshot()
    shared.capabilities[cap.snapshot_id] = cap
    gid = GrantId(UUID(int=830))
    shared.grants[gid] = grant(gid)
    first_tx = shared.fork(UUID(int=831))
    first = prepare_owner_change(
        first_tx,
        evidence(first_tx.transaction_id),
        RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(first, OwnershipRefusal)
    first_tx.stage_owner_change(first)
    first_tx.commit()
    first_generation = shared.owners[(WAVE, WORKER)].generation_id

    duplicate_tx = shared.fork(UUID(int=832))
    duplicate = prepare_owner_change(
        duplicate_tx,
        evidence(duplicate_tx.transaction_id),
        RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(duplicate, OwnershipRefusal)
    assert duplicate.replacement.generation_id == first_generation
    assert duplicate.consumed_grant_id is None


def test_competing_prepared_registration_cas_has_one_winner_and_no_partial_grant_mutation() -> None:
    shared = FakeTransaction()
    cap = snapshot()
    shared.capabilities[cap.snapshot_id] = cap
    first_gid = GrantId(UUID(int=840))
    second_gid = GrantId(UUID(int=841))
    shared.grants[first_gid] = grant(first_gid)
    shared.grants[second_gid] = grant(second_gid, thread=OTHER_THREAD)
    first_tx = shared.fork(UUID(int=842))
    second_tx = shared.fork(UUID(int=843))
    first = prepare_owner_change(
        first_tx,
        evidence(first_tx.transaction_id),
        RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, first_gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    second = prepare_owner_change(
        second_tx,
        evidence(second_tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, second_gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(first, OwnershipRefusal)
    assert not isinstance(second, OwnershipRefusal)
    first_tx.stage_owner_change(first)
    second_tx.stage_owner_change(second)
    first_tx.commit()
    with pytest.raises(SerializationConflict):
        second_tx.commit()
    assert shared.owners[(WAVE, WORKER)].thread_id == THREAD
    assert shared.grants[first_gid].consumed
    assert not shared.grants[second_gid].consumed


def test_wrong_wave_registration_fails_before_grant_authority_is_considered() -> None:
    tx = FakeTransaction()
    cap = snapshot()
    tx.capabilities[cap.snapshot_id] = cap
    gid = GrantId(UUID(int=850))
    tx.grants[gid] = grant(gid)
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        RegisterOwner(WaveId("other-wave"), WORKER, cap.snapshot_id, 2, gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.STALE_POLICY)


def test_live_owner_conflict_is_not_replaced_by_registration() -> None:
    tx, cap, _ = prepared_owner_tx()
    gid = GrantId(UUID(int=22))
    tx.grants[gid] = grant(gid)
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        RegisterOwner(WAVE, WORKER, cap.snapshot_id, 2, gid),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.OWNER_EXISTS)


def test_dead_owner_replacement_reads_fresh_proof_inside_active_transaction() -> None:
    tx, cap, current = prepared_owner_tx()
    probe = FakeProbe()
    probe.assert_active = tx
    probe.recorded = ProcessObservationUnavailable(ObservationFailure.PROCESS_MISSING, "gone")
    intent = ReplaceDeadOwner(WAVE, WORKER, current.record_version, current.generation_id, cap.snapshot_id, 2)
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        intent,
        probe,
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(result, OwnershipRefusal)
    assert result.fresh_liveness is Liveness.DEAD
    assert result.replacement.generation_id != current.generation_id
    assert probe.recorded_calls == 1


@pytest.mark.parametrize(
    ("recorded", "code"),
    [
        (PROCESS, RefusalCode.OWNER_LIVE),
        (
            ProcessObservationUnavailable(ObservationFailure.PROBE_UNAVAILABLE, "unreadable"),
            RefusalCode.OWNER_LIVENESS_UNKNOWN,
        ),
    ],
)
def test_alive_or_unknown_owner_refuses_automatic_replacement(recorded, code) -> None:
    tx, cap, current = prepared_owner_tx()
    probe = FakeProbe()
    probe.recorded = recorded
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        ReplaceDeadOwner(WAVE, WORKER, current.record_version, current.generation_id, cap.snapshot_id, 2),
        probe,
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, code)


def test_authorized_takeover_requires_exact_coordinator_generation() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.owners[(WAVE, COORDINATOR)] = owner(
        role=COORDINATOR,
        generation=OwnerGenerationId(COORDINATOR_GENERATION.value),
        capability=cap.snapshot_id,
    )
    gid = GrantId(UUID(int=23))
    tx.grants[gid] = grant(
        gid,
        purpose=GrantPurpose.TAKEOVER,
        authorized_by=COORDINATOR_GENERATION,
        target_generation=current.generation_id,
        target_version=current.record_version,
    )
    intent = AuthorizedTakeover(
        WAVE,
        WORKER,
        current.record_version,
        current.generation_id,
        cap.snapshot_id,
        2,
        gid,
        CoordinatorGenerationId(UUID(int=999)),
    )
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        intent,
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.STALE_OWNER_GENERATION)


def test_takeover_grant_is_bound_to_exact_target_owner_generation_and_version() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.owners[(WAVE, COORDINATOR)] = owner(
        role=COORDINATOR,
        generation=OwnerGenerationId(COORDINATOR_GENERATION.value),
        capability=cap.snapshot_id,
    )
    gid = GrantId(UUID(int=802))
    tx.grants[gid] = grant(
        gid,
        purpose=GrantPurpose.TAKEOVER,
        authorized_by=COORDINATOR_GENERATION,
        target_generation=OwnerGenerationId(UUID(int=999)),
        target_version=current.record_version,
    )
    intent = AuthorizedTakeover(
        WAVE,
        WORKER,
        current.record_version,
        current.generation_id,
        cap.snapshot_id,
        2,
        gid,
        COORDINATOR_GENERATION,
    )
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        intent,
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.GRANT_MISMATCH)


def test_stale_authorizing_coordinator_cannot_activate_takeover_grant() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.owners[(WAVE, COORDINATOR)] = owner(
        role=COORDINATOR,
        generation=OwnerGenerationId(UUID(int=803)),
        capability=cap.snapshot_id,
    )
    gid = GrantId(UUID(int=804))
    tx.grants[gid] = grant(
        gid,
        purpose=GrantPurpose.TAKEOVER,
        authorized_by=COORDINATOR_GENERATION,
        target_generation=current.generation_id,
        target_version=current.record_version,
    )
    intent = AuthorizedTakeover(
        WAVE,
        WORKER,
        current.record_version,
        current.generation_id,
        cap.snapshot_id,
        2,
        gid,
        COORDINATOR_GENERATION,
    )
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        intent,
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.STALE_OWNER_GENERATION)


def test_coordinator_recovery_has_an_explicit_target_bound_consumption_path() -> None:
    tx = FakeTransaction()
    cap = snapshot()
    tx.capabilities[cap.snapshot_id] = cap
    current = owner(
        role=COORDINATOR,
        generation=OwnerGenerationId(COORDINATOR_GENERATION.value),
        capability=cap.snapshot_id,
    )
    tx.owners[(WAVE, COORDINATOR)] = current
    gid = GrantId(UUID(int=805))
    tx.grants[gid] = StoredGrant(
        gid,
        WAVE,
        COORDINATOR,
        OTHER_THREAD,
        GrantPurpose.COORDINATOR_RECOVERY,
        2,
        tx.base_store_revision,
        NOW - timedelta(minutes=1),
        NOW + timedelta(minutes=5),
        False,
        COORDINATOR_GENERATION,
        current.generation_id,
        current.record_version,
    )
    intent = RecoverCoordinator(
        WAVE,
        COORDINATOR,
        current.record_version,
        current.generation_id,
        cap.snapshot_id,
        2,
        gid,
    )
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        intent,
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(result, OwnershipRefusal)
    assert result.consumed_grant_id == gid
    assert result.replacement.thread_id == OTHER_THREAD


def test_capability_update_preserves_generation_but_changes_exact_pointer() -> None:
    tx, _, current = prepared_owner_tx()
    updated = snapshot(web_mode="enabled")
    tx.capabilities[updated.snapshot_id] = updated
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        UpdateCapability(expected(current), updated.snapshot_id),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(result, OwnershipRefusal)
    assert result.replacement.generation_id == current.generation_id
    assert result.replacement.capability_snapshot_id == updated.snapshot_id
    assert result.expected_owner_version == current.record_version


def test_policy_rebrief_advances_only_owner_policy_and_preserves_generation_snapshot() -> None:
    tx, cap, current = prepared_owner_tx()
    old = dataclasses.replace(current, policy_revision=1)
    tx.owners[(WAVE, WORKER)] = old
    tx.policy_revision = 2
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        RebriefOwner(expected(old), 2),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(result, OwnershipRefusal)
    assert result.replacement.policy_revision == 2
    assert result.replacement.record_version == old.record_version + 1
    assert result.replacement.generation_id == old.generation_id
    assert result.replacement.capability_snapshot_id == cap.snapshot_id
    assert result.consumed_grant_id is None
    assert not tx.assignments


def test_policy_rebrief_rejects_stale_process_cas_or_uncommitted_policy() -> None:
    tx, _, current = prepared_owner_tx()
    old = dataclasses.replace(current, policy_revision=1)
    tx.owners[(WAVE, WORKER)] = old
    tx.policy_revision = 2
    stale_process = prepare_owner_change(
        tx,
        evidence(tx.transaction_id, OTHER_THREAD, OTHER_PROCESS),
        RebriefOwner(expected(old), 2),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(stale_process, RefusalCode.OWNER_MISMATCH)
    stale_cas = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        RebriefOwner(dataclasses.replace(expected(old), owner_record_version=old.record_version - 1), 2),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(stale_cas, RefusalCode.STALE_OWNER_VERSION)
    tx.policy_revision = 3
    wrong_policy = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        RebriefOwner(expected(old), 2),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(wrong_policy, RefusalCode.STALE_POLICY)


def test_policy_rebrief_cannot_silently_ack_assignment_or_claim() -> None:
    tx, cap, current = prepared_owner_tx()
    old = dataclasses.replace(current, policy_revision=1)
    tx.owners[(WAVE, WORKER)] = old
    tx.policy_revision = 2
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    result = prepare_owner_change(
        tx,
        evidence(tx.transaction_id),
        RebriefOwner(expected(old, assignment_ref=ASSIGNMENT_REF), 2),
        FakeProbe(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.STALE_ASSIGNMENT)


def test_bootstrap_and_recovery_are_restricted_administrative_entries() -> None:
    gid = GrantId(UUID(int=24))
    request = BootstrapRequest(
        WAVE,
        REPOSITORY,
        2,
        (BootstrapGrantSpec(WORKER, THREAD, GrantPurpose.REGISTER, gid, NOW + timedelta(minutes=5)),),
        NOW,
    )
    bootstrap_tx = FakeBootstrapTransaction("bootstrap")
    assert not isinstance(provision_wave_bootstrap(bootstrap_tx, request), OwnershipRefusal)
    wrong_tx = FakeBootstrapTransaction("recovery")
    assert_refusal(provision_wave_bootstrap(wrong_tx, request), RefusalCode.ADMINISTRATIVE_ENTRY_MISMATCH)

    recovery_tx = FakeBootstrapTransaction("recovery")
    recovery_tx.exists = True
    coord_generation = OwnerGenerationId(COORDINATOR_GENERATION.value)
    recovery_tx.owners[(WAVE, COORDINATOR)] = owner(
        role=COORDINATOR,
        generation=coord_generation,
    )
    recovery = RecoveryDelegationRequest(
        WAVE,
        COORDINATOR_GENERATION,
        3,
        OTHER_THREAD,
        GrantId(UUID(int=25)),
        NOW + timedelta(minutes=5),
        NOW,
    )
    assert not isinstance(provision_recovery_delegation(recovery_tx, recovery), OwnershipRefusal)


def test_physical_target_conflict_is_independent_of_repository_and_wave() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    conflicting_repository = RepositoryKey(TARGET.host_instance_id, "/another/repository/.git")
    existing = WorktreeClaim(
        ClaimId(UUID(int=26)),
        1,
        ClaimState.RESERVED,
        TARGET,
        conflicting_repository,
        WaveId("another-wave"),
        99,
        "other-branch",
        ASSIGNMENT_REF,
        WORKER,
        THREAD,
        GENERATION,
        "sha256:" + "c" * 64,
    )
    tx.claims[existing.claim_id] = existing
    intent = ReserveClaim(
        expected(current, assignment_ref=ASSIGNMENT_REF),
        TARGET,
        REPOSITORY,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        "sha256:" + "d" * 64,
    )
    result = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        intent,
        worktree(),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.CLAIM_CONFLICT)


def test_reserve_before_materialization_and_finalize_require_fresh_exact_evidence() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    reserve = ReserveClaim(
        expected(current, assignment_ref=ASSIGNMENT_REF),
        TARGET,
        REPOSITORY,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        "sha256:" + "e" * 64,
    )
    prepared = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        reserve,
        worktree(),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(prepared, OwnershipRefusal)
    assert prepared.replacement.state is ClaimState.RESERVED
    claim = prepared.replacement
    tx.claims[claim.claim_id] = claim
    bound = expected(current, assignment_ref=ASSIGNMENT_REF, claim_id=claim.claim_id)
    mismatch = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        FinalizeClaim(bound, claim.claim_id, claim.record_version),
        worktree(exists=True, branch="wrong"),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(mismatch, RefusalCode.WORKTREE_EVIDENCE_MISMATCH)
    finalized = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        FinalizeClaim(bound, claim.claim_id, claim.record_version),
        worktree(exists=True, branch="issue-200"),
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(finalized, OwnershipRefusal)
    assert finalized.replacement.state is ClaimState.MATERIALIZED


def test_reservation_rejects_a_preexisting_materialization() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    reserve = ReserveClaim(
        expected(current, assignment_ref=ASSIGNMENT_REF),
        TARGET,
        REPOSITORY,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        "sha256:" + "9" * 64,
    )
    result = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        reserve,
        worktree(exists=True, branch="foreign-preexisting"),
        FakeIds(),
        FakeClock(),
    )
    assert_refusal(result, RefusalCode.WORKTREE_EVIDENCE_MISMATCH)


@pytest.mark.parametrize("state", [ClaimState.RELEASED, ClaimState.RECONCILE_REQUIRED])
def test_inactive_claim_cannot_be_reused_as_owner_authority(state: ClaimState) -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    claim = WorktreeClaim(
        ClaimId(UUID(int=806)),
        1,
        state,
        TARGET,
        REPOSITORY,
        WAVE,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        WORKER,
        THREAD,
        GENERATION,
        "sha256:" + "3" * 64,
    )
    tx.claims[claim.claim_id] = claim
    result = check_owner(
        tx,
        evidence(tx.transaction_id),
        expected(current, assignment_ref=ASSIGNMENT_REF, claim_id=claim.claim_id),
    )
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.CLAIM_STATE_MISMATCH


def test_claim_cannot_be_reused_with_a_different_assignment() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    other_assignment = AssignmentRef(UUID(int=807), 1, "sha256:" + "4" * 64)
    tx.assignments[other_assignment] = dataclasses.replace(
        assignment(capability=cap.snapshot_id), assignment=other_assignment
    )
    claim = WorktreeClaim(
        ClaimId(UUID(int=808)),
        1,
        ClaimState.RESERVED,
        TARGET,
        REPOSITORY,
        WAVE,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        WORKER,
        THREAD,
        GENERATION,
        "sha256:" + "5" * 64,
    )
    tx.claims[claim.claim_id] = claim
    result = check_owner(
        tx,
        evidence(tx.transaction_id),
        expected(current, assignment_ref=other_assignment, claim_id=claim.claim_id),
    )
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.STALE_ASSIGNMENT


def test_claim_from_another_wave_cannot_be_reused_by_current_owner() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    claim = WorktreeClaim(
        ClaimId(UUID(int=809)),
        1,
        ClaimState.RESERVED,
        TARGET,
        REPOSITORY,
        WaveId("other-wave"),
        200,
        "issue-200",
        ASSIGNMENT_REF,
        WORKER,
        THREAD,
        GENERATION,
        "sha256:" + "6" * 64,
    )
    tx.claims[claim.claim_id] = claim
    result = check_owner(
        tx,
        evidence(tx.transaction_id),
        expected(current, assignment_ref=ASSIGNMENT_REF, claim_id=claim.claim_id),
    )
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.STALE_CLAIM


def test_claim_release_and_reconcile_marker_are_explicit_state_transitions() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id)
    claim = WorktreeClaim(
        ClaimId(UUID(int=27)),
        2,
        ClaimState.MATERIALIZED,
        TARGET,
        REPOSITORY,
        WAVE,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        WORKER,
        THREAD,
        GENERATION,
        "sha256:" + "f" * 64,
    )
    tx.claims[claim.claim_id] = claim
    bound = expected(current, assignment_ref=ASSIGNMENT_REF, claim_id=claim.claim_id)
    marked = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        MarkReconciliationRequired(bound, claim.claim_id, 2),
        None,
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(marked, OwnershipRefusal)
    assert marked.replacement.state is ClaimState.RECONCILE_REQUIRED
    released = prepare_claim_change(
        tx,
        evidence(tx.transaction_id),
        ReleaseClaim(bound, claim.claim_id, 2),
        None,
        FakeIds(),
        FakeClock(),
    )
    assert not isinstance(released, OwnershipRefusal)
    assert released.replacement.state is ClaimState.RELEASED


def test_reconciliation_requires_current_coordinator_record_and_successor_assignment() -> None:
    tx, cap, old_owner = prepared_owner_tx()
    new_generation = OwnerGenerationId(UUID(int=28))
    successor = owner(thread=OTHER_THREAD, process=OTHER_PROCESS, generation=new_generation, capability=cap.snapshot_id)
    tx.owners[(WAVE, WORKER)] = successor
    coordinator_owner = owner(
        role=COORDINATOR,
        thread=THREAD,
        generation=OwnerGenerationId(COORDINATOR_GENERATION.value),
        capability=cap.snapshot_id,
    )
    tx.owners[(WAVE, COORDINATOR)] = coordinator_owner
    tx.assignments[ASSIGNMENT_REF] = assignment(capability=cap.snapshot_id, generation=new_generation)
    claim = WorktreeClaim(
        ClaimId(UUID(int=29)),
        4,
        ClaimState.RECONCILE_REQUIRED,
        TARGET,
        REPOSITORY,
        WAVE,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        WORKER,
        old_owner.thread_id,
        old_owner.generation_id,
        "sha256:" + "1" * 64,
    )
    tx.claims[claim.claim_id] = claim
    tx.reconciliations[RECORD_REF] = StoredReconciliation(
        RECORD_REF,
        WAVE,
        claim.claim_id,
        old_owner.generation_id,
        new_generation,
        COORDINATOR_GENERATION,
        ASSIGNMENT_REF,
        True,
        "issue-200",
    )
    intent = RebindClaimIntent(
        claim.claim_id,
        claim.record_version,
        ClaimState.RECONCILE_REQUIRED,
        old_owner.generation_id,
        new_generation,
        COORDINATOR_GENERATION,
        RECORD_REF,
        ASSIGNMENT_REF,
    )
    result = prepare_claim_reconciliation(
        tx,
        evidence(tx.transaction_id, coordinator_owner.thread_id, coordinator_owner.process),
        intent,
        worktree(exists=True, branch="issue-200"),
    )
    assert not isinstance(result, OwnershipRefusal)
    assert result.replacement.owner_generation_id == new_generation
    assert result.replacement.thread_id == OTHER_THREAD
    assert result.reconciliation == RECORD_REF
    tx.policy_revision = 3
    stale_policy = prepare_claim_reconciliation(
        tx,
        evidence(tx.transaction_id, coordinator_owner.thread_id, coordinator_owner.process),
        intent,
        worktree(exists=True, branch="issue-200"),
    )
    assert_refusal(stale_policy, RefusalCode.STALE_POLICY)


def test_stale_coordinator_generation_cannot_rebind_crash_claim() -> None:
    tx, cap, current = prepared_owner_tx()
    tx.owners[(WAVE, COORDINATOR)] = owner(
        role=COORDINATOR,
        generation=OwnerGenerationId(UUID(int=998)),
        capability=cap.snapshot_id,
    )
    claim = WorktreeClaim(
        ClaimId(UUID(int=30)),
        1,
        ClaimState.RECONCILE_REQUIRED,
        TARGET,
        REPOSITORY,
        WAVE,
        200,
        "issue-200",
        ASSIGNMENT_REF,
        WORKER,
        current.thread_id,
        current.generation_id,
        "sha256:" + "2" * 64,
    )
    tx.claims[claim.claim_id] = claim
    intent = RebindClaimIntent(
        claim.claim_id,
        1,
        ClaimState.RECONCILE_REQUIRED,
        current.generation_id,
        OwnerGenerationId(UUID(int=31)),
        COORDINATOR_GENERATION,
        RECORD_REF,
        ASSIGNMENT_REF,
    )
    result = prepare_claim_reconciliation(tx, evidence(tx.transaction_id), intent, worktree())
    assert_refusal(result, RefusalCode.STALE_OWNER_GENERATION)


def test_linux_probe_rejects_missing_thread_and_namespace_pid1(tmp_path: Path) -> None:
    host = tmp_path / "machine-id"
    boot = tmp_path / "boot-id"
    host.write_text("0123456789abcdef\n", encoding="utf-8")
    boot.write_text(f"{BOOT}\n", encoding="utf-8")
    missing = LinuxHostProcessProbe(
        proc_root=tmp_path / "proc",
        host_id_path=host,
        boot_id_path=boot,
        environ={},
        getpid=lambda: 2,
    ).observe_self(LocalIdentityContext(THREAD))
    assert isinstance(missing, ProcessObservationUnavailable)
    assert missing.reason is ObservationFailure.MISSING_THREAD
    pid1 = LinuxHostProcessProbe(
        proc_root=tmp_path / "proc",
        host_id_path=host,
        boot_id_path=boot,
        environ={"CODEX_THREAD_ID": str(THREAD.value)},
        getpid=lambda: 1,
    ).observe_self(LocalIdentityContext(THREAD))
    assert isinstance(pid1, ProcessObservationUnavailable)
    assert pid1.reason is ObservationFailure.NAMESPACE_PID1


def test_linux_probe_reads_bounded_native_ancestor_and_detects_pid_reuse(tmp_path: Path) -> None:
    host = tmp_path / "machine-id"
    boot = tmp_path / "boot-id"
    proc = tmp_path / "proc"
    host.write_text("0123456789abcdef\n", encoding="utf-8")
    boot.write_text(f"{BOOT}\n", encoding="utf-8")
    process_dir = proc / "4200"
    process_dir.mkdir(parents=True)

    def write_stat(start: int) -> None:
        # fields after comm begin with state (3); index 19 is starttime (22).
        fields = ["S", "1"] + ["0"] * 17 + [str(start)] + ["0"] * 4
        (process_dir / "stat").write_text(f"4200 (codex) {' '.join(fields)}\n", encoding="utf-8")

    write_stat(900)
    (process_dir / "comm").write_text("codex\n", encoding="utf-8")
    (process_dir / "cmdline").write_bytes(b"/usr/bin/codex\0")
    probe = LinuxHostProcessProbe(
        proc_root=proc,
        host_id_path=host,
        boot_id_path=boot,
        environ={"CODEX_THREAD_ID": str(THREAD.value)},
        getpid=lambda: 4200,
        monotonic_ns=lambda: 123,
    )
    observed = probe.observe_self(LocalIdentityContext(THREAD))
    assert isinstance(observed, ProcessObservation)
    assert observed.process == PROCESS
    write_stat(901)
    reused = probe.observe_recorded(PROCESS)
    assert isinstance(reused, ProcessCoordinates)
    assert reused.start_ticks == 901
    assert check_liveness(PROCESS, probe) is Liveness.DEAD


def test_linux_probe_does_not_trust_codex_substrings_or_malformed_proc_data(tmp_path: Path) -> None:
    host = tmp_path / "machine-id"
    boot = tmp_path / "boot-id"
    proc = tmp_path / "proc"
    host.write_text("0123456789abcdef\n", encoding="utf-8")
    boot.write_text(f"{BOOT}\n", encoding="utf-8")
    process_dir = proc / "4200"
    process_dir.mkdir(parents=True)
    fields = ["S", "1"] + ["0"] * 17 + ["900"] + ["0"] * 4
    (process_dir / "stat").write_text(f"4200 (not-codex-helper) {' '.join(fields)}\n", encoding="utf-8")
    (process_dir / "comm").write_text("not-codex-helper\n", encoding="utf-8")
    (process_dir / "cmdline").write_bytes(b"/usr/bin/not-codex-helper\0")
    probe = LinuxHostProcessProbe(
        proc_root=proc,
        host_id_path=host,
        boot_id_path=boot,
        environ={"CODEX_THREAD_ID": str(THREAD.value)},
        getpid=lambda: 4200,
    )
    result = probe.observe_self(LocalIdentityContext(THREAD))
    assert isinstance(result, ProcessObservationUnavailable)
    assert result.reason is ObservationFailure.NO_CODEX_ANCESTOR

    malformed_fields = ["S", "1"] + ["0"] * 17 + ["-1"] + ["0"] * 4
    (process_dir / "stat").write_text(f"4200 (codex) {' '.join(malformed_fields)}\n", encoding="utf-8")
    (process_dir / "comm").write_bytes(b"\xff\xfe")
    malformed = probe.observe_self(LocalIdentityContext(THREAD))
    assert isinstance(malformed, ProcessObservationUnavailable)
    assert malformed.reason is ObservationFailure.CONTRADICTORY


def test_real_worktree_probe_canonicalizes_linked_metadata_without_git_subprocess(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    admin = common / "worktrees" / "issue-200"
    target_path = tmp_path / "worktrees" / "issue-200"
    admin.mkdir(parents=True)
    target_path.mkdir(parents=True)
    (target_path / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (admin / "gitdir").write_text(f"{target_path / '.git'}\n", encoding="utf-8")
    (admin / "HEAD").write_text("ref: refs/heads/issue-200\n", encoding="utf-8")
    repository = RepositoryKey("0123456789abcdef", str(common.resolve()))
    probe = LocalWorktreeEvidenceProbe(repository, monotonic_ns=lambda: 777)
    target = probe.canonicalize_target(target_path)
    assert isinstance(target, PhysicalTargetKey)
    inspected = probe.inspect(target)
    assert isinstance(inspected, WorktreeEvidence)
    assert inspected.repository == repository
    assert inspected.branch == "issue-200"
    assert inspected.observed_monotonic_ns == 777


def test_real_worktree_probe_rejects_symlink_alias_and_foreign_common_dir(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    admin = common / "worktrees" / "issue-200"
    target_path = tmp_path / "worktrees" / "issue-200"
    admin.mkdir(parents=True)
    target_path.mkdir(parents=True)
    (target_path / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (admin / "gitdir").write_text(f"{target_path / '.git'}\n", encoding="utf-8")
    (admin / "HEAD").write_text("ref: refs/heads/issue-200\n", encoding="utf-8")
    repository = RepositoryKey("0123456789abcdef", str(common.resolve()))
    probe = LocalWorktreeEvidenceProbe(repository)
    alias = tmp_path / "alias"
    alias.symlink_to(target_path, target_is_directory=True)
    assert isinstance(probe.canonicalize_target(alias), WorktreeEvidenceUnavailable)

    target = probe.canonicalize_target(target_path)
    assert isinstance(target, PhysicalTargetKey)
    foreign = RepositoryKey("0123456789abcdef", str((tmp_path / "foreign" / ".git").absolute()))
    foreign_probe = LocalWorktreeEvidenceProbe(foreign)
    assert isinstance(foreign_probe.inspect(target), WorktreeEvidenceUnavailable)


def test_real_worktree_probe_rejects_copied_linked_worktree_pointer(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    admin = common / "worktrees" / "worktree-a"
    worktree_a = tmp_path / "worktrees" / "worktree-a"
    worktree_b = tmp_path / "worktrees" / "worktree-b"
    admin.mkdir(parents=True)
    worktree_a.mkdir(parents=True)
    worktree_b.mkdir(parents=True)
    pointer = f"gitdir: {admin}\n"
    (worktree_a / ".git").write_text(pointer, encoding="utf-8")
    (worktree_b / ".git").write_text(pointer, encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (admin / "gitdir").write_text(f"{worktree_a / '.git'}\n", encoding="utf-8")
    (admin / "HEAD").write_text("ref: refs/heads/issue-200\n", encoding="utf-8")
    repository = RepositoryKey("0123456789abcdef", str(common.resolve()))
    probe = LocalWorktreeEvidenceProbe(repository)
    target_a = probe.canonicalize_target(worktree_a)
    target_b = probe.canonicalize_target(worktree_b)
    assert isinstance(target_a, PhysicalTargetKey)
    assert isinstance(target_b, PhysicalTargetKey)
    assert isinstance(probe.inspect(target_a), WorktreeEvidence)
    copied = probe.inspect(target_b)
    assert isinstance(copied, WorktreeEvidenceUnavailable)
    assert "backlink" in copied.detail


def test_worktree_probe_fails_typed_on_absent_parent_or_lstat_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = RepositoryKey("0123456789abcdef", str((tmp_path / "repo" / ".git").absolute()))
    probe = LocalWorktreeEvidenceProbe(repository)
    impossible = PhysicalTargetKey(
        repository.host_instance_id,
        str((tmp_path / "missing-parent" / "target").absolute()),
    )
    assert isinstance(probe.inspect(impossible), WorktreeEvidenceUnavailable)

    def denied(self: Path):
        raise PermissionError("fixture denial")

    monkeypatch.setattr(Path, "lstat", denied)
    denied_result = probe.canonicalize_target(tmp_path / "target")
    assert isinstance(denied_result, WorktreeEvidenceUnavailable)
