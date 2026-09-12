"""Validated append service and mechanical native-wave transition reducer."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from typing import Any

from .claims import prepare_claim_change, prepare_claim_reconciliation
from .cursors import advance_cursor
from .event_types import (
    AppendReceipt,
    AssignmentState,
    CanonicalRecord,
    CursorState,
    DurableEvent,
    EventDisposition,
    EventId,
    EventKind,
    EventPage,
    EventValidationError,
    NativeCommand,
    PolicyRevisionChange,
    canonical_json_bytes,
    canonical_record,
    command_from_bytes,
    digest_bytes,
    receipt_from_bytes,
)
from .identity import accept_process_evidence, observe_self
from .ports import Clock, HostProcessProbe, IdFactory
from .registry import (
    check_owner,
    evaluate_assignment_capabilities,
    prepare_owner_change,
    provision_recovery_delegation,
    provision_wave_bootstrap,
)
from .replay import CursorRow, ProjectionRow, ProjectionSnapshot, recover_scan_page, replay_scan_cursor
from .storage import SQLiteTransaction, SQLiteWaveStore
from .types import (
    AssignmentRef,
    AuthorizedTakeover,
    BootstrapRequest,
    CapabilitySnapshot,
    ClaimChangeIntent,
    ExpectedOwnerBindings,
    FinalizeClaim,
    GrantPurpose,
    LocalIdentityContext,
    MarkReconciliationRequired,
    OwnerChangeIntent,
    OwnerGenerationId,
    OwnershipRefusal,
    PreparedClaimChange,
    ProcessObservationUnavailable,
    RebindClaimIntent,
    RebriefOwner,
    RecoverCoordinator,
    RecoveryDelegationRequest,
    RegisterOwner,
    ReleaseClaim,
    ReplaceDeadOwner,
    ReserveClaim,
    RoleId,
    StoredAssignment,
    StoredGrant,
    StoredReconciliation,
    UpdateCapability,
    WaveId,
    WorktreeEvidence,
)


class EventAuthorizationError(RuntimeError):
    """A caller could not establish trusted local provenance for any write."""


class _OwnerPreparationRefused(RuntimeError):
    def __init__(self, refusal: OwnershipRefusal) -> None:
        super().__init__(refusal.detail)
        self.refusal = refusal


@dataclass(frozen=True, slots=True)
class ProjectionDecision:
    accepted: bool
    reason: str | None
    current: dict[str, Any] | None


_COORDINATOR_KINDS = frozenset(
    {
        EventKind.ASSIGNMENT_QUEUED,
        EventKind.ASSIGNMENT_REBOUND,
        EventKind.GATE_APPROVED,
        EventKind.GATE_REJECTED,
        EventKind.ASSIGNMENT_HELD,
        EventKind.ASSIGNMENT_RELEASED,
        EventKind.MERGE_CLEARED,
        EventKind.ASSIGNMENT_COMPLETED,
        EventKind.ASSIGNMENT_CANCELLED,
        EventKind.TRANSPORT_ACCEPTED,
        EventKind.EXTERNAL_MERGE_OBSERVED,
    }
)
_WORKER_KINDS = frozenset(
    {
        EventKind.ASSIGNMENT_READ,
        EventKind.ASSIGNMENT_ACCEPTED,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        EventKind.ASSIGNMENT_PR_OPEN,
        EventKind.WORKER_ACTION_SUPPRESSED,
    }
)
_NO_ASSIGNMENT_STATE_CHANGE = frozenset(
    {
        EventKind.GATE_APPROVED,
        EventKind.GATE_REJECTED,
        EventKind.MERGE_CLEARED,
        EventKind.TRANSPORT_ACCEPTED,
        EventKind.WORKER_ACTION_SUPPRESSED,
        EventKind.EXTERNAL_MERGE_OBSERVED,
    }
)
_TERMINAL_STATES = frozenset({AssignmentState.COMPLETED.value, AssignmentState.CANCELLED.value})
_TYPED_MUTATION_KINDS = frozenset(
    {
        EventKind.WAVE_BOOTSTRAPPED,
        EventKind.POLICY_REVISED,
        EventKind.RECOVERY_DELEGATED,
        EventKind.OWNER_REGISTERED,
        EventKind.OWNER_REPLACED,
        EventKind.OWNER_CAPABILITY_UPDATED,
        EventKind.OWNER_REBRIEFED,
        EventKind.CLAIM_RESERVED,
        EventKind.CLAIM_MATERIALIZED,
        EventKind.CLAIM_RECONCILE_REQUIRED,
        EventKind.CLAIM_REBOUND,
        EventKind.CLAIM_RELEASED,
        EventKind.RECONCILIATION_RECORDED,
        EventKind.CURSOR_ADVANCED,
    }
)


def _uuid_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _same_generation(left: Any, right: Any) -> bool:
    return _uuid_value(left) == _uuid_value(right)


def _assignment_key(reference: AssignmentRef) -> str:
    return str(reference.assignment_id)


def _plain_record(value: Any) -> dict[str, Any]:
    parsed = json.loads(canonical_json_bytes(value))
    if not isinstance(parsed, dict):
        raise EventValidationError("durable projection value must be an object")
    return parsed


def _require_effect(command: NativeCommand, **expected: Any) -> None:
    expected_record = canonical_record(**expected)
    if not hmac.compare_digest(canonical_json_bytes(command.effect), canonical_json_bytes(expected_record)):
        raise EventValidationError(f"{command.kind.value} effect does not match its typed mutation input")


def _owner_target(intent: OwnerChangeIntent) -> tuple[WaveId, RoleId]:
    if isinstance(intent, (UpdateCapability, RebriefOwner)):
        return intent.expected.wave_id, intent.expected.role_id
    return intent.wave_id, intent.role_id


def _owner_event_kind(intent: OwnerChangeIntent) -> EventKind:
    if isinstance(intent, RegisterOwner):
        return EventKind.OWNER_REGISTERED
    if isinstance(intent, UpdateCapability):
        return EventKind.OWNER_CAPABILITY_UPDATED
    if isinstance(intent, RebriefOwner):
        return EventKind.OWNER_REBRIEFED
    if isinstance(intent, (ReplaceDeadOwner, AuthorizedTakeover, RecoverCoordinator)):
        return EventKind.OWNER_REPLACED
    raise TypeError(f"unsupported owner intent: {type(intent).__name__}")


def _claim_event_kind(intent: ClaimChangeIntent | RebindClaimIntent) -> EventKind:
    if isinstance(intent, ReserveClaim):
        return EventKind.CLAIM_RESERVED
    if isinstance(intent, FinalizeClaim):
        return EventKind.CLAIM_MATERIALIZED
    if isinstance(intent, MarkReconciliationRequired):
        return EventKind.CLAIM_RECONCILE_REQUIRED
    if isinstance(intent, RebindClaimIntent):
        return EventKind.CLAIM_REBOUND
    if isinstance(intent, ReleaseClaim):
        return EventKind.CLAIM_RELEASED
    raise TypeError(f"unsupported claim intent: {type(intent).__name__}")


def _projection_from_binding(command: NativeCommand) -> dict[str, Any]:
    assert command.assignment is not None
    binding = command.assignment
    return {
        "assignment_digest": binding.ref.digest,
        "assignment_revision": binding.ref.revision,
        "brief_state": AssignmentState.QUEUED.value,
        "capability_requirements_digest": binding.capability_requirements.digest,
        "capability_snapshot_id": str(binding.capability_snapshot_id),
        "coordinator_generation": str(binding.coordinator_generation),
        "held_from": None,
        "held_release_conditions": None,
        "held_plan_digest": None,
        "held_pr_head": None,
        "issue": binding.issue,
        "last_event_id": str(command.event_id),
        "merge_clearance_event_id": None,
        "merge_clearance_base": None,
        "merge_clearance_head": None,
        "plan_digest": binding.plan_digest,
        "policy_revision": binding.policy_revision,
        "pr_base": binding.pr_base,
        "pr_head": binding.pr_head,
        "rebound_requires_gate": False,
        "required_evidence": [str(item.record_id) for item in binding.required_evidence],
        "state": AssignmentState.QUEUED.value,
        "worker_generation": str(binding.worker_generation),
        "worker_role": str(binding.worker_role),
        "worker_thread": str(binding.worker_thread),
    }


def _binding_matches_projection(command: NativeCommand, current: dict[str, Any]) -> bool:
    binding = command.assignment
    if binding is None:
        return False
    return (
        current["assignment_digest"] == binding.ref.digest
        and current["assignment_revision"] == binding.ref.revision
        and current["issue"] == binding.issue
        and current["policy_revision"] == binding.policy_revision
        and current["worker_role"] == str(binding.worker_role)
        and current["worker_thread"] == str(binding.worker_thread)
        and current["worker_generation"] == str(binding.worker_generation)
        and current["coordinator_generation"] == str(binding.coordinator_generation)
        and current["capability_snapshot_id"] == str(binding.capability_snapshot_id)
        and current["capability_requirements_digest"] == binding.capability_requirements.digest
        and current["required_evidence"] == [str(item.record_id) for item in binding.required_evidence]
        and (
            command.kind == EventKind.ASSIGNMENT_PR_OPEN
            or (current.get("pr_base") == binding.pr_base and current.get("pr_head") == binding.pr_head)
        )
    )


def _project_command(command: NativeCommand, current: dict[str, Any] | None) -> ProjectionDecision:
    """Apply contract-v1 mechanical state rules without policy judgment."""

    kind = command.kind
    if command.assignment is None:
        return ProjectionDecision(True, None, current)
    if kind in {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND}:
        if current is not None and kind == EventKind.ASSIGNMENT_QUEUED:
            return ProjectionDecision(False, "assignment_already_exists", current)
        if kind == EventKind.ASSIGNMENT_REBOUND:
            if current is None or current["state"] != AssignmentState.HELD.value:
                return ProjectionDecision(False, "rebind_requires_held_assignment", current)
            if command.assignment.ref.revision <= int(current["assignment_revision"]):
                return ProjectionDecision(False, "assignment_revision_not_monotonic", current)
        replacement = _projection_from_binding(command)
        if kind == EventKind.ASSIGNMENT_REBOUND:
            assert current is not None
            replacement["state"] = AssignmentState.HELD.value
            replacement["held_from"] = current["held_from"]
            replacement["held_release_conditions"] = current.get("held_release_conditions")
            replacement["held_plan_digest"] = None
            replacement["held_pr_head"] = command.assignment.pr_head
            replacement["rebound_requires_gate"] = True
        return ProjectionDecision(True, None, replacement)
    if current is None or not _binding_matches_projection(command, current):
        return ProjectionDecision(False, "assignment_binding_mismatch", current)
    if current["state"] in _TERMINAL_STATES:
        return ProjectionDecision(False, "terminal_state_cannot_regress", current)

    next_projection = dict(current)
    if kind == EventKind.ASSIGNMENT_READ:
        if current["state"] not in {AssignmentState.QUEUED.value, AssignmentState.HELD.value}:
            return ProjectionDecision(False, "read_requires_queued", current)
        if current.get("brief_state") != AssignmentState.QUEUED.value:
            return ProjectionDecision(False, "brief_already_read", current)
        next_projection["brief_state"] = AssignmentState.READ.value
        updated_state = (
            AssignmentState.READ.value
            if current["state"] == AssignmentState.QUEUED.value
            else AssignmentState.HELD.value
        )
    elif kind == EventKind.ASSIGNMENT_ACCEPTED:
        if current["state"] not in {AssignmentState.READ.value, AssignmentState.HELD.value}:
            return ProjectionDecision(False, "accept_requires_read", current)
        if current.get("brief_state") != AssignmentState.READ.value:
            return ProjectionDecision(False, "brief_not_read", current)
        next_projection["brief_state"] = AssignmentState.ACCEPTED.value
        updated_state = (
            AssignmentState.ACCEPTED.value
            if current["state"] == AssignmentState.READ.value
            else AssignmentState.HELD.value
        )
    elif kind in {EventKind.GATE_APPROVED, EventKind.GATE_REJECTED}:
        if current["state"] not in {AssignmentState.ACCEPTED.value, AssignmentState.HELD.value}:
            return ProjectionDecision(False, "gate_requires_accepted_or_held", current)
        if current.get("brief_state") != AssignmentState.ACCEPTED.value:
            return ProjectionDecision(False, "gate_requires_current_brief_acceptance", current)
        updated_state = current["state"]
        next_projection["gate_event_id"] = str(command.event_id)
        next_projection["gate_plan_digest"] = command.assignment.plan_digest
        next_projection["plan_digest"] = command.assignment.plan_digest
        next_projection["gate_verdict"] = command.payload.get("verdict")
        next_projection["gate_conditions"] = command.payload.get("conditions")
        if kind == EventKind.GATE_APPROVED:
            next_projection["rebound_requires_gate"] = False
    elif kind == EventKind.ASSIGNMENT_IMPLEMENTING:
        if current["state"] != AssignmentState.ACCEPTED.value:
            return ProjectionDecision(False, "implementing_requires_accepted", current)
        if (
            current.get("gate_verdict") != "approved"
            or current.get("gate_plan_digest") != command.assignment.plan_digest
            or current.get("gate_event_id") != str(command.correlation_id)
        ):
            return ProjectionDecision(False, "current_gate_mismatch", current)
        updated_state = AssignmentState.IMPLEMENTING.value
    elif kind == EventKind.ASSIGNMENT_PR_OPEN:
        if current["state"] != AssignmentState.IMPLEMENTING.value:
            return ProjectionDecision(False, "pr_open_requires_implementing", current)
        if command.assignment.plan_digest != current.get("gate_plan_digest"):
            return ProjectionDecision(False, "pr_open_plan_mismatch", current)
        updated_state = AssignmentState.PR_OPEN.value
        next_projection["pr_base"] = command.assignment.pr_base
        next_projection["pr_head"] = command.assignment.pr_head
        next_projection["merge_clearance_event_id"] = None
        next_projection["merge_clearance_base"] = None
        next_projection["merge_clearance_head"] = None
    elif kind == EventKind.ASSIGNMENT_HELD:
        prior = command.payload.get("resume_state")
        if prior != current["state"]:
            return ProjectionDecision(False, "hold_resume_state_mismatch", current)
        if prior in {AssignmentState.IMPLEMENTING.value, AssignmentState.PR_OPEN.value} and (
            command.assignment.plan_digest != current.get("gate_plan_digest")
        ):
            return ProjectionDecision(False, "hold_plan_mismatch", current)
        updated_state = AssignmentState.HELD.value
        next_projection["held_from"] = current["state"]
        next_projection["held_release_conditions"] = command.payload.get("conditions")
        next_projection["held_plan_digest"] = current.get("gate_plan_digest")
        next_projection["held_pr_head"] = current.get("pr_head")
    elif kind == EventKind.ASSIGNMENT_RELEASED:
        if current["state"] != AssignmentState.HELD.value:
            return ProjectionDecision(False, "release_requires_held", current)
        if current.get("brief_state") != AssignmentState.ACCEPTED.value:
            return ProjectionDecision(False, "release_requires_current_brief_acceptance", current)
        prior = command.payload.get("previous_state")
        if prior != current.get("held_from"):
            return ProjectionDecision(False, "release_state_mismatch", current)
        release_conditions = command.payload.get("conditions")
        stored_conditions = current.get("held_release_conditions")
        if not isinstance(release_conditions, tuple) or not isinstance(stored_conditions, (tuple, list)):
            return ProjectionDecision(False, "release_conditions_mismatch", current)
        if release_conditions != tuple(stored_conditions):
            return ProjectionDecision(False, "release_conditions_mismatch", current)
        if current.get("rebound_requires_gate"):
            return ProjectionDecision(False, "release_requires_fresh_gate", current)
        if prior == AssignmentState.IMPLEMENTING.value and (
            current.get("gate_verdict") != "approved"
            or current.get("gate_plan_digest") != command.assignment.plan_digest
        ):
            return ProjectionDecision(False, "release_gate_changed", current)
        if prior == AssignmentState.PR_OPEN.value and (
            current.get("gate_verdict") != "approved"
            or current.get("gate_plan_digest") != command.assignment.plan_digest
            or current.get("pr_base") != command.assignment.pr_base
            or current.get("pr_head") != command.assignment.pr_head
            or current.get("held_pr_head") != command.assignment.pr_head
        ):
            return ProjectionDecision(False, "release_pr_binding_changed", current)
        updated_state = (
            AssignmentState.ACCEPTED.value
            if prior in {AssignmentState.QUEUED.value, AssignmentState.READ.value}
            else str(prior)
        )
        next_projection["held_from"] = None
        next_projection["held_release_conditions"] = None
        next_projection["held_plan_digest"] = None
        next_projection["held_pr_head"] = None
    elif kind == EventKind.MERGE_CLEARED:
        if current["state"] != AssignmentState.PR_OPEN.value:
            return ProjectionDecision(False, "merge_clearance_requires_pr_open", current)
        if current.get("pr_head") != command.assignment.pr_head:
            return ProjectionDecision(False, "pr_head_mismatch", current)
        if current.get("pr_base") != command.assignment.pr_base:
            return ProjectionDecision(False, "pr_base_mismatch", current)
        if current.get("gate_plan_digest") != command.assignment.plan_digest:
            return ProjectionDecision(False, "merge_clearance_plan_mismatch", current)
        updated_state = current["state"]
        next_projection["merge_clearance_event_id"] = str(command.event_id)
        next_projection["merge_clearance_base"] = command.assignment.pr_base
        next_projection["merge_clearance_head"] = command.assignment.pr_head
    elif kind == EventKind.ASSIGNMENT_COMPLETED:
        if current["state"] != AssignmentState.PR_OPEN.value:
            return ProjectionDecision(False, "completion_requires_pr_open", current)
        if (
            current.get("merge_clearance_head") != command.assignment.pr_head
            or current.get("merge_clearance_base") != command.assignment.pr_base
            or current.get("pr_base") != command.assignment.pr_base
            or current.get("pr_head") != command.assignment.pr_head
            or current.get("gate_plan_digest") != command.assignment.plan_digest
        ):
            return ProjectionDecision(False, "completion_ref_not_cleared", current)
        updated_state = AssignmentState.COMPLETED.value
    elif kind == EventKind.ASSIGNMENT_CANCELLED:
        updated_state = AssignmentState.CANCELLED.value
    elif kind in _NO_ASSIGNMENT_STATE_CHANGE:
        if kind == EventKind.EXTERNAL_MERGE_OBSERVED and (
            current.get("pr_base") != command.assignment.pr_base
            or current.get("pr_head") != command.assignment.pr_head
            or current.get("gate_plan_digest") != command.assignment.plan_digest
        ):
            return ProjectionDecision(False, "observed_merge_ref_mismatch", current)
        updated_state = current["state"]
    else:
        return ProjectionDecision(False, "unsupported_assignment_transition", current)

    next_projection["state"] = updated_state
    next_projection["last_event_id"] = str(command.event_id)
    return ProjectionDecision(True, None, next_projection)


def _correlation_reason(tx: SQLiteTransaction, command: NativeCommand) -> str | None:
    if command.kind not in {
        EventKind.ASSIGNMENT_READ,
        EventKind.ASSIGNMENT_ACCEPTED,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        EventKind.ASSIGNMENT_COMPLETED,
    }:
        return None
    assert command.correlation_id is not None
    correlated = tx.lookup_event(command.wave_id, command.correlation_id)
    if correlated is None:
        return "correlation_event_missing"
    correlated_command = command_from_bytes(correlated.command_bytes)
    expected_kinds: set[EventKind] = {
        EventKind.ASSIGNMENT_READ: {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND},
        EventKind.ASSIGNMENT_ACCEPTED: {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND},
        EventKind.ASSIGNMENT_IMPLEMENTING: {EventKind.GATE_APPROVED},
        EventKind.ASSIGNMENT_COMPLETED: {EventKind.EXTERNAL_MERGE_OBSERVED},
    }[command.kind]
    if correlated_command.kind not in expected_kinds:
        return "correlation_kind_mismatch"
    correlated_receipt = receipt_from_bytes(correlated.receipt_bytes)
    expected_disposition = (
        EventDisposition.RECONCILED if command.kind == EventKind.ASSIGNMENT_COMPLETED else EventDisposition.APPLIED
    )
    if correlated_receipt.disposition != expected_disposition:
        return "correlation_event_not_successful"
    if correlated_command.assignment is None or command.assignment is None:
        return "correlation_assignment_missing"
    if correlated_command.assignment != command.assignment:
        return "correlation_assignment_mismatch"
    return None


class EventService:
    def __init__(
        self,
        store: SQLiteWaveStore,
        *,
        process_probe: HostProcessProbe,
        ids: IdFactory,
        clock: Clock,
    ) -> None:
        self.store = store
        self.process_probe = process_probe
        self.ids = ids
        self.clock = clock

    def _fresh_evidence(self, tx: SQLiteTransaction, context: LocalIdentityContext) -> Any:
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        evidence = accept_process_evidence(tx, candidate, self.process_probe)
        if isinstance(evidence, ProcessObservationUnavailable):
            raise EventAuthorizationError(evidence.detail)
        return evidence

    @staticmethod
    def _history_allowed(tx: SQLiteTransaction, wave_id: WaveId, evidence: Any) -> bool:
        thread_id = evidence.observation.thread_id
        if tx.participant_exists(wave_id, thread_id):
            return True
        coordinator = tx.read_owner(wave_id, RoleId("coordinator"))
        return (
            coordinator is not None
            and coordinator.thread_id == thread_id
            and coordinator.process == evidence.observation.process
        )

    @staticmethod
    def _conflict_receipt(command: NativeCommand) -> AppendReceipt:
        return AppendReceipt(
            wave_id=command.wave_id,
            event_id=command.event_id,
            command_digest=command.payload_digest(),
            disposition=EventDisposition.REJECTED,
            reason="event_id_payload_conflict",
            sequence=None,
            event_digest=None,
            committed_at=None,
        )

    def _existing_receipt(
        self,
        tx: SQLiteTransaction,
        command: NativeCommand,
        evidence: Any,
    ) -> AppendReceipt | None:
        if not self._history_allowed(tx, command.wave_id, evidence):
            raise EventAuthorizationError("historical receipt is not available to this participant")
        existing = tx.lookup_event(command.wave_id, command.event_id)
        if existing is None:
            return None
        if not hmac.compare_digest(existing.command_bytes, command.canonical_bytes()):
            return self._conflict_receipt(command)
        return receipt_from_bytes(existing.receipt_bytes)

    def get_receipt(
        self,
        wave_id: WaveId,
        event_id: EventId,
        context: LocalIdentityContext,
    ) -> AppendReceipt | None:
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            if not self._history_allowed(tx, wave_id, evidence):
                raise EventAuthorizationError("historical receipt is not available to this participant")
            existing = tx.lookup_event(wave_id, event_id)
            if existing is None:
                return None
            return receipt_from_bytes(existing.receipt_bytes)

    def _owner_refusal(self, tx: SQLiteTransaction, command: NativeCommand, evidence: Any) -> str | None:
        owner = tx.read_owner(command.wave_id, command.actor.role_id)
        if owner is None:
            return "owner_missing"
        expected = ExpectedOwnerBindings(
            wave_id=command.wave_id,
            role_id=command.actor.role_id,
            thread_id=command.actor.thread_id,
            generation_id=OwnerGenerationId(_uuid_value(command.actor.generation_id)),
            capability_snapshot_id=owner.capability_snapshot_id,
            policy_revision=owner.policy_revision,
            owner_record_version=owner.record_version,
            assignment=None,
        )
        result = check_owner(tx, evidence, expected)
        if result.allowed:
            return None
        assert result.refusal is not None
        return result.refusal.code.value

    def _assignment_refusal(self, tx: SQLiteTransaction, command: NativeCommand) -> str | None:
        binding = command.assignment
        if binding is None:
            return None
        if tx.read_policy_revision(command.wave_id) != binding.policy_revision:
            return "stale_policy"
        coordinator = tx.read_owner(command.wave_id, RoleId("coordinator"))
        if coordinator is None or not _same_generation(coordinator.generation_id, binding.coordinator_generation):
            return "stale_coordinator_generation"
        worker = tx.read_owner(command.wave_id, binding.worker_role)
        if (
            worker is None
            or worker.thread_id != binding.worker_thread
            or worker.generation_id != binding.worker_generation
        ):
            return "stale_worker_generation"
        if command.kind in {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND}:
            if worker.capability_snapshot_id != binding.capability_snapshot_id:
                return "stale_capability"
            snapshot = tx.read_capability(worker.capability_snapshot_id)
            if snapshot is None:
                return "capability_missing"
            proposed = StoredAssignment(
                assignment=binding.ref,
                wave_id=command.wave_id,
                role_id=binding.worker_role,
                owner_generation_id=binding.worker_generation,
                capability_snapshot_id=binding.capability_snapshot_id,
                capability_requirements=binding.capability_requirements,
                required_evidence=binding.required_evidence,
                policy_revision=binding.policy_revision,
                acknowledged=False,
            )
            if not evaluate_assignment_capabilities(snapshot, proposed).satisfied:
                return "capability_requirements_unsatisfied"
            return None
        stored = tx.read_assignment(binding.ref)
        if stored is None:
            return "assignment_missing"
        if (
            stored.wave_id != command.wave_id
            or stored.role_id != binding.worker_role
            or stored.owner_generation_id != binding.worker_generation
            or stored.capability_snapshot_id != binding.capability_snapshot_id
            or stored.capability_requirements != binding.capability_requirements
            or stored.required_evidence != binding.required_evidence
            or stored.policy_revision != binding.policy_revision
        ):
            return "assignment_binding_mismatch"
        if command.kind in {EventKind.ASSIGNMENT_HELD, EventKind.ASSIGNMENT_CANCELLED}:
            return None
        snapshot = tx.read_capability(worker.capability_snapshot_id)
        if snapshot is None:
            return "capability_missing"
        requirements = evaluate_assignment_capabilities(snapshot, stored)
        if not requirements.satisfied:
            return "capability_requirements_unsatisfied"
        return None

    def _append_refusal(
        self,
        tx: SQLiteTransaction,
        command: NativeCommand,
        refusal: OwnershipRefusal,
    ) -> AppendReceipt:
        return self._append_rejected_reason(tx, command, refusal.code.value)

    def _append_rejected_reason(
        self,
        tx: SQLiteTransaction,
        command: NativeCommand,
        reason: str,
    ) -> AppendReceipt:
        receipt = tx.append_event(
            command,
            disposition=EventDisposition.REJECTED,
            reason=reason,
            validation_facts=canonical_record(refusal_code=reason),
            committed_at=self.clock.now_utc(),
        )
        tx.commit()
        return receipt

    @staticmethod
    def _actor_refusal(command: NativeCommand) -> str | None:
        if command.kind in _COORDINATOR_KINDS and str(command.actor.role_id) != "coordinator":
            return "coordinator_authority_required"
        if command.kind in _WORKER_KINDS:
            assert command.assignment is not None
            if (
                command.actor.role_id != command.assignment.worker_role
                or command.actor.thread_id != command.assignment.worker_thread
                or not _same_generation(command.actor.generation_id, command.assignment.worker_generation)
            ):
                return "assigned_worker_authority_required"
        return None

    def append(self, command: NativeCommand, context: LocalIdentityContext) -> AppendReceipt:
        if command.kind in _TYPED_MUTATION_KINDS:
            raise EventValidationError(f"{command.kind.value} requires its typed atomic mutation entrypoint")
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            existing = self._existing_receipt(tx, command, evidence)
            if existing is not None:
                return existing
            if not tx.participant_exists(command.wave_id, evidence.observation.thread_id):
                raise EventAuthorizationError("new events require a recorded wave participant")
            reason = self._owner_refusal(tx, command, evidence)
            reason = reason or self._actor_refusal(command)
            reason = reason or self._assignment_refusal(tx, command)
            reason = reason or _correlation_reason(tx, command)
            current = None
            if command.assignment is not None:
                current = tx.get_projection(command.wave_id, "assignment", _assignment_key(command.assignment.ref))
            decision = (
                _project_command(command, current) if reason is None else ProjectionDecision(False, reason, current)
            )
            if not decision.accepted:
                receipt = tx.append_event(
                    command,
                    disposition=EventDisposition.REJECTED,
                    reason=decision.reason,
                    validation_facts=self._validation_facts(tx, command),
                    committed_at=self.clock.now_utc(),
                )
                tx.commit()
                return receipt
            disposition = (
                EventDisposition.OBSERVED
                if command.kind
                in {EventKind.TRANSPORT_ACCEPTED, EventKind.WORKER_ACTION_SUPPRESSED, EventKind.PROSE_MESSAGE}
                else EventDisposition.RECONCILED
                if command.kind == EventKind.EXTERNAL_MERGE_OBSERVED
                else EventDisposition.APPLIED
            )
            receipt = tx.append_event(
                command,
                disposition=disposition,
                reason=None,
                validation_facts=self._validation_facts(tx, command),
                committed_at=self.clock.now_utc(),
            )
            self._apply_accepted(tx, command, decision.current, receipt)
            tx.commit()
            return receipt

    @staticmethod
    def _validation_facts(tx: SQLiteTransaction, command: NativeCommand) -> CanonicalRecord:
        owner = tx.read_owner(command.wave_id, command.actor.role_id)
        return CanonicalRecord.from_mapping(
            {
                "actor_generation": str(command.actor.generation_id),
                "assignment_digest": command.assignment.ref.digest if command.assignment else None,
                "owner_record_version": owner.record_version if owner else None,
                "policy_revision": tx.policy_revision(command.wave_id),
                "transaction_id": str(tx.transaction_id),
            }
        )

    def _apply_accepted(
        self,
        tx: SQLiteTransaction,
        command: NativeCommand,
        projection: dict[str, Any] | None,
        receipt: AppendReceipt,
    ) -> None:
        assert receipt.sequence is not None
        if command.assignment is not None and projection is not None:
            tx.put_projection(
                command.wave_id,
                "assignment",
                _assignment_key(command.assignment.ref),
                projection,
                receipt.sequence,
            )
        if command.kind in {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND}:
            assert command.assignment is not None
            binding = command.assignment
            tx.stage_assignment(
                StoredAssignment(
                    assignment=binding.ref,
                    wave_id=command.wave_id,
                    role_id=binding.worker_role,
                    owner_generation_id=binding.worker_generation,
                    capability_snapshot_id=binding.capability_snapshot_id,
                    capability_requirements=binding.capability_requirements,
                    required_evidence=binding.required_evidence,
                    policy_revision=binding.policy_revision,
                    acknowledged=False,
                )
            )
        elif command.kind == EventKind.ASSIGNMENT_ACCEPTED:
            assert command.assignment is not None
            tx.set_assignment_acknowledged(command.assignment.ref)
        if command.kind == EventKind.ASSIGNMENT_READ:
            assert command.assignment is not None and command.correlation_id is not None
            current = tx.read_cursor(
                command.wave_id,
                command.assignment.worker_role,
                command.assignment.worker_thread,
                command.assignment.worker_generation,
            ) or CursorState(
                wave_id=command.wave_id,
                role_id=command.assignment.worker_role,
                thread_id=command.assignment.worker_thread,
                generation_id=command.assignment.worker_generation,
            )
            correlated = tx.lookup_event(command.wave_id, command.correlation_id)
            assert correlated is not None
            correlated_receipt = receipt_from_bytes(correlated.receipt_bytes)
            assert correlated_receipt.sequence is not None
            cursor = advance_cursor(
                current,
                observed_sequences=(correlated_receipt.sequence, receipt.sequence),
                scanned_through=receipt.sequence,
            )
            tx.put_cursor(cursor, receipt.sequence)

    def scan_and_advance(
        self,
        command: NativeCommand,
        context: LocalIdentityContext,
    ) -> tuple[AppendReceipt, EventPage]:
        """Commit one scan, or recover its original response without advancing again."""

        if command.kind != EventKind.CURSOR_ADVANCED:
            raise EventValidationError("cursor scan requires cursor.advanced command")
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            generation = OwnerGenerationId(_uuid_value(command.actor.generation_id))
            current = tx.read_cursor(
                command.wave_id,
                command.actor.role_id,
                command.actor.thread_id,
                generation,
            ) or CursorState(
                command.wave_id,
                command.actor.role_id,
                command.actor.thread_id,
                generation,
            )
            existing = self._existing_receipt(tx, command, evidence)
            if existing is not None:
                if existing.disposition == EventDisposition.APPLIED:
                    return existing, recover_scan_page(tx, command.wave_id, command.event_id)
                return existing, EventPage((), current.highest_contiguous, current)
            reason = self._owner_refusal(tx, command, evidence)
            if reason is not None:
                receipt = self._append_rejected_reason(tx, command, reason)
                return receipt, EventPage((), current.highest_contiguous, current)
            target = command.payload.get("cursor_highest_contiguous")
            if isinstance(target, bool) or not isinstance(target, int):
                raise EventValidationError("cursor target must be an integer")
            span = target - current.highest_contiguous
            if span <= 0:
                raise EventValidationError("cursor scan target must advance")
            page = tx.read_event_page(
                command.wave_id,
                after_sequence=current.highest_contiguous,
                limit=span,
            )
            if len(page) != span or page[-1].sequence != target:
                raise EventValidationError("cursor scan target exceeds the committed journal")
            next_cursor = advance_cursor(
                current,
                observed_sequences=(event.sequence for event in page),
                scanned_through=target,
            )
            supplied_sparse = command.payload.get("cursor_sparse")
            if supplied_sparse != next_cursor.sparse_sequences:
                raise EventValidationError("cursor command sparse set differs from scanned journal")
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(cursor=next_cursor, scan_after_sequence=current.highest_contiguous),
                committed_at=self.clock.now_utc(),
            )
            assert receipt.sequence is not None
            tx.put_cursor(next_cursor, receipt.sequence)
            tx.commit()
            return receipt, EventPage(page, target, next_cursor)

    def bootstrap(self, command: NativeCommand, request: BootstrapRequest) -> AppendReceipt:
        if command.kind != EventKind.WAVE_BOOTSTRAPPED or command.wave_id != request.wave_id:
            raise ValueError("bootstrap command/request mismatch")
        with self.store.transaction(administrative_entry="bootstrap") as tx:
            existing = tx.lookup_event(command.wave_id, command.event_id)
            if existing is not None:
                if not hmac.compare_digest(existing.command_bytes, command.canonical_bytes()):
                    return self._conflict_receipt(command)
                return receipt_from_bytes(existing.receipt_bytes)
            _require_effect(command, request=request)
            prepared = provision_wave_bootstrap(tx, request)
            if isinstance(prepared, OwnershipRefusal):
                raise EventAuthorizationError(prepared.detail)
            grants = tuple(
                StoredGrant(
                    grant_id=spec.grant_id,
                    wave_id=request.wave_id,
                    role_id=spec.role_id,
                    thread_id=spec.thread_id,
                    purpose=spec.purpose,
                    policy_revision=request.policy_revision,
                    created_store_revision=tx.base_store_revision + 1,
                    not_before=request.created_at,
                    expires_at=spec.expires_at,
                    consumed=False,
                )
                for spec in request.grants
            )
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(
                    administrative_entry="bootstrap",
                    created_store_revision=tx.base_store_revision + 1,
                    grants=grants,
                    request=request,
                ),
                committed_at=self.clock.now_utc(),
            )
            tx.stage_bootstrap(prepared)
            assert receipt.sequence is not None
            tx.put_projection(
                request.wave_id,
                "wave",
                str(request.wave_id),
                _plain_record(request),
                receipt.sequence,
            )
            for grant in grants:
                tx.put_projection(
                    request.wave_id,
                    "grant",
                    str(grant.grant_id),
                    _plain_record(grant),
                    receipt.sequence,
                )
            tx.commit()
            return receipt

    def append_policy_revision(
        self,
        command: NativeCommand,
        context: LocalIdentityContext,
        change: PolicyRevisionChange,
    ) -> AppendReceipt:
        if command.kind != EventKind.POLICY_REVISED or str(command.actor.role_id) != "coordinator":
            raise EventValidationError("policy revision requires a coordinator policy.revised command")
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            existing = self._existing_receipt(tx, command, evidence)
            if existing is not None:
                return existing
            _require_effect(command, change=change)
            reason = self._owner_refusal(tx, command, evidence)
            if reason is not None:
                return self._append_rejected_reason(tx, command, reason)
            if tx.read_policy_revision(command.wave_id) != change.expected_revision:
                return self._append_rejected_reason(tx, command, "stale_policy")
            wave_projection = tx.get_projection(command.wave_id, "wave", str(command.wave_id))
            if wave_projection is None:
                raise EventAuthorizationError("wave projection is missing")
            replacement = dict(wave_projection)
            replacement["policy_revision"] = change.new_revision
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(change=change),
                committed_at=self.clock.now_utc(),
            )
            tx.stage_policy_revision(command.wave_id, change.expected_revision, change.new_revision)
            assert receipt.sequence is not None
            tx.put_projection(
                command.wave_id,
                "wave",
                str(command.wave_id),
                replacement,
                receipt.sequence,
            )
            tx.commit()
            return receipt

    def append_reconciliation(
        self,
        command: NativeCommand,
        context: LocalIdentityContext,
        reconciliation: StoredReconciliation,
    ) -> AppendReceipt:
        if (
            command.kind != EventKind.RECONCILIATION_RECORDED
            or command.wave_id != reconciliation.wave_id
            or str(command.actor.role_id) != "coordinator"
            or not _same_generation(
                command.actor.generation_id,
                reconciliation.coordinator_generation,
            )
        ):
            raise EventValidationError("reconciliation requires a matching coordinator command")
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            existing = self._existing_receipt(tx, command, evidence)
            if existing is not None:
                return existing
            _require_effect(command, reconciliation=reconciliation)
            if command.payload.get("reconciliation_ref") != reconciliation.record.digest:
                raise EventValidationError("reconciliation command reference differs from its record")
            reason = self._owner_refusal(tx, command, evidence)
            if reason is not None:
                return self._append_rejected_reason(tx, command, reason)
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(reconciliation=reconciliation),
                committed_at=self.clock.now_utc(),
            )
            tx.stage_reconciliation(reconciliation)
            assert receipt.sequence is not None
            tx.put_projection(
                command.wave_id,
                "reconciliation",
                str(reconciliation.record.record_id),
                _plain_record(reconciliation),
                receipt.sequence,
            )
            tx.commit()
            return receipt

    def delegate_recovery(
        self,
        command: NativeCommand,
        context: LocalIdentityContext,
        request: RecoveryDelegationRequest,
    ) -> AppendReceipt:
        if command.kind != EventKind.RECOVERY_DELEGATED or command.wave_id != request.wave_id:
            raise ValueError("recovery command/request mismatch")
        if str(command.actor.role_id) != "coordinator" or not _same_generation(
            command.actor.generation_id, request.expected_coordinator_generation
        ):
            raise EventValidationError("recovery command actor does not match the expected coordinator")
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction(administrative_entry="recovery") as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            existing = self._existing_receipt(tx, command, evidence)
            if existing is not None:
                return existing
            _require_effect(command, request=request)
            if str(command.payload.get("grant_id")) != str(request.grant_id):
                raise EventValidationError("recovery command grant differs from its request")
            reason = self._owner_refusal(tx, command, evidence)
            if reason is not None:
                return self._append_rejected_reason(tx, command, reason)
            prepared = provision_recovery_delegation(tx, request)
            if isinstance(prepared, OwnershipRefusal):
                raise EventAuthorizationError(prepared.detail)
            coordinator = tx.read_owner(request.wave_id, RoleId("coordinator"))
            assert coordinator is not None
            grant = StoredGrant(
                grant_id=request.grant_id,
                wave_id=request.wave_id,
                role_id=RoleId("coordinator"),
                thread_id=request.successor_thread_id,
                purpose=GrantPurpose.COORDINATOR_RECOVERY,
                policy_revision=tx.read_policy_revision(request.wave_id),
                created_store_revision=tx.base_store_revision + 1,
                not_before=request.created_at,
                expires_at=request.expires_at,
                consumed=False,
                authorized_by=request.expected_coordinator_generation,
                target_owner_generation=coordinator.generation_id,
                target_owner_version=coordinator.record_version,
            )
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(administrative_entry="recovery", grant=grant),
                committed_at=self.clock.now_utc(),
            )
            tx.stage_recovery_delegation(prepared)
            assert receipt.sequence is not None
            tx.put_projection(
                request.wave_id,
                "grant",
                str(grant.grant_id),
                _plain_record(grant),
                receipt.sequence,
            )
            tx.commit()
            return receipt

    def append_owner_change(
        self,
        command: NativeCommand,
        context: LocalIdentityContext,
        intent: OwnerChangeIntent,
        snapshot: CapabilitySnapshot | None = None,
    ) -> AppendReceipt:
        wave_id, role_id = _owner_target(intent)
        if command.wave_id != wave_id or command.kind != _owner_event_kind(intent):
            raise EventValidationError("owner command kind/wave does not match its intent")
        if command.actor.role_id != role_id:
            raise EventValidationError("owner command actor role does not match its intent")
        if isinstance(intent, RebriefOwner):
            if snapshot is not None:
                raise EventValidationError("policy rebrief cannot carry a capability snapshot")
        else:
            if snapshot is None:
                raise EventValidationError("owner change requires its immutable capability snapshot")
            snapshot_id = intent.capability_snapshot_id
            if snapshot.snapshot_id != snapshot_id:
                raise EventValidationError("owner intent and capability snapshot differ")
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            participant = self._history_allowed(tx, command.wave_id, evidence)
            if participant:
                existing = self._existing_receipt(tx, command, evidence)
                if existing is not None:
                    return existing
            if command.actor.thread_id != evidence.observation.thread_id:
                raise EventAuthorizationError("owner command actor thread does not match fresh process evidence")
            if isinstance(intent, RebriefOwner):
                _require_effect(command, intent=intent)
            else:
                assert snapshot is not None
                _require_effect(command, intent=intent, snapshot=snapshot)
            intent_grant = getattr(intent, "grant_id", None)
            payload_grant = command.payload.get("grant_id")
            if (payload_grant is None) != (intent_grant is None) or (
                intent_grant is not None and str(payload_grant) != str(intent_grant)
            ):
                raise EventValidationError("owner command grant differs from its intent")
            try:
                with tx.savepoint():
                    if snapshot is not None:
                        tx.stage_capability(snapshot)
                    prepared = prepare_owner_change(
                        tx,
                        evidence,
                        intent,
                        self.process_probe,
                        self.ids,
                        self.clock,
                    )
                    if isinstance(prepared, OwnershipRefusal):
                        raise _OwnerPreparationRefused(prepared)
            except _OwnerPreparationRefused as rejected:
                if not participant:
                    raise EventAuthorizationError(rejected.refusal.detail) from rejected
                return self._append_refusal(tx, command, rejected.refusal)
            if not _same_generation(command.actor.generation_id, prepared.replacement.generation_id):
                raise EventValidationError("owner command generation does not match the prepared replacement")
            if not participant:
                existing = tx.lookup_event(command.wave_id, command.event_id)
                if existing is not None:
                    if not hmac.compare_digest(existing.command_bytes, command.canonical_bytes()):
                        return self._conflict_receipt(command)
                    return receipt_from_bytes(existing.receipt_bytes)
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(
                    consumed_grant_id=prepared.consumed_grant_id,
                    fresh_liveness=prepared.fresh_liveness,
                    owner=prepared.replacement,
                    snapshot=snapshot,
                ),
                committed_at=self.clock.now_utc(),
            )
            tx.stage_owner_change(prepared)
            assert receipt.sequence is not None
            tx.put_projection(
                command.wave_id,
                "owner",
                str(prepared.replacement.role_id),
                _plain_record(prepared.replacement),
                receipt.sequence,
            )
            if snapshot is not None:
                tx.put_projection(
                    command.wave_id,
                    "capability",
                    str(snapshot.snapshot_id),
                    _plain_record(snapshot),
                    receipt.sequence,
                )
            if prepared.consumed_grant_id is not None:
                grant = tx.read_preexisting_grant(prepared.consumed_grant_id)
                assert grant is not None
                tx.put_projection(
                    command.wave_id,
                    "grant",
                    str(grant.grant_id),
                    _plain_record(grant),
                    receipt.sequence,
                )
            tx.commit()
            return receipt

    def append_claim_change(
        self,
        command: NativeCommand,
        context: LocalIdentityContext,
        intent: ClaimChangeIntent | RebindClaimIntent,
        worktree: WorktreeEvidence | None,
    ) -> AppendReceipt:
        candidate = observe_self(context, self.process_probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise EventAuthorizationError(candidate.detail)
        with self.store.transaction() as tx:
            evidence = accept_process_evidence(tx, candidate, self.process_probe)
            if isinstance(evidence, ProcessObservationUnavailable):
                raise EventAuthorizationError(evidence.detail)
            existing = self._existing_receipt(tx, command, evidence)
            if existing is not None:
                return existing
            if command.actor.thread_id != evidence.observation.thread_id:
                raise EventAuthorizationError("claim command actor thread does not match fresh process evidence")
            if command.kind != _claim_event_kind(intent):
                raise EventValidationError("claim command kind does not match its intent")
            _require_effect(command, intent=intent, worktree=worktree)
            supplied_worktree_digest = command.payload.get("worktree_evidence_digest")
            expected_worktree_digest = digest_bytes(canonical_json_bytes(worktree)) if worktree is not None else None
            if supplied_worktree_digest is not None and supplied_worktree_digest != expected_worktree_digest:
                raise EventValidationError("claim command worktree digest differs from its evidence")
            if isinstance(intent, RebindClaimIntent):
                if worktree is None or command.kind != EventKind.CLAIM_REBOUND:
                    raise ValueError("claim reconciliation requires event and worktree evidence")
                if str(command.actor.role_id) != "coordinator" or not _same_generation(
                    command.actor.generation_id, intent.expected_coordinator_generation
                ):
                    raise EventValidationError("claim rebind actor is not the expected coordinator")
                if command.payload.get("reconciliation_ref") != intent.reconciliation.digest:
                    raise EventValidationError("claim rebind reconciliation reference differs from its intent")
                prepared: PreparedClaimChange | OwnershipRefusal = prepare_claim_reconciliation(
                    tx, evidence, intent, worktree
                )
            else:
                if (
                    command.wave_id != intent.expected.wave_id
                    or command.actor.role_id != intent.expected.role_id
                    or command.actor.thread_id != intent.expected.thread_id
                    or not _same_generation(command.actor.generation_id, intent.expected.generation_id)
                ):
                    raise EventValidationError("claim command actor/wave does not match expected owner bindings")
                authority_assignment = intent.expected.assignment
                if authority_assignment is None:
                    return self._append_rejected_reason(tx, command, "stale_assignment")
                if isinstance(intent, ReserveClaim) and intent.assignment != authority_assignment:
                    raise EventValidationError("claim reservation assignment differs from expected bindings")
                current_assignment = tx.read_current_assignment(command.wave_id, authority_assignment)
                if (
                    current_assignment is None
                    or current_assignment.assignment != authority_assignment
                    or not current_assignment.acknowledged
                ):
                    return self._append_rejected_reason(tx, command, "stale_assignment")
                prepared = prepare_claim_change(tx, evidence, intent, worktree, self.ids, self.clock)
            if isinstance(prepared, OwnershipRefusal):
                return self._append_refusal(tx, command, prepared)
            if prepared.replacement.wave_id != command.wave_id:
                raise EventValidationError("claim command wave differs from prepared replacement")
            if str(command.payload.get("claim_id")) != str(prepared.replacement.claim_id):
                raise EventValidationError("claim command ID differs from prepared replacement")
            if command.kind == EventKind.CLAIM_RESERVED and (
                command.payload.get("file_lane_digest") != prepared.replacement.file_lane_digest
            ):
                raise EventValidationError("claim command lane differs from prepared replacement")
            receipt = tx.append_event(
                command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                validation_facts=canonical_record(
                    claim=prepared.replacement,
                    reconciliation=prepared.reconciliation,
                ),
                committed_at=self.clock.now_utc(),
            )
            tx.stage_claim_change(prepared)
            assert receipt.sequence is not None
            tx.put_projection(
                command.wave_id,
                "claim",
                str(prepared.replacement.claim_id),
                _plain_record(prepared.replacement),
                receipt.sequence,
            )
            tx.commit()
            return receipt


def build_projection_snapshot(events: tuple[DurableEvent, ...]) -> ProjectionSnapshot:
    """Pure replay reducer using original committed dispositions and facts."""

    projections: dict[tuple[str, str], tuple[dict[str, Any], int]] = {}
    cursors: dict[tuple[str, str, str, str], tuple[CursorState, int]] = {}
    by_id = {(str(event.command.wave_id), str(event.command.event_id)): event for event in events}
    for event in events:
        if event.disposition == EventDisposition.REJECTED:
            continue
        command = event.command
        facts = event.validation_facts.as_mapping()
        if command.kind == EventKind.WAVE_BOOTSTRAPPED:
            request = _plain_record(facts["request"])
            projections[("wave", str(command.wave_id))] = (request, event.sequence)
            grants = facts["grants"]
            assert isinstance(grants, tuple)
            for grant_value in grants:
                grant = _plain_record(grant_value)
                projections[("grant", str(grant["grant_id"]))] = (grant, event.sequence)
        elif command.kind == EventKind.POLICY_REVISED:
            wave_key = ("wave", str(command.wave_id))
            current_wave = projections.get(wave_key)
            if current_wave is None:
                raise ValueError("policy revision precedes wave bootstrap")
            change = _plain_record(facts["change"])
            if current_wave[0].get("policy_revision") != change["expected_revision"]:
                raise ValueError("policy revision replay compare value differs")
            replacement_wave = dict(current_wave[0])
            replacement_wave["policy_revision"] = change["new_revision"]
            projections[wave_key] = (replacement_wave, event.sequence)
        elif command.kind == EventKind.RECOVERY_DELEGATED:
            grant = _plain_record(facts["grant"])
            projections[("grant", str(grant["grant_id"]))] = (grant, event.sequence)
        elif command.kind in {
            EventKind.OWNER_REGISTERED,
            EventKind.OWNER_REPLACED,
            EventKind.OWNER_CAPABILITY_UPDATED,
            EventKind.OWNER_REBRIEFED,
        }:
            owner = _plain_record(facts["owner"])
            projections[("owner", str(owner["role_id"]))] = (owner, event.sequence)
            snapshot_value = facts.get("snapshot")
            if snapshot_value is not None:
                snapshot = _plain_record(snapshot_value)
                projections[("capability", str(snapshot["snapshot_id"]))] = (
                    snapshot,
                    event.sequence,
                )
            consumed_grant_id = facts.get("consumed_grant_id")
            if consumed_grant_id is not None:
                grant_key = ("grant", str(consumed_grant_id))
                current_grant = projections.get(grant_key)
                if current_grant is None:
                    raise ValueError("owner event consumed a grant absent from the journal")
                consumed_grant = dict(current_grant[0])
                consumed_grant["consumed"] = True
                projections[grant_key] = (consumed_grant, event.sequence)
        elif command.kind in {
            EventKind.CLAIM_RESERVED,
            EventKind.CLAIM_MATERIALIZED,
            EventKind.CLAIM_RECONCILE_REQUIRED,
            EventKind.CLAIM_REBOUND,
            EventKind.CLAIM_RELEASED,
        }:
            claim = _plain_record(facts["claim"])
            projections[("claim", str(claim["claim_id"]))] = (claim, event.sequence)
        elif command.kind == EventKind.RECONCILIATION_RECORDED:
            reconciliation = _plain_record(facts["reconciliation"])
            projections[("reconciliation", str(reconciliation["record"]["record_id"]))] = (
                reconciliation,
                event.sequence,
            )
        elif command.kind == EventKind.CURSOR_ADVANCED:
            cursor = CursorState(
                command.wave_id,
                command.actor.role_id,
                command.actor.thread_id,
                OwnerGenerationId(_uuid_value(command.actor.generation_id)),
            )
            cursor_key = (
                str(cursor.wave_id),
                str(cursor.role_id),
                str(cursor.thread_id),
                str(cursor.generation_id),
            )
            preceding = cursors.get(cursor_key)
            cursor = replay_scan_cursor(event, preceding[0] if preceding is not None else cursor)
            cursors[cursor_key] = (cursor, event.sequence)
        if command.assignment is None:
            continue
        if command.kind in {
            EventKind.ASSIGNMENT_READ,
            EventKind.ASSIGNMENT_ACCEPTED,
            EventKind.ASSIGNMENT_IMPLEMENTING,
            EventKind.ASSIGNMENT_COMPLETED,
        }:
            assert command.correlation_id is not None
            correlated = by_id.get((str(command.wave_id), str(command.correlation_id)))
            if correlated is None or correlated.sequence >= event.sequence:
                raise ValueError("committed acknowledgement has no prior correlated event")
            expected_kinds = {
                EventKind.ASSIGNMENT_READ: {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND},
                EventKind.ASSIGNMENT_ACCEPTED: {
                    EventKind.ASSIGNMENT_QUEUED,
                    EventKind.ASSIGNMENT_REBOUND,
                },
                EventKind.ASSIGNMENT_IMPLEMENTING: {EventKind.GATE_APPROVED},
                EventKind.ASSIGNMENT_COMPLETED: {EventKind.EXTERNAL_MERGE_OBSERVED},
            }[command.kind]
            expected_disposition = (
                EventDisposition.RECONCILED
                if command.kind == EventKind.ASSIGNMENT_COMPLETED
                else EventDisposition.APPLIED
            )
            if (
                correlated.command.kind not in expected_kinds
                or correlated.disposition != expected_disposition
                or correlated.command.assignment != command.assignment
            ):
                raise ValueError("committed acknowledgement has invalid correlation evidence")
        key = _assignment_key(command.assignment.ref)
        projection_key = ("assignment", key)
        current_entry = projections.get(projection_key)
        current = None if current_entry is None else current_entry[0]
        decision = _project_command(command, current)
        if not decision.accepted:
            raise ValueError(f"committed applied event violates transition rules: {command.event_id}")
        if decision.current is not None:
            projections[projection_key] = (decision.current, event.sequence)
        if command.kind == EventKind.ASSIGNMENT_READ:
            assert command.correlation_id is not None
            correlated = by_id.get((str(command.wave_id), str(command.correlation_id)))
            if correlated is None or correlated.command.assignment is None:
                raise ValueError("committed read acknowledgement has no correlated event")
            cursor_key = (
                str(command.wave_id),
                str(command.assignment.worker_role),
                str(command.assignment.worker_thread),
                str(command.assignment.worker_generation),
            )
            current_cursor = cursors.get(cursor_key)
            cursor = (
                current_cursor[0]
                if current_cursor is not None
                else CursorState(
                    wave_id=command.wave_id,
                    role_id=command.assignment.worker_role,
                    thread_id=command.assignment.worker_thread,
                    generation_id=command.assignment.worker_generation,
                )
            )
            cursor = advance_cursor(
                cursor,
                observed_sequences=(correlated.sequence, event.sequence),
                scanned_through=event.sequence,
            )
            cursors[cursor_key] = (cursor, event.sequence)
    return ProjectionSnapshot(
        projections=tuple(
            ProjectionRow(kind, key, value, sequence) for (kind, key), (value, sequence) in sorted(projections.items())
        ),
        cursors=tuple(CursorRow(cursor, sequence) for _, (cursor, sequence) in sorted(cursors.items())),
    )


__all__ = [
    "EventAuthorizationError",
    "EventService",
    "ProjectionDecision",
    "build_projection_snapshot",
]
