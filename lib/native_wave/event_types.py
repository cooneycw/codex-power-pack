"""Canonical native-wave event values owned by issue #205.

The registry/identity value objects live in :mod:`lib.native_wave.types` and
are deliberately imported rather than duplicated here.  Store-generated
sequence numbers and receipts are separate from caller-supplied commands.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias
from uuid import UUID

from .types import (
    AssignmentRef,
    CapabilityField,
    CapabilityFieldRequirement,
    CapabilityRequirements,
    CapabilitySnapshotId,
    ClaimId,
    CoordinatorGenerationId,
    DurableRecordRef,
    GrantId,
    OwnerGenerationId,
    RoleId,
    ThreadId,
    WaveId,
)

SCHEMA_VERSION = 1
SHA256_PREFIX = "sha256:"


class EventValidationError(ValueError):
    """Raised before persistence when a command is not canonical or well formed."""


def _require_int(value: object, *, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if minimum == 1 else f">= {minimum}"
        raise EventValidationError(f"{field} must be an integer {qualifier}")
    return value


@dataclass(frozen=True, slots=True)
class EventId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise EventValidationError("event_id must be a UUID")

    @classmethod
    def parse(cls, value: str) -> EventId:
        try:
            parsed = UUID(value)
        except (AttributeError, TypeError, ValueError) as exc:
            raise EventValidationError("event_id must be a canonical UUID") from exc
        if str(parsed) != value:
            raise EventValidationError("event_id must use canonical lowercase UUID spelling")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


class EventKind(str, Enum):
    WAVE_BOOTSTRAPPED = "wave.bootstrapped"
    POLICY_REVISED = "policy.revised"
    RECOVERY_DELEGATED = "recovery.delegated"
    OWNER_REGISTERED = "owner.registered"
    OWNER_REPLACED = "owner.replaced"
    OWNER_CAPABILITY_UPDATED = "owner.capability_updated"
    OWNER_REBRIEFED = "owner.rebriefed"
    CLAIM_RESERVED = "claim.reserved"
    CLAIM_MATERIALIZED = "claim.materialized"
    CLAIM_RECONCILE_REQUIRED = "claim.reconcile_required"
    CLAIM_REBOUND = "claim.rebound"
    CLAIM_RELEASED = "claim.released"
    RECONCILIATION_RECORDED = "reconciliation.recorded"
    ASSIGNMENT_QUEUED = "assignment.queued"
    ASSIGNMENT_REBOUND = "assignment.rebound"
    ASSIGNMENT_READ = "assignment.read"
    ASSIGNMENT_ACCEPTED = "assignment.accepted"
    GATE_APPROVED = "gate.approved"
    GATE_REJECTED = "gate.rejected"
    ASSIGNMENT_IMPLEMENTING = "assignment.implementing"
    ASSIGNMENT_PR_OPEN = "assignment.pr_open"
    ASSIGNMENT_HELD = "assignment.held"
    ASSIGNMENT_RELEASED = "assignment.released"
    MERGE_CLEARED = "merge.cleared"
    ASSIGNMENT_COMPLETED = "assignment.completed"
    ASSIGNMENT_CANCELLED = "assignment.cancelled"
    TRANSPORT_ACCEPTED = "transport.accepted"
    WORKER_ACTION_SUPPRESSED = "worker.action_suppressed"
    EXTERNAL_MERGE_OBSERVED = "external.merge_observed"
    CURSOR_ADVANCED = "cursor.advanced"
    PROSE_MESSAGE = "prose.message"


class ProvenanceClass(str, Enum):
    TRANSPORT_OBSERVED = "transport_observed"
    REGISTRY_BOUND_LOCAL = "registry_bound_local"
    PAYLOAD_ONLY = "payload_only"


class EventDisposition(str, Enum):
    APPLIED = "applied"
    OBSERVED = "observed"
    RECONCILED = "reconciled"
    REJECTED = "rejected"


class AssignmentState(str, Enum):
    QUEUED = "queued"
    READ = "read"
    ACCEPTED = "accepted"
    IMPLEMENTING = "implementing"
    PR_OPEN = "pr_open"
    HELD = "held"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


GenerationId: TypeAlias = OwnerGenerationId | CoordinatorGenerationId
CanonicalScalar: TypeAlias = None | bool | int | str
CanonicalValue: TypeAlias = CanonicalScalar | tuple["CanonicalValue", ...] | Mapping[str, "CanonicalValue"]


def _require_nfc(value: str, *, field: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise EventValidationError(f"{field} must already be Unicode NFC")
    return value


def _require_digest(value: str | None, *, field: str) -> None:
    if value is None:
        return
    if not value.startswith(SHA256_PREFIX) or len(value) != len(SHA256_PREFIX) + 64:
        raise EventValidationError(f"{field} must be sha256:<64 lowercase hex>")
    suffix = value[len(SHA256_PREFIX) :]
    if any(char not in "0123456789abcdef" for char in suffix):
        raise EventValidationError(f"{field} must be sha256:<64 lowercase hex>")


def _require_git_sha(value: str | None, *, field: str) -> None:
    if value is None:
        return
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise EventValidationError(f"{field} must be a full lowercase Git SHA")


def _require_uuid_text(value: object, *, field: str) -> None:
    if not isinstance(value, str):
        raise EventValidationError(f"{field} must be a canonical UUID string")
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise EventValidationError(f"{field} must be a canonical UUID string") from exc
    if str(parsed) != value:
        raise EventValidationError(f"{field} must be a canonical UUID string")


def _require_nonempty_text(value: object, *, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EventValidationError(f"{field} must be a non-empty string")
    _require_nfc(value, field=field)


def _validate_payload_values(payload: EventPayload) -> None:
    values = payload.as_mapping()
    for name in ("claim_id", "grant_id"):
        if name in values:
            _require_uuid_text(values[name], field=f"payload.{name}")
    for name in ("file_lane_digest", "reconciliation_ref", "worktree_evidence_digest"):
        if name in values:
            value = values[name]
            if not isinstance(value, str):
                raise EventValidationError(f"payload.{name} must be a digest string")
            _require_digest(value, field=f"payload.{name}")
    if "merge_commit" in values:
        value = values["merge_commit"]
        if not isinstance(value, str):
            raise EventValidationError("payload.merge_commit must be a Git SHA string")
        _require_git_sha(value, field="payload.merge_commit")
    for name in ("gate_id", "operator_reason", "reason", "text", "transport", "verdict"):
        if name in values:
            _require_nonempty_text(values[name], field=f"payload.{name}")
    for name in ("previous_state", "resume_state"):
        if name in values:
            value = values[name]
            if not isinstance(value, str) or value not in {state.value for state in AssignmentState}:
                raise EventValidationError(f"payload.{name} must be an assignment state")
    if "conditions" in values:
        conditions = values["conditions"]
        if not isinstance(conditions, tuple):
            raise EventValidationError("payload.conditions must be an array of strings")
        for condition in conditions:
            _require_nonempty_text(condition, field="payload.conditions[]")
    if "cursor_highest_contiguous" in values:
        _require_int(
            values["cursor_highest_contiguous"],
            field="payload.cursor_highest_contiguous",
            minimum=0,
        )
    if "cursor_sparse" in values:
        sparse = values["cursor_sparse"]
        if not isinstance(sparse, tuple):
            raise EventValidationError("payload.cursor_sparse must be an array of sequences")
        sequences = tuple(_require_int(sequence, field="payload.cursor_sparse[]", minimum=1) for sequence in sparse)
        if sequences != tuple(sorted(set(sequences))):
            raise EventValidationError("payload.cursor_sparse must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ProvenanceEvidence:
    classification: ProvenanceClass
    source: str
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        _require_nfc(self.source, field="provenance source")
        if not self.source:
            raise EventValidationError("provenance source must not be empty")
        _require_digest(self.evidence_digest, field="provenance evidence_digest")


@dataclass(frozen=True, slots=True)
class ActorBinding:
    role_id: RoleId
    thread_id: ThreadId
    generation_id: GenerationId

    def __post_init__(self) -> None:
        if self.role_id == RoleId("coordinator"):
            if not isinstance(self.generation_id, CoordinatorGenerationId):
                raise EventValidationError("coordinator actor requires a coordinator generation")
        elif not isinstance(self.generation_id, OwnerGenerationId) or isinstance(
            self.generation_id, CoordinatorGenerationId
        ):
            raise EventValidationError("worker actor requires an owner generation")


@dataclass(frozen=True, slots=True)
class PolicyRevisionChange:
    expected_revision: int
    new_revision: int

    def __post_init__(self) -> None:
        for name, value in (
            ("expected_revision", self.expected_revision),
            ("new_revision", self.new_revision),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise EventValidationError(f"{name} must be a positive integer")
        if self.new_revision <= self.expected_revision:
            raise EventValidationError("policy revision must advance")


@dataclass(frozen=True, slots=True)
class AssignmentBinding:
    ref: AssignmentRef
    issue: int
    worker_role: RoleId
    worker_thread: ThreadId
    worker_generation: OwnerGenerationId
    coordinator_generation: CoordinatorGenerationId
    capability_snapshot_id: CapabilitySnapshotId
    capability_requirements: CapabilityRequirements
    required_evidence: tuple["DurableRecordRef", ...]
    policy_revision: int
    plan_digest: str | None = None
    pr_base: str | None = None
    pr_head: str | None = None

    def __post_init__(self) -> None:
        _require_int(self.issue, field="assignment issue", minimum=1)
        _require_int(self.policy_revision, field="policy_revision", minimum=1)
        if self.required_evidence != tuple(sorted(self.required_evidence, key=lambda item: str(item.record_id))):
            raise EventValidationError("assignment required_evidence must be canonical")
        _require_digest(self.plan_digest, field="plan_digest")
        _require_git_sha(self.pr_base, field="pr_base")
        _require_git_sha(self.pr_head, field="pr_head")


_PAYLOAD_FIELDS = frozenset(
    {
        "claim_id",
        "conditions",
        "cursor_highest_contiguous",
        "cursor_sparse",
        "file_lane_digest",
        "gate_id",
        "grant_id",
        "merge_commit",
        "operator_reason",
        "previous_state",
        "reason",
        "reconciliation_ref",
        "resume_state",
        "text",
        "transport",
        "verdict",
        "worktree_evidence_digest",
    }
)


def _freeze_payload(value: CanonicalValue, *, field: str) -> CanonicalValue:
    if value is None or isinstance(value, (bool, int, str)):
        _canonicalize(value, field=field)
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, CanonicalValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise EventValidationError(f"{field} object keys must be strings")
            _require_nfc(key, field=f"{field} key")
            if key in frozen:
                raise EventValidationError(f"{field} object keys must be unique")
            frozen[key] = _freeze_payload(item, field=f"{field}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_payload(item, field=f"{field}[]") for item in value)
    raise EventValidationError(f"{field} contains unsupported value type {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class EventPayload:
    """Closed, immutable payload field set for v1 events.

    Values are supplied as sorted pairs so duplicate keys cannot disappear in a
    Python ``dict`` before validation.
    """

    items: tuple[tuple[str, CanonicalValue], ...] = ()

    def __post_init__(self) -> None:
        names = [name for name, _ in self.items]
        if names != sorted(names):
            raise EventValidationError("payload keys must be sorted")
        if len(names) != len(set(names)):
            raise EventValidationError("payload keys must be unique")
        unknown = set(names) - _PAYLOAD_FIELDS
        if unknown:
            raise EventValidationError(f"unknown payload field(s): {', '.join(sorted(unknown))}")
        frozen_items: list[tuple[str, CanonicalValue]] = []
        for name, value in self.items:
            _require_nfc(name, field="payload key")
            frozen_items.append((name, _freeze_payload(value, field=f"payload.{name}")))
        object.__setattr__(self, "items", tuple(frozen_items))

    @classmethod
    def from_mapping(cls, values: Mapping[str, CanonicalValue]) -> EventPayload:
        return cls(tuple(sorted(values.items())))

    def as_mapping(self) -> Mapping[str, CanonicalValue]:
        return MappingProxyType(dict(self.items))

    def get(self, name: str, default: CanonicalValue = None) -> CanonicalValue:
        return dict(self.items).get(name, default)


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    """Immutable canonical key/value record for store-owned validation facts."""

    items: tuple[tuple[str, CanonicalValue], ...] = ()

    def __post_init__(self) -> None:
        names = [name for name, _ in self.items]
        if names != sorted(names) or len(names) != len(set(names)):
            raise EventValidationError("canonical record keys must be sorted and unique")
        frozen_items: list[tuple[str, CanonicalValue]] = []
        for name, value in self.items:
            _require_nfc(name, field="canonical record key")
            frozen_items.append((name, _freeze_payload(value, field=f"record.{name}")))
        object.__setattr__(self, "items", tuple(frozen_items))

    @classmethod
    def from_mapping(cls, values: Mapping[str, CanonicalValue]) -> CanonicalRecord:
        return cls(tuple(sorted(values.items())))

    def as_mapping(self) -> Mapping[str, CanonicalValue]:
        return MappingProxyType(dict(self.items))

    def get(self, name: str, default: CanonicalValue = None) -> CanonicalValue:
        return dict(self.items).get(name, default)


_ASSIGNMENT_KINDS = frozenset(
    {
        EventKind.ASSIGNMENT_QUEUED,
        EventKind.ASSIGNMENT_REBOUND,
        EventKind.ASSIGNMENT_READ,
        EventKind.ASSIGNMENT_ACCEPTED,
        EventKind.GATE_APPROVED,
        EventKind.GATE_REJECTED,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        EventKind.ASSIGNMENT_PR_OPEN,
        EventKind.ASSIGNMENT_HELD,
        EventKind.ASSIGNMENT_RELEASED,
        EventKind.MERGE_CLEARED,
        EventKind.ASSIGNMENT_COMPLETED,
        EventKind.ASSIGNMENT_CANCELLED,
        EventKind.TRANSPORT_ACCEPTED,
        EventKind.WORKER_ACTION_SUPPRESSED,
        EventKind.EXTERNAL_MERGE_OBSERVED,
    }
)
_PLAN_KINDS = frozenset(
    {
        EventKind.GATE_APPROVED,
        EventKind.GATE_REJECTED,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        EventKind.ASSIGNMENT_PR_OPEN,
        EventKind.MERGE_CLEARED,
        EventKind.ASSIGNMENT_COMPLETED,
        EventKind.EXTERNAL_MERGE_OBSERVED,
    }
)
_PR_KINDS = frozenset(
    {
        EventKind.ASSIGNMENT_PR_OPEN,
        EventKind.MERGE_CLEARED,
        EventKind.ASSIGNMENT_COMPLETED,
        EventKind.EXTERNAL_MERGE_OBSERVED,
    }
)
_CORRELATED_KINDS = frozenset(
    {
        EventKind.ASSIGNMENT_READ,
        EventKind.ASSIGNMENT_ACCEPTED,
        EventKind.ASSIGNMENT_IMPLEMENTING,
        EventKind.ASSIGNMENT_COMPLETED,
    }
)
_AUTHORITY_KINDS = _ASSIGNMENT_KINDS | frozenset(
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

_KIND_PAYLOAD_SCHEMA: dict[EventKind, tuple[frozenset[str], frozenset[str]]] = {
    EventKind.WAVE_BOOTSTRAPPED: (frozenset({"operator_reason"}), frozenset({"operator_reason"})),
    EventKind.POLICY_REVISED: (frozenset({"operator_reason"}), frozenset({"operator_reason"})),
    EventKind.RECOVERY_DELEGATED: (
        frozenset({"grant_id", "operator_reason"}),
        frozenset({"grant_id", "operator_reason"}),
    ),
    EventKind.OWNER_REGISTERED: (frozenset({"grant_id"}), frozenset({"grant_id"})),
    EventKind.OWNER_REPLACED: (frozenset(), frozenset({"grant_id", "reason"})),
    EventKind.OWNER_CAPABILITY_UPDATED: (frozenset(), frozenset()),
    EventKind.OWNER_REBRIEFED: (frozenset(), frozenset()),
    EventKind.CLAIM_RESERVED: (
        frozenset({"claim_id", "file_lane_digest"}),
        frozenset({"claim_id", "file_lane_digest", "worktree_evidence_digest"}),
    ),
    EventKind.CLAIM_MATERIALIZED: (
        frozenset({"claim_id", "worktree_evidence_digest"}),
        frozenset({"claim_id", "worktree_evidence_digest"}),
    ),
    EventKind.CLAIM_RECONCILE_REQUIRED: (
        frozenset({"claim_id", "reason"}),
        frozenset({"claim_id", "reason", "worktree_evidence_digest"}),
    ),
    EventKind.CLAIM_REBOUND: (
        frozenset({"claim_id", "reconciliation_ref", "worktree_evidence_digest"}),
        frozenset({"claim_id", "reconciliation_ref", "worktree_evidence_digest"}),
    ),
    EventKind.CLAIM_RELEASED: (frozenset({"claim_id"}), frozenset({"claim_id", "reason"})),
    EventKind.RECONCILIATION_RECORDED: (
        frozenset({"reconciliation_ref"}),
        frozenset({"reconciliation_ref"}),
    ),
    EventKind.ASSIGNMENT_QUEUED: (frozenset(), frozenset({"file_lane_digest"})),
    EventKind.ASSIGNMENT_REBOUND: (frozenset({"reason"}), frozenset({"reason", "reconciliation_ref"})),
    EventKind.ASSIGNMENT_READ: (frozenset(), frozenset()),
    EventKind.ASSIGNMENT_ACCEPTED: (frozenset(), frozenset()),
    EventKind.GATE_APPROVED: (
        frozenset({"gate_id", "verdict"}),
        frozenset({"conditions", "gate_id", "verdict"}),
    ),
    EventKind.GATE_REJECTED: (
        frozenset({"gate_id", "reason", "verdict"}),
        frozenset({"conditions", "gate_id", "reason", "verdict"}),
    ),
    EventKind.ASSIGNMENT_IMPLEMENTING: (frozenset(), frozenset()),
    EventKind.ASSIGNMENT_PR_OPEN: (frozenset(), frozenset()),
    EventKind.ASSIGNMENT_HELD: (
        frozenset({"conditions", "reason", "resume_state"}),
        frozenset({"conditions", "reason", "resume_state"}),
    ),
    EventKind.ASSIGNMENT_RELEASED: (
        frozenset({"conditions", "previous_state", "reason"}),
        frozenset({"conditions", "previous_state", "reason"}),
    ),
    EventKind.MERGE_CLEARED: (frozenset(), frozenset({"conditions"})),
    EventKind.ASSIGNMENT_COMPLETED: (frozenset(), frozenset({"merge_commit", "reason"})),
    EventKind.ASSIGNMENT_CANCELLED: (frozenset({"reason"}), frozenset({"reason"})),
    EventKind.TRANSPORT_ACCEPTED: (frozenset({"transport"}), frozenset({"transport"})),
    EventKind.WORKER_ACTION_SUPPRESSED: (frozenset({"reason"}), frozenset({"reason"})),
    EventKind.EXTERNAL_MERGE_OBSERVED: (
        frozenset({"merge_commit"}),
        frozenset({"merge_commit"}),
    ),
    EventKind.CURSOR_ADVANCED: (
        frozenset({"cursor_highest_contiguous", "cursor_sparse"}),
        frozenset({"cursor_highest_contiguous", "cursor_sparse"}),
    ),
    EventKind.PROSE_MESSAGE: (frozenset({"text"}), frozenset({"text"})),
}

_KIND_EFFECT_FIELDS: dict[EventKind, frozenset[str]] = {
    EventKind.WAVE_BOOTSTRAPPED: frozenset({"request"}),
    EventKind.POLICY_REVISED: frozenset({"change"}),
    EventKind.RECOVERY_DELEGATED: frozenset({"request"}),
    EventKind.OWNER_REGISTERED: frozenset({"intent", "snapshot"}),
    EventKind.OWNER_REPLACED: frozenset({"intent", "snapshot"}),
    EventKind.OWNER_CAPABILITY_UPDATED: frozenset({"intent", "snapshot"}),
    EventKind.OWNER_REBRIEFED: frozenset({"intent"}),
    EventKind.CLAIM_RESERVED: frozenset({"intent", "worktree"}),
    EventKind.CLAIM_MATERIALIZED: frozenset({"intent", "worktree"}),
    EventKind.CLAIM_RECONCILE_REQUIRED: frozenset({"intent", "worktree"}),
    EventKind.CLAIM_REBOUND: frozenset({"intent", "worktree"}),
    EventKind.CLAIM_RELEASED: frozenset({"intent", "worktree"}),
    EventKind.RECONCILIATION_RECORDED: frozenset({"reconciliation"}),
}


@dataclass(frozen=True, slots=True)
class NativeCommand:
    event_id: EventId
    kind: EventKind
    wave_id: WaveId
    actor: ActorBinding
    provenance: ProvenanceEvidence
    assignment: AssignmentBinding | None = None
    causation_id: EventId | None = None
    correlation_id: EventId | None = None
    payload: EventPayload = EventPayload()
    effect: CanonicalRecord = CanonicalRecord()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise EventValidationError("command schema version must be an integer")
        if self.schema_version != SCHEMA_VERSION:
            raise EventValidationError(f"unsupported command schema version: {self.schema_version}")
        if self.kind in _ASSIGNMENT_KINDS and self.assignment is None:
            raise EventValidationError(f"{self.kind.value} requires assignment bindings")
        if self.kind not in _ASSIGNMENT_KINDS and self.assignment is not None:
            raise EventValidationError(f"{self.kind.value} must not carry assignment bindings")
        if self.kind in _PLAN_KINDS and (self.assignment is None or self.assignment.plan_digest is None):
            raise EventValidationError(f"{self.kind.value} requires plan_digest")
        if self.kind in _PR_KINDS and (
            self.assignment is None or self.assignment.pr_base is None or self.assignment.pr_head is None
        ):
            raise EventValidationError(f"{self.kind.value} requires pr_base and pr_head")
        if self.kind in _CORRELATED_KINDS and self.correlation_id is None:
            raise EventValidationError(f"{self.kind.value} requires correlation_id")
        if self.kind == EventKind.ASSIGNMENT_HELD:
            if not self.payload.get("reason") or not self.payload.get("resume_state"):
                raise EventValidationError("assignment.held requires reason and resume_state")
        if self.kind == EventKind.GATE_APPROVED and self.payload.get("verdict") != "approved":
            raise EventValidationError("gate.approved requires verdict=approved")
        if self.kind == EventKind.GATE_REJECTED and self.payload.get("verdict") != "rejected":
            raise EventValidationError("gate.rejected requires verdict=rejected")
        if self.kind == EventKind.PROSE_MESSAGE and not isinstance(self.payload.get("text"), str):
            raise EventValidationError("prose.message requires text")
        required_payload, allowed_payload = _KIND_PAYLOAD_SCHEMA[self.kind]
        supplied_payload = {name for name, _ in self.payload.items}
        missing_payload = required_payload - supplied_payload
        unexpected_payload = supplied_payload - allowed_payload
        if missing_payload:
            raise EventValidationError(
                f"{self.kind.value} missing payload field(s): {', '.join(sorted(missing_payload))}"
            )
        if unexpected_payload:
            raise EventValidationError(
                f"{self.kind.value} has unexpected payload field(s): {', '.join(sorted(unexpected_payload))}"
            )
        _validate_payload_values(self.payload)
        expected_effect = _KIND_EFFECT_FIELDS.get(self.kind, frozenset())
        supplied_effect = {name for name, _ in self.effect.items}
        if supplied_effect != expected_effect:
            missing_effect = expected_effect - supplied_effect
            unexpected_effect = supplied_effect - expected_effect
            details = []
            if missing_effect:
                details.append(f"missing {', '.join(sorted(missing_effect))}")
            if unexpected_effect:
                details.append(f"unexpected {', '.join(sorted(unexpected_effect))}")
            raise EventValidationError(f"{self.kind.value} effect schema mismatch: {'; '.join(details)}")
        if self.kind in _AUTHORITY_KINDS and self.provenance.classification == ProvenanceClass.PAYLOAD_ONLY:
            raise EventValidationError("payload_only provenance cannot form an authority-bearing command")

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self)

    def payload_digest(self) -> str:
        return digest_bytes(self.canonical_bytes())


@dataclass(frozen=True, slots=True)
class AppendReceipt:
    wave_id: WaveId
    event_id: EventId
    command_digest: str
    disposition: EventDisposition
    reason: str | None
    sequence: int | None
    event_digest: str | None
    committed_at: datetime | None

    def __post_init__(self) -> None:
        _require_digest(self.command_digest, field="command_digest")
        _require_digest(self.event_digest, field="event_digest")
        if self.sequence is not None:
            _require_int(self.sequence, field="receipt sequence", minimum=1)
        if self.committed_at is not None:
            _canonical_datetime(self.committed_at, field="committed_at")


@dataclass(frozen=True, slots=True)
class DurableEvent:
    command: NativeCommand
    sequence: int
    disposition: EventDisposition
    reason: str | None
    committed_at: datetime
    previous_event_digest: str | None
    event_digest: str
    validation_facts: CanonicalRecord = CanonicalRecord()

    def __post_init__(self) -> None:
        _require_int(self.sequence, field="event sequence", minimum=1)
        _canonical_datetime(self.committed_at, field="committed_at")
        _require_digest(self.previous_event_digest, field="previous_event_digest")
        _require_digest(self.event_digest, field="event_digest")


@dataclass(frozen=True, slots=True)
class CursorState:
    wave_id: WaveId
    role_id: RoleId
    thread_id: ThreadId
    generation_id: OwnerGenerationId
    highest_contiguous: int = 0
    sparse_sequences: tuple[int, ...] = ()
    gaps: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _require_int(self.highest_contiguous, field="cursor highest_contiguous", minimum=0)
        for label, values in (("sparse_sequences", self.sparse_sequences), ("gaps", self.gaps)):
            if not isinstance(values, tuple) or any(
                isinstance(value, bool) or not isinstance(value, int) for value in values
            ):
                raise EventValidationError(f"cursor {label} must be an immutable integer tuple")
            if tuple(sorted(set(values))) != values or any(value <= self.highest_contiguous for value in values):
                raise EventValidationError(f"cursor {label} must be sorted unique values above the contiguous point")
        if set(self.sparse_sequences) & set(self.gaps):
            raise EventValidationError("cursor sparse sequences and gaps must be disjoint")


@dataclass(frozen=True, slots=True)
class EventPage:
    events: tuple[DurableEvent, ...]
    scanned_through: int
    cursor: CursorState

    def __post_init__(self) -> None:
        if not isinstance(self.events, tuple):
            raise EventValidationError("event page events must be immutable")
        _require_int(self.scanned_through, field="event page scanned_through", minimum=0)
        if self.scanned_through < self.cursor.highest_contiguous:
            raise EventValidationError("event page cannot end before its cursor")


def _canonical_datetime(value: datetime, *, field: str) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise EventValidationError(f"{field} must be timezone-aware UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonicalize(value: Any, *, field: str = "value") -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not -(2**63) <= value <= 2**63 - 1:
            raise EventValidationError(f"{field} integer is outside signed 64-bit range")
        return value
    if isinstance(value, float):
        raise EventValidationError(f"{field} floats are forbidden")
    if isinstance(value, str):
        return _require_nfc(value, field=field)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _canonical_datetime(value, field=field)
    if isinstance(value, Enum):
        return _canonicalize(value.value, field=field)
    if isinstance(value, (EventPayload, CanonicalRecord)):
        return {key: _canonicalize(item, field=f"{field}.{key}") for key, item in value.items}
    if isinstance(
        value,
        (
            EventId,
            WaveId,
            RoleId,
            ThreadId,
            OwnerGenerationId,
            CoordinatorGenerationId,
            CapabilitySnapshotId,
            ClaimId,
            GrantId,
        ),
    ):
        return _canonicalize(value.value, field=field)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _canonicalize(getattr(value, item.name), field=f"{field}.{item.name}") for item in fields(value)
        }
    if isinstance(value, Mapping):
        canonical: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise EventValidationError(f"{field} object keys must be strings")
            _require_nfc(key, field=f"{field} key")
            if key in canonical:
                raise EventValidationError(f"{field} object keys must be unique")
            canonical[key] = _canonicalize(item, field=f"{field}.{key}")
        return canonical
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item, field=f"{field}[]") for item in value]
    raise EventValidationError(f"{field} contains unsupported value type {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    canonical = _canonicalize(value)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_record(**values: Any) -> CanonicalRecord:
    """Freeze typed values into the command/event canonical record domain."""

    canonical = _canonicalize(values, field="record")
    if not isinstance(canonical, dict):  # pragma: no cover - defensive narrowing
        raise EventValidationError("canonical record must be an object")
    return CanonicalRecord.from_mapping(canonical)


def digest_bytes(value: bytes) -> str:
    return f"{SHA256_PREFIX}{hashlib.sha256(value).hexdigest()}"


def command_from_bytes(value: bytes) -> NativeCommand:
    """Decode and revalidate canonical command bytes from the durable store."""

    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EventValidationError("stored command is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise EventValidationError("stored command must be an object")
    expected = {
        "actor",
        "assignment",
        "causation_id",
        "correlation_id",
        "effect",
        "event_id",
        "kind",
        "payload",
        "provenance",
        "schema_version",
        "wave_id",
    }
    if set(payload) != expected:
        raise EventValidationError("stored command has an unexpected top-level schema")
    actor_payload = payload["actor"]
    provenance_payload = payload["provenance"]
    if not isinstance(actor_payload, dict) or not isinstance(provenance_payload, dict):
        raise EventValidationError("stored actor/provenance must be objects")
    role_id = RoleId(actor_payload["role_id"])
    generation_value = UUID(actor_payload["generation_id"])
    generation: GenerationId
    if getattr(role_id, "value", None) == "coordinator":
        generation = CoordinatorGenerationId(generation_value)
    else:
        generation = OwnerGenerationId(generation_value)
    actor = ActorBinding(
        role_id=role_id,
        thread_id=ThreadId(UUID(actor_payload["thread_id"])),
        generation_id=generation,
    )
    provenance = ProvenanceEvidence(
        classification=ProvenanceClass(provenance_payload["classification"]),
        source=provenance_payload["source"],
        evidence_digest=provenance_payload.get("evidence_digest"),
    )
    assignment_payload = payload["assignment"]
    assignment = None
    if assignment_payload is not None:
        if not isinstance(assignment_payload, dict):
            raise EventValidationError("stored assignment must be an object")
        ref_payload = assignment_payload["ref"]
        assignment = AssignmentBinding(
            ref=AssignmentRef(
                UUID(ref_payload["assignment_id"]),
                ref_payload["revision"],
                ref_payload["digest"],
            ),
            issue=assignment_payload["issue"],
            worker_role=RoleId(assignment_payload["worker_role"]),
            worker_thread=ThreadId(UUID(assignment_payload["worker_thread"])),
            worker_generation=OwnerGenerationId(UUID(assignment_payload["worker_generation"])),
            coordinator_generation=CoordinatorGenerationId(UUID(assignment_payload["coordinator_generation"])),
            capability_snapshot_id=CapabilitySnapshotId(assignment_payload["capability_snapshot_id"]),
            capability_requirements=CapabilityRequirements(
                schema_version=assignment_payload["capability_requirements"]["schema_version"],
                fields=tuple(
                    CapabilityFieldRequirement(
                        field=CapabilityField(item["field"]),
                        accepted_values=tuple(item["accepted_values"]),
                    )
                    for item in assignment_payload["capability_requirements"]["fields"]
                ),
                digest=assignment_payload["capability_requirements"]["digest"],
            ),
            required_evidence=tuple(
                DurableRecordRef(UUID(item["record_id"]), item["digest"])
                for item in assignment_payload["required_evidence"]
            ),
            policy_revision=assignment_payload["policy_revision"],
            plan_digest=assignment_payload.get("plan_digest"),
            pr_base=assignment_payload.get("pr_base"),
            pr_head=assignment_payload.get("pr_head"),
        )
    raw_event_payload = payload["payload"]
    raw_effect = payload["effect"]
    if not isinstance(raw_event_payload, dict):
        raise EventValidationError("stored event payload must be an object")
    if not isinstance(raw_effect, dict):
        raise EventValidationError("stored command effect must be an object")
    command = NativeCommand(
        event_id=EventId.parse(payload["event_id"]),
        kind=EventKind(payload["kind"]),
        wave_id=WaveId(payload["wave_id"]),
        actor=actor,
        provenance=provenance,
        assignment=assignment,
        causation_id=EventId.parse(payload["causation_id"]) if payload["causation_id"] else None,
        correlation_id=EventId.parse(payload["correlation_id"]) if payload["correlation_id"] else None,
        payload=EventPayload.from_mapping(raw_event_payload),
        effect=CanonicalRecord.from_mapping(raw_effect),
        schema_version=payload["schema_version"],
    )
    if command.canonical_bytes() != value:
        raise EventValidationError("stored command bytes are not canonical")
    return command


def receipt_bytes(receipt: AppendReceipt) -> bytes:
    return canonical_json_bytes(receipt)


def receipt_from_bytes(value: bytes) -> AppendReceipt:
    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EventValidationError("stored receipt is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "command_digest",
        "committed_at",
        "disposition",
        "event_digest",
        "event_id",
        "reason",
        "sequence",
        "wave_id",
    }:
        raise EventValidationError("stored receipt has an unexpected schema")
    receipt = AppendReceipt(
        wave_id=WaveId(payload["wave_id"]),
        event_id=EventId.parse(payload["event_id"]),
        command_digest=payload["command_digest"],
        disposition=EventDisposition(payload["disposition"]),
        reason=payload["reason"],
        sequence=payload["sequence"],
        event_digest=payload["event_digest"],
        committed_at=(
            datetime.fromisoformat(payload["committed_at"].replace("Z", "+00:00"))
            if payload["committed_at"] is not None
            else None
        ),
    )
    if receipt_bytes(receipt) != value:
        raise EventValidationError("stored receipt bytes are not canonical")
    return receipt


def event_record_digest(
    *,
    command_bytes: bytes,
    sequence: int,
    disposition: EventDisposition,
    reason: str | None,
    committed_at: datetime,
    previous_event_digest: str | None,
    validation_facts: CanonicalRecord,
) -> str:
    record = {
        "command": json.loads(command_bytes),
        "committed_at": _canonical_datetime(committed_at, field="committed_at"),
        "disposition": disposition.value,
        "previous_event_digest": previous_event_digest,
        "reason": reason,
        "sequence": sequence,
        "validation_facts": dict(validation_facts.items),
    }
    return digest_bytes(canonical_json_bytes(record))


__all__ = [
    "ActorBinding",
    "AppendReceipt",
    "AssignmentBinding",
    "AssignmentState",
    "CursorState",
    "CanonicalRecord",
    "DurableEvent",
    "EventDisposition",
    "EventId",
    "EventKind",
    "EventPage",
    "EventPayload",
    "EventValidationError",
    "NativeCommand",
    "PolicyRevisionChange",
    "ProvenanceClass",
    "ProvenanceEvidence",
    "canonical_json_bytes",
    "canonical_record",
    "command_from_bytes",
    "digest_bytes",
    "event_record_digest",
    "receipt_bytes",
    "receipt_from_bytes",
]
