"""Pure transaction-bound ownership, capability, and bootstrap policy."""

from __future__ import annotations

from dataclasses import replace

from .ports import BootstrapTransaction, Clock, HostProcessProbe, IdFactory, OwnershipTransaction
from .types import (
    AcceptedProcessEvidence,
    AuthorizedTakeover,
    BootstrapRequest,
    CapabilityField,
    CapabilityRequirementCheck,
    CapabilitySnapshot,
    CapabilitySnapshotId,
    ClaimState,
    CoordinatorGenerationId,
    ExpectedOwnerBindings,
    GrantPurpose,
    Liveness,
    ObservationFailure,
    OwnerChangeIntent,
    OwnerCheck,
    OwnershipRefusal,
    PreparedBootstrap,
    PreparedOwnerChange,
    PreparedRecoveryDelegation,
    ProcessCoordinates,
    ProcessObservationUnavailable,
    RebriefOwner,
    RecoverCoordinator,
    RecoveryDelegationRequest,
    RefusalCode,
    RegisterOwner,
    ReplaceDeadOwner,
    RoleId,
    RoleOwner,
    StoredAssignment,
    StoredGrant,
    TransactionClosedError,
    TransactionMismatchError,
    UpdateCapability,
    WaveId,
)

_SET_FIELDS = {
    CapabilityField.WORKSPACE_ROOTS,
    CapabilityField.ADDITIONAL_WRITABLE_ROOTS,
    CapabilityField.TOOL_FAMILIES,
    CapabilityField.REQUIRED_APPS,
    CapabilityField.REQUIRED_PLUGINS,
    CapabilityField.DELIVERY_MECHANISMS,
    CapabilityField.WAKE_MECHANISMS,
}
_DEAD_FAILURES = {
    ObservationFailure.PROCESS_MISSING,
    ObservationFailure.PROCESS_START_CHANGED,
    ObservationFailure.BOOT_CHANGED,
}


def _refuse(code: RefusalCode, detail: str) -> OwnershipRefusal:
    return OwnershipRefusal(code=code, detail=detail)


def _require_evidence_transaction(tx: OwnershipTransaction, evidence: AcceptedProcessEvidence) -> None:
    if not tx.is_active:
        raise TransactionClosedError("ownership operation requires an active transaction")
    if evidence.transaction_id != tx.transaction_id:
        raise TransactionMismatchError("accepted process evidence belongs to another transaction")


def evaluate_assignment_capabilities(
    current: CapabilitySnapshot, assignment: StoredAssignment
) -> CapabilityRequirementCheck:
    """Evaluate only durable, coordinator-authored typed requirements.

    The assignment's historical snapshot remains immutable provenance.  A new
    current snapshot can keep the assignment valid when every required field is
    still satisfied; unrelated digest changes therefore do not fabricate a new
    assignment revision.
    """

    unsatisfied: list[CapabilityField] = []
    for requirement in assignment.capability_requirements.fields:
        current_values = set(current.field_values(requirement.field))
        required_values = set(requirement.accepted_values)
        if requirement.field in _SET_FIELDS:
            satisfied = required_values <= current_values
        else:
            satisfied = bool(required_values & current_values)
        if not satisfied:
            unsatisfied.append(requirement.field)
    return CapabilityRequirementCheck(
        satisfied=not unsatisfied,
        unsatisfied_fields=tuple(unsatisfied),
        requirements_digest=assignment.capability_requirements.digest,
        evaluated_snapshot_id=current.snapshot_id,
    )


def check_liveness(recorded: ProcessCoordinates, probe: HostProcessProbe) -> Liveness:
    """Return a diagnostic tri-state; this standalone result grants no authority."""

    observed = probe.observe_recorded(recorded)
    if isinstance(observed, ProcessObservationUnavailable):
        return Liveness.DEAD if observed.reason in _DEAD_FAILURES else Liveness.UNKNOWN
    if observed.host_instance_id != recorded.host_instance_id or observed.pid != recorded.pid:
        return Liveness.UNKNOWN
    if observed.boot_id != recorded.boot_id or observed.start_ticks != recorded.start_ticks:
        return Liveness.DEAD
    return Liveness.ALIVE


def _fresh_liveness_in_transaction(
    tx: OwnershipTransaction, recorded: ProcessCoordinates, probe: HostProcessProbe
) -> Liveness:
    if not tx.is_active:
        raise TransactionClosedError("dead-owner proof requires an active transaction")
    # The bounded read happens here, after the active-transaction check.  No
    # cached Liveness/observation is accepted by prepare_owner_change.
    return check_liveness(recorded, probe)


def check_owner(
    tx: OwnershipTransaction,
    evidence: AcceptedProcessEvidence,
    expected: ExpectedOwnerBindings,
) -> OwnerCheck:
    _require_evidence_transaction(tx, evidence)
    owner = tx.read_owner(expected.wave_id, expected.role_id)
    if owner is None:
        return OwnerCheck(None, _refuse(RefusalCode.OWNER_MISSING, "role has no current owner"))
    comparisons = (
        (
            owner.record_version == expected.owner_record_version,
            RefusalCode.STALE_OWNER_VERSION,
            "owner version changed",
        ),
        (owner.thread_id == expected.thread_id, RefusalCode.OWNER_MISMATCH, "owner thread changed"),
        (
            owner.generation_id == expected.generation_id,
            RefusalCode.STALE_OWNER_GENERATION,
            "owner generation changed",
        ),
        (
            owner.capability_snapshot_id == expected.capability_snapshot_id,
            RefusalCode.STALE_CAPABILITY,
            "owner capability snapshot changed",
        ),
        (owner.policy_revision == expected.policy_revision, RefusalCode.STALE_POLICY, "owner policy changed"),
        (
            tx.read_policy_revision(expected.wave_id) == expected.policy_revision,
            RefusalCode.STALE_POLICY,
            "wave policy changed",
        ),
        (
            evidence.observation.thread_id == owner.thread_id and evidence.observation.process == owner.process,
            RefusalCode.OWNER_MISMATCH,
            "fresh process evidence does not match current owner",
        ),
    )
    for matched, code, detail in comparisons:
        if not matched:
            return OwnerCheck(owner, _refuse(code, detail))
    if expected.assignment is not None:
        assignment = tx.read_assignment(expected.assignment)
        if assignment is None:
            return OwnerCheck(owner, _refuse(RefusalCode.ASSIGNMENT_MISSING, "assignment record is absent"))
        if assignment.assignment != expected.assignment or assignment.wave_id != owner.wave_id:
            return OwnerCheck(owner, _refuse(RefusalCode.STALE_ASSIGNMENT, "assignment reference changed"))
        if assignment.role_id != owner.role_id or assignment.owner_generation_id != owner.generation_id:
            return OwnerCheck(owner, _refuse(RefusalCode.STALE_ASSIGNMENT, "assignment owner binding changed"))
        if assignment.policy_revision != owner.policy_revision:
            return OwnerCheck(owner, _refuse(RefusalCode.STALE_POLICY, "assignment policy is stale"))
        if not assignment.acknowledged:
            return OwnerCheck(
                owner,
                _refuse(RefusalCode.ASSIGNMENT_NOT_ACKNOWLEDGED, "assignment has no matching acknowledgement"),
            )
        current_snapshot = tx.read_capability(owner.capability_snapshot_id)
        if current_snapshot is None:
            return OwnerCheck(owner, _refuse(RefusalCode.CAPABILITY_MISSING, "current capability is absent"))
        requirement_check = evaluate_assignment_capabilities(current_snapshot, assignment)
        if not requirement_check.satisfied:
            names = ",".join(field.value for field in requirement_check.unsatisfied_fields)
            return OwnerCheck(
                owner,
                _refuse(
                    RefusalCode.CAPABILITY_REQUIREMENTS_UNSATISFIED,
                    f"assignment-required capability fields changed: {names}",
                ),
            )
    if expected.claim_id is not None:
        claim = tx.read_claim(expected.claim_id)
        if claim is None:
            return OwnerCheck(owner, _refuse(RefusalCode.CLAIM_MISSING, "bound claim is absent"))
        if (
            claim.wave_id != owner.wave_id
            or claim.role_id != owner.role_id
            or claim.thread_id != owner.thread_id
            or claim.owner_generation_id != owner.generation_id
        ):
            return OwnerCheck(owner, _refuse(RefusalCode.STALE_CLAIM, "claim owner binding changed"))
        if claim.state not in {ClaimState.RESERVED, ClaimState.MATERIALIZED}:
            return OwnerCheck(owner, _refuse(RefusalCode.CLAIM_STATE_MISMATCH, "claim is not active"))
        if expected.assignment is None or claim.assignment != expected.assignment:
            return OwnerCheck(owner, _refuse(RefusalCode.STALE_ASSIGNMENT, "claim assignment binding changed"))
    return OwnerCheck(owner, None)


def _validate_capability_and_policy(
    tx: OwnershipTransaction,
    wave_id: WaveId,
    snapshot_id: CapabilitySnapshotId,
    policy_revision: int,
) -> OwnershipRefusal | None:
    if tx.read_policy_revision(wave_id) != policy_revision:
        return _refuse(RefusalCode.STALE_POLICY, "wave policy revision does not match")
    if tx.read_capability(snapshot_id) is None:
        return _refuse(RefusalCode.CAPABILITY_MISSING, "capability snapshot is not stored")
    return None


def _validate_grant(
    tx: OwnershipTransaction,
    evidence: AcceptedProcessEvidence,
    grant: StoredGrant | None,
    *,
    wave_id: WaveId,
    role_id: RoleId,
    purpose: GrantPurpose,
    policy_revision: int,
    clock: Clock,
    authorized_by: CoordinatorGenerationId | None = None,
    target_owner: RoleOwner | None = None,
) -> OwnershipRefusal | None:
    if grant is None:
        return _refuse(RefusalCode.GRANT_MISSING, "one-use grant is absent")
    if grant.created_store_revision > tx.base_store_revision:
        return _refuse(RefusalCode.GRANT_NOT_PREEXISTING, "grant was not durable before claimant transaction")
    if grant.consumed:
        return _refuse(RefusalCode.GRANT_CONSUMED, "one-use grant was already consumed")
    now = clock.now_utc()
    if now < grant.not_before or now >= grant.expires_at:
        return _refuse(RefusalCode.GRANT_EXPIRED, "grant is outside its validity window")
    if (
        grant.wave_id != wave_id
        or grant.role_id != role_id
        or grant.thread_id != evidence.observation.thread_id
        or grant.purpose is not purpose
        or grant.policy_revision != policy_revision
        or (authorized_by is not None and grant.authorized_by != authorized_by)
    ):
        return _refuse(RefusalCode.GRANT_MISMATCH, "stored grant does not match requested registration")
    if target_owner is None:
        if grant.target_owner_generation is not None or grant.target_owner_version is not None:
            return _refuse(RefusalCode.GRANT_MISMATCH, "new registration grant unexpectedly targets an owner")
    elif (
        grant.target_owner_generation != target_owner.generation_id
        or grant.target_owner_version != target_owner.record_version
    ):
        return _refuse(RefusalCode.GRANT_MISMATCH, "grant targets a stale owner generation or version")
    return None


def prepare_owner_change(
    tx: OwnershipTransaction,
    evidence: AcceptedProcessEvidence,
    intent: OwnerChangeIntent,
    process_probe: HostProcessProbe,
    ids: IdFactory,
    clock: Clock,
) -> PreparedOwnerChange | OwnershipRefusal:
    """Prepare one owner CAS without staging or committing it."""

    _require_evidence_transaction(tx, evidence)
    if isinstance(intent, RebriefOwner):
        expected = intent.expected
        if expected.assignment is not None or expected.claim_id is not None:
            return _refuse(
                RefusalCode.STALE_ASSIGNMENT,
                "policy rebrief cannot imply assignment or claim acknowledgement",
            )
        current = tx.read_owner(expected.wave_id, expected.role_id)
        if current is None:
            return _refuse(RefusalCode.OWNER_MISSING, "policy rebrief requires a current owner")
        comparisons = (
            (current.record_version == expected.owner_record_version, RefusalCode.STALE_OWNER_VERSION),
            (current.thread_id == expected.thread_id, RefusalCode.OWNER_MISMATCH),
            (current.generation_id == expected.generation_id, RefusalCode.STALE_OWNER_GENERATION),
            (current.capability_snapshot_id == expected.capability_snapshot_id, RefusalCode.STALE_CAPABILITY),
            (current.policy_revision == expected.policy_revision, RefusalCode.STALE_POLICY),
            (
                evidence.observation.thread_id == current.thread_id
                and evidence.observation.process == current.process,
                RefusalCode.OWNER_MISMATCH,
            ),
            (
                tx.read_policy_revision(expected.wave_id) == intent.new_policy_revision,
                RefusalCode.STALE_POLICY,
            ),
        )
        for matched, code in comparisons:
            if not matched:
                return _refuse(code, "policy rebrief compare value changed")
        replacement = replace(
            current,
            policy_revision=intent.new_policy_revision,
            record_version=current.record_version + 1,
        )
        return PreparedOwnerChange(tx.transaction_id, current.record_version, replacement, None, None)
    if isinstance(intent, UpdateCapability):
        checked = check_owner(tx, evidence, intent.expected)
        if not checked.allowed:
            assert checked.refusal is not None
            return checked.refusal
        assert checked.owner is not None
        if tx.read_capability(intent.capability_snapshot_id) is None:
            return _refuse(RefusalCode.CAPABILITY_MISSING, "new capability snapshot is not stored")
        replacement = replace(
            checked.owner,
            capability_snapshot_id=intent.capability_snapshot_id,
            record_version=checked.owner.record_version + 1,
        )
        return PreparedOwnerChange(tx.transaction_id, checked.owner.record_version, replacement, None, None)

    current = tx.read_owner(intent.wave_id, intent.role_id)
    validation = _validate_capability_and_policy(
        tx, intent.wave_id, intent.capability_snapshot_id, intent.policy_revision
    )
    if validation is not None:
        return validation

    consumed_grant = None
    fresh_liveness = None
    expected_version = None
    if isinstance(intent, RegisterOwner):
        if current is not None:
            if (
                current.thread_id == evidence.observation.thread_id
                and current.process == evidence.observation.process
                and current.capability_snapshot_id == intent.capability_snapshot_id
                and current.policy_revision == intent.policy_revision
            ):
                return PreparedOwnerChange(tx.transaction_id, current.record_version, current, None, None)
            return _refuse(RefusalCode.OWNER_EXISTS, "role already has a different current owner")
        grant = tx.read_preexisting_grant(intent.grant_id)
        refusal = _validate_grant(
            tx,
            evidence,
            grant,
            wave_id=intent.wave_id,
            role_id=intent.role_id,
            purpose=GrantPurpose.REGISTER,
            policy_revision=intent.policy_revision,
            clock=clock,
        )
        if refusal is not None:
            return refusal
        consumed_grant = intent.grant_id
    else:
        if current is None:
            return _refuse(RefusalCode.OWNER_MISSING, "replacement requires a current owner")
        if current.record_version != intent.expected_owner_version:
            return _refuse(RefusalCode.STALE_OWNER_VERSION, "owner version changed before replacement")
        if current.generation_id != intent.expected_generation:
            return _refuse(RefusalCode.STALE_OWNER_GENERATION, "owner generation changed before replacement")
        expected_version = current.record_version
        if isinstance(intent, ReplaceDeadOwner):
            fresh_liveness = _fresh_liveness_in_transaction(tx, current.process, process_probe)
            if fresh_liveness is Liveness.ALIVE:
                return _refuse(RefusalCode.OWNER_LIVE, "current process generation is still alive")
            if fresh_liveness is Liveness.UNKNOWN:
                return _refuse(
                    RefusalCode.OWNER_LIVENESS_UNKNOWN,
                    "current process generation cannot be proven dead",
                )
        elif isinstance(intent, AuthorizedTakeover):
            coordinator = tx.read_owner(intent.wave_id, RoleId("coordinator"))
            if coordinator is None:
                return _refuse(RefusalCode.OWNER_MISSING, "takeover authorizer is absent")
            current_coordinator_generation = CoordinatorGenerationId(coordinator.generation_id.value)
            if current_coordinator_generation != intent.expected_coordinator_generation:
                return _refuse(RefusalCode.STALE_OWNER_GENERATION, "takeover authorizer generation changed")
            grant = tx.read_preexisting_grant(intent.grant_id)
            refusal = _validate_grant(
                tx,
                evidence,
                grant,
                wave_id=intent.wave_id,
                role_id=intent.role_id,
                purpose=GrantPurpose.TAKEOVER,
                policy_revision=intent.policy_revision,
                clock=clock,
                authorized_by=intent.expected_coordinator_generation,
                target_owner=current,
            )
            if refusal is not None:
                return refusal
            consumed_grant = intent.grant_id
        elif isinstance(intent, RecoverCoordinator):
            current_coordinator_generation = CoordinatorGenerationId(current.generation_id.value)
            grant = tx.read_preexisting_grant(intent.grant_id)
            refusal = _validate_grant(
                tx,
                evidence,
                grant,
                wave_id=intent.wave_id,
                role_id=intent.role_id,
                purpose=GrantPurpose.COORDINATOR_RECOVERY,
                policy_revision=intent.policy_revision,
                clock=clock,
                authorized_by=current_coordinator_generation,
                target_owner=current,
            )
            if refusal is not None:
                return refusal
            consumed_grant = intent.grant_id

    replacement = RoleOwner(
        wave_id=intent.wave_id,
        role_id=intent.role_id,
        thread_id=evidence.observation.thread_id,
        generation_id=ids.new_owner_generation_id(),
        process=evidence.observation.process,
        capability_snapshot_id=intent.capability_snapshot_id,
        policy_revision=intent.policy_revision,
        record_version=1 if current is None else current.record_version + 1,
    )
    return PreparedOwnerChange(
        transaction_id=tx.transaction_id,
        expected_owner_version=expected_version,
        replacement=replacement,
        consumed_grant_id=consumed_grant,
        fresh_liveness=fresh_liveness,
    )


def provision_wave_bootstrap(
    tx: BootstrapTransaction, request: BootstrapRequest
) -> PreparedBootstrap | OwnershipRefusal:
    if not tx.is_active:
        raise TransactionClosedError("bootstrap requires an active transaction")
    if tx.administrative_entry != "bootstrap":
        return _refuse(RefusalCode.ADMINISTRATIVE_ENTRY_MISMATCH, "bootstrap entry is required")
    if tx.wave_exists(request.wave_id):
        return _refuse(RefusalCode.WAVE_EXISTS, "wave already exists")
    if request.policy_revision < 1 or len({grant.role_id for grant in request.grants}) != len(request.grants):
        return _refuse(RefusalCode.GRANT_MISMATCH, "bootstrap roles and policy must be canonical")
    if any(
        grant.purpose is not GrantPurpose.REGISTER or grant.expires_at <= request.created_at
        for grant in request.grants
    ):
        return _refuse(RefusalCode.GRANT_MISMATCH, "bootstrap grants must be future register grants")
    return PreparedBootstrap(tx.transaction_id, request)


def provision_recovery_delegation(
    tx: BootstrapTransaction, request: RecoveryDelegationRequest
) -> PreparedRecoveryDelegation | OwnershipRefusal:
    if not tx.is_active:
        raise TransactionClosedError("recovery delegation requires an active transaction")
    if tx.administrative_entry != "recovery":
        return _refuse(RefusalCode.ADMINISTRATIVE_ENTRY_MISMATCH, "recovery entry is required")
    if not tx.wave_exists(request.wave_id):
        return _refuse(RefusalCode.WAVE_MISSING, "wave does not exist")
    coordinator = tx.read_owner(request.wave_id, RoleId("coordinator"))
    if coordinator is None:
        return _refuse(RefusalCode.OWNER_MISSING, "current coordinator is absent")
    current_generation = CoordinatorGenerationId(coordinator.generation_id.value)
    if current_generation != request.expected_coordinator_generation:
        return _refuse(RefusalCode.STALE_OWNER_GENERATION, "coordinator generation changed")
    if coordinator.record_version != request.expected_coordinator_version:
        return _refuse(RefusalCode.STALE_OWNER_VERSION, "coordinator record version changed")
    if request.expires_at <= request.created_at:
        return _refuse(RefusalCode.GRANT_EXPIRED, "recovery delegation expiry must follow creation")
    return PreparedRecoveryDelegation(tx.transaction_id, request)


__all__ = [
    "check_liveness",
    "check_owner",
    "evaluate_assignment_capabilities",
    "prepare_owner_change",
    "provision_recovery_delegation",
    "provision_wave_bootstrap",
]
