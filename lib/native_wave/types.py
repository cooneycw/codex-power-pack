"""Immutable domain values for native Codex wave ownership.

The records in this module are deliberately inert.  Authority comes from a
store transaction re-reading these records, never from possession of a Python
object or from mutable caller-provided mappings.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import TypeAlias
from uuid import UUID

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_name(value: str, label: str) -> None:
    if not _NAME_RE.fullmatch(value):
        raise ValueError(f"{label} must be a non-empty canonical identifier")


def _require_digest(value: str, label: str = "digest") -> None:
    if not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase sha256 digest")


def _require_utc(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _require_canonical_absolute_path(value: str, label: str) -> None:
    path = PurePosixPath(value)
    if not path.is_absolute() or str(path) != value or ".." in path.parts:
        raise ValueError(f"{label} must be a canonical absolute POSIX path")


def _canonical_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class _TextId:
    value: str

    def __post_init__(self) -> None:
        _require_name(self.value, type(self).__name__)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class WaveId(_TextId):
    """Host-local wave namespace."""


@dataclass(frozen=True, slots=True)
class RoleId(_TextId):
    """Role within a wave."""


@dataclass(frozen=True, slots=True)
class _UuidId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError(f"{type(self).__name__} requires UUID")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ThreadId(_UuidId):
    """Native Codex thread identity."""


@dataclass(frozen=True, slots=True)
class OwnerGenerationId(_UuidId):
    """Generation fence for a role owner."""


@dataclass(frozen=True, slots=True)
class CoordinatorGenerationId(_UuidId):
    """Typed coordinator generation used for coordinator-only authority."""


@dataclass(frozen=True, slots=True)
class ClaimId(_UuidId):
    """Durable worktree claim identifier."""


@dataclass(frozen=True, slots=True)
class GrantId(_UuidId):
    """One-use durable grant identifier."""


@dataclass(frozen=True, slots=True)
class CapabilitySnapshotId:
    value: str

    def __post_init__(self) -> None:
        _require_digest(self.value, "capability snapshot id")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class AssignmentRef:
    assignment_id: UUID
    revision: int
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.assignment_id, UUID):
            raise TypeError("assignment_id requires UUID")
        if self.revision < 1:
            raise ValueError("assignment revision must be positive")
        _require_digest(self.digest, "assignment digest")


@dataclass(frozen=True, slots=True)
class DurableRecordRef:
    record_id: UUID
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, UUID):
            raise TypeError("record_id requires UUID")
        _require_digest(self.digest, "record digest")


class Liveness(Enum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


class Readiness(Enum):
    READY = "ready"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


class ClaimState(Enum):
    RESERVED = "reserved"
    MATERIALIZED = "materialized"
    RECONCILE_REQUIRED = "reconcile_required"
    RELEASED = "released"


class GrantPurpose(Enum):
    REGISTER = "register"
    TAKEOVER = "takeover"
    COORDINATOR_RECOVERY = "coordinator_recovery"


class CapabilityField(Enum):
    SCHEMA_VERSION = "schema_version"
    CLI_VERSION = "cli_version"
    RUNTIME_VERSION = "runtime_version"
    MODEL = "model"
    REASONING_EFFORT = "reasoning_effort"
    SANDBOX_MODE = "sandbox_mode"
    APPROVAL_POLICY = "approval_policy"
    WORKSPACE_ROOTS = "workspace_roots"
    ADDITIONAL_WRITABLE_ROOTS = "additional_writable_roots"
    TOOL_FAMILIES = "tool_families"
    REQUIRED_APPS = "required_apps"
    REQUIRED_PLUGINS = "required_plugins"
    DELIVERY_MECHANISMS = "delivery_mechanisms"
    WAKE_MECHANISMS = "wake_mechanisms"
    WEB_MODE = "web_mode"


class ObservationFailure(Enum):
    MISSING_THREAD = "missing_thread"
    MALFORMED_THREAD = "malformed_thread"
    NO_CODEX_ANCESTOR = "no_codex_ancestor"
    NAMESPACE_PID1 = "namespace_pid1"
    HOST_ID_UNAVAILABLE = "host_id_unavailable"
    BOOT_ID_UNAVAILABLE = "boot_id_unavailable"
    PROCESS_MISSING = "process_missing"
    PROCESS_START_CHANGED = "process_start_changed"
    BOOT_CHANGED = "boot_changed"
    PROBE_UNAVAILABLE = "probe_unavailable"
    CONTRADICTORY = "contradictory"
    IDENTITY_CHANGED = "identity_changed"


class RefusalCode(Enum):
    TRANSACTION_INACTIVE = "transaction_inactive"
    EVIDENCE_TRANSACTION_MISMATCH = "evidence_transaction_mismatch"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    OWNER_MISSING = "owner_missing"
    OWNER_EXISTS = "owner_exists"
    OWNER_MISMATCH = "owner_mismatch"
    OWNER_LIVE = "owner_live"
    OWNER_LIVENESS_UNKNOWN = "owner_liveness_unknown"
    STALE_OWNER_VERSION = "stale_owner_version"
    STALE_OWNER_GENERATION = "stale_owner_generation"
    STALE_CAPABILITY = "stale_capability"
    STALE_POLICY = "stale_policy"
    STALE_ASSIGNMENT = "stale_assignment"
    STALE_CLAIM = "stale_claim"
    GRANT_MISSING = "grant_missing"
    GRANT_NOT_PREEXISTING = "grant_not_preexisting"
    GRANT_EXPIRED = "grant_expired"
    GRANT_CONSUMED = "grant_consumed"
    GRANT_MISMATCH = "grant_mismatch"
    CAPABILITY_MISSING = "capability_missing"
    CAPABILITY_REQUIREMENTS_UNSATISFIED = "capability_requirements_unsatisfied"
    ASSIGNMENT_MISSING = "assignment_missing"
    ASSIGNMENT_NOT_ACKNOWLEDGED = "assignment_not_acknowledged"
    CLAIM_CONFLICT = "claim_conflict"
    CLAIM_MISSING = "claim_missing"
    CLAIM_STATE_MISMATCH = "claim_state_mismatch"
    WORKTREE_EVIDENCE_MISMATCH = "worktree_evidence_mismatch"
    RECONCILIATION_MISSING = "reconciliation_missing"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    ADMINISTRATIVE_ENTRY_MISMATCH = "administrative_entry_mismatch"
    WAVE_EXISTS = "wave_exists"
    WAVE_MISSING = "wave_missing"


@dataclass(frozen=True, slots=True)
class LocalIdentityContext:
    thread_id: ThreadId


@dataclass(frozen=True, slots=True)
class ProcessCoordinates:
    host_instance_id: str
    boot_id: UUID
    pid: int
    start_ticks: int

    def __post_init__(self) -> None:
        _require_name(self.host_instance_id, "host_instance_id")
        if not isinstance(self.boot_id, UUID):
            raise TypeError("boot_id requires UUID")
        if self.pid <= 1:
            raise ValueError("pid must identify a host-observable non-PID1 process")
        if self.start_ticks < 0:
            raise ValueError("start_ticks must be non-negative")


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    thread_id: ThreadId
    process: ProcessCoordinates
    observed_monotonic_ns: int
    provenance: str

    def __post_init__(self) -> None:
        if self.observed_monotonic_ns < 0:
            raise ValueError("observed_monotonic_ns must be non-negative")
        if not self.provenance.strip():
            raise ValueError("process observation provenance is required")


@dataclass(frozen=True, slots=True)
class ProcessObservationUnavailable:
    reason: ObservationFailure
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("observation failure detail is required")


@dataclass(frozen=True, slots=True)
class AcceptedProcessEvidence:
    transaction_id: UUID
    observation: ProcessObservation
    revalidated_monotonic_ns: int

    def __post_init__(self) -> None:
        if self.revalidated_monotonic_ns < self.observation.observed_monotonic_ns:
            raise ValueError("accepted evidence cannot predate its observation")


@dataclass(frozen=True, slots=True)
class PhysicalTargetKey:
    host_instance_id: str
    canonical_path: str

    def __post_init__(self) -> None:
        _require_name(self.host_instance_id, "host_instance_id")
        _require_canonical_absolute_path(self.canonical_path, "canonical_path")


@dataclass(frozen=True, slots=True)
class RepositoryKey:
    host_instance_id: str
    canonical_common_dir: str

    def __post_init__(self) -> None:
        _require_name(self.host_instance_id, "host_instance_id")
        _require_canonical_absolute_path(self.canonical_common_dir, "canonical_common_dir")


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    field: CapabilityField
    evidence_class: str
    provenance: str

    def __post_init__(self) -> None:
        if not self.evidence_class.strip() or not self.provenance.strip():
            raise ValueError("capability evidence class and provenance are required")


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    schema_version: int
    cli_version: str
    runtime_version: str
    model: str
    reasoning_effort: str
    sandbox_mode: str
    approval_policy: str
    workspace_roots: tuple[str, ...]
    additional_writable_roots: tuple[str, ...]
    tool_families: tuple[str, ...]
    required_apps: tuple[str, ...]
    required_plugins: tuple[str, ...]
    delivery_mechanisms: tuple[str, ...]
    wake_mechanisms: tuple[str, ...]
    web_mode: str
    evidence: tuple[CapabilityEvidence, ...]
    snapshot_id: CapabilitySnapshotId

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("capability schema_version must be positive")
        scalar_values = (
            self.cli_version,
            self.runtime_version,
            self.model,
            self.reasoning_effort,
            self.sandbox_mode,
            self.approval_policy,
            self.web_mode,
        )
        if any(not value.strip() for value in scalar_values):
            raise ValueError("capability scalar values must be non-empty")
        for field_name in (
            "workspace_roots",
            "additional_writable_roots",
            "tool_families",
            "required_apps",
            "required_plugins",
            "delivery_mechanisms",
            "wake_mechanisms",
        ):
            values = getattr(self, field_name)
            if values != _canonical_tuple(values):
                raise ValueError(f"{field_name} must be sorted and unique")
        canonical_evidence = tuple(
            sorted(self.evidence, key=lambda item: (item.field.value, item.evidence_class, item.provenance))
        )
        if self.evidence != canonical_evidence:
            raise ValueError("capability evidence must be canonical")
        if self.snapshot_id.value != self._computed_digest():
            raise ValueError("capability snapshot id does not match immutable contents")

    @classmethod
    def create(
        cls,
        *,
        schema_version: int,
        cli_version: str,
        runtime_version: str,
        model: str,
        reasoning_effort: str,
        sandbox_mode: str,
        approval_policy: str,
        workspace_roots: tuple[str, ...] = (),
        additional_writable_roots: tuple[str, ...] = (),
        tool_families: tuple[str, ...] = (),
        required_apps: tuple[str, ...] = (),
        required_plugins: tuple[str, ...] = (),
        delivery_mechanisms: tuple[str, ...] = (),
        wake_mechanisms: tuple[str, ...] = (),
        web_mode: str,
        evidence: tuple[CapabilityEvidence, ...] = (),
    ) -> CapabilitySnapshot:
        canonical_evidence = tuple(
            sorted(evidence, key=lambda item: (item.field.value, item.evidence_class, item.provenance))
        )
        values = {
            "schema_version": schema_version,
            "cli_version": cli_version,
            "runtime_version": runtime_version,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "sandbox_mode": sandbox_mode,
            "approval_policy": approval_policy,
            "workspace_roots": _canonical_tuple(workspace_roots),
            "additional_writable_roots": _canonical_tuple(additional_writable_roots),
            "tool_families": _canonical_tuple(tool_families),
            "required_apps": _canonical_tuple(required_apps),
            "required_plugins": _canonical_tuple(required_plugins),
            "delivery_mechanisms": _canonical_tuple(delivery_mechanisms),
            "wake_mechanisms": _canonical_tuple(wake_mechanisms),
            "web_mode": web_mode,
            "evidence": canonical_evidence,
        }
        payload = cls._digest_payload(values)
        return cls(**values, snapshot_id=CapabilitySnapshotId(_sha256(payload)))

    @staticmethod
    def _digest_payload(values: dict[str, object]) -> dict[str, object]:
        payload = dict(values)
        payload["evidence"] = [
            {"field": item.field.value, "evidence_class": item.evidence_class, "provenance": item.provenance}
            for item in values["evidence"]  # type: ignore[union-attr]
        ]
        return payload

    def _computed_digest(self) -> str:
        values = {
            field: getattr(self, field)
            for field in (
                "schema_version",
                "cli_version",
                "runtime_version",
                "model",
                "reasoning_effort",
                "sandbox_mode",
                "approval_policy",
                "workspace_roots",
                "additional_writable_roots",
                "tool_families",
                "required_apps",
                "required_plugins",
                "delivery_mechanisms",
                "wake_mechanisms",
                "web_mode",
                "evidence",
            )
        }
        return _sha256(self._digest_payload(values))

    def field_values(self, field: CapabilityField) -> tuple[str, ...]:
        value = getattr(self, field.value)
        if isinstance(value, tuple):
            return value
        return (str(value),)


@dataclass(frozen=True, slots=True)
class CapabilityFieldRequirement:
    field: CapabilityField
    accepted_values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.accepted_values or self.accepted_values != _canonical_tuple(self.accepted_values):
            raise ValueError("accepted capability values must be non-empty, sorted, and unique")


@dataclass(frozen=True, slots=True)
class CapabilityRequirements:
    schema_version: int
    fields: tuple[CapabilityFieldRequirement, ...]
    digest: str

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("requirements schema_version must be positive")
        canonical = tuple(sorted(self.fields, key=lambda item: item.field.value))
        if self.fields != canonical or len({item.field for item in self.fields}) != len(self.fields):
            raise ValueError("capability requirements must be sorted with unique fields")
        _require_digest(self.digest, "capability requirements digest")
        if self.digest != self._computed_digest():
            raise ValueError("capability requirements digest does not match contents")

    @classmethod
    def create(
        cls, fields: tuple[CapabilityFieldRequirement, ...], *, schema_version: int = 1
    ) -> CapabilityRequirements:
        canonical = tuple(sorted(fields, key=lambda item: item.field.value))
        payload = {
            "schema_version": schema_version,
            "fields": [
                {"field": item.field.value, "accepted_values": item.accepted_values} for item in canonical
            ],
        }
        return cls(schema_version=schema_version, fields=canonical, digest=_sha256(payload))

    def _computed_digest(self) -> str:
        return _sha256(
            {
                "schema_version": self.schema_version,
                "fields": [
                    {"field": item.field.value, "accepted_values": item.accepted_values}
                    for item in self.fields
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class CapabilityRequirementCheck:
    satisfied: bool
    unsatisfied_fields: tuple[CapabilityField, ...]
    requirements_digest: str
    evaluated_snapshot_id: CapabilitySnapshotId


@dataclass(frozen=True, slots=True)
class RoleOwner:
    wave_id: WaveId
    role_id: RoleId
    thread_id: ThreadId
    generation_id: OwnerGenerationId
    process: ProcessCoordinates
    capability_snapshot_id: CapabilitySnapshotId
    policy_revision: int
    record_version: int

    def __post_init__(self) -> None:
        if self.policy_revision < 1 or self.record_version < 1:
            raise ValueError("owner policy and record versions must be positive")


@dataclass(frozen=True, slots=True)
class StoredAssignment:
    assignment: AssignmentRef
    wave_id: WaveId
    role_id: RoleId
    owner_generation_id: OwnerGenerationId
    capability_snapshot_id: CapabilitySnapshotId
    capability_requirements: CapabilityRequirements
    required_evidence: tuple[DurableRecordRef, ...]
    policy_revision: int
    acknowledged: bool

    def __post_init__(self) -> None:
        if self.policy_revision < 1:
            raise ValueError("assignment policy revision must be positive")
        if self.required_evidence != tuple(sorted(self.required_evidence, key=lambda item: str(item.record_id))):
            raise ValueError("required evidence references must be canonical")


@dataclass(frozen=True, slots=True)
class ExpectedOwnerBindings:
    wave_id: WaveId
    role_id: RoleId
    thread_id: ThreadId
    generation_id: OwnerGenerationId
    capability_snapshot_id: CapabilitySnapshotId
    policy_revision: int
    owner_record_version: int
    assignment: AssignmentRef | None = None
    claim_id: ClaimId | None = None


@dataclass(frozen=True, slots=True)
class OwnerCheck:
    owner: RoleOwner | None
    refusal: OwnershipRefusal | None

    @property
    def allowed(self) -> bool:
        return self.refusal is None


@dataclass(frozen=True, slots=True)
class WorktreeEvidence:
    target: PhysicalTargetKey
    repository: RepositoryKey
    exists: bool
    branch: str | None
    observed_monotonic_ns: int
    provenance: str

    def __post_init__(self) -> None:
        if self.observed_monotonic_ns < 0 or not self.provenance.strip():
            raise ValueError("worktree evidence requires time and provenance")
        if self.exists and not self.branch:
            raise ValueError("materialized worktree evidence requires a branch")


@dataclass(frozen=True, slots=True)
class WorktreeEvidenceUnavailable:
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("worktree evidence failure detail is required")


@dataclass(frozen=True, slots=True)
class WorktreeClaim:
    claim_id: ClaimId
    record_version: int
    state: ClaimState
    target: PhysicalTargetKey
    repository: RepositoryKey
    wave_id: WaveId
    issue_number: int
    branch: str
    assignment: AssignmentRef
    role_id: RoleId
    thread_id: ThreadId
    owner_generation_id: OwnerGenerationId
    file_lane_digest: str

    def __post_init__(self) -> None:
        if self.record_version < 1 or self.issue_number < 1 or not self.branch.strip():
            raise ValueError("claim version, issue, and branch must be valid")
        _require_digest(self.file_lane_digest, "file lane digest")


@dataclass(frozen=True, slots=True)
class StoredGrant:
    grant_id: GrantId
    wave_id: WaveId
    role_id: RoleId
    thread_id: ThreadId
    purpose: GrantPurpose
    policy_revision: int
    created_store_revision: int
    not_before: datetime
    expires_at: datetime
    consumed: bool
    authorized_by: CoordinatorGenerationId | None = None

    def __post_init__(self) -> None:
        _require_utc(self.not_before, "grant not_before")
        _require_utc(self.expires_at, "grant expires_at")
        if self.policy_revision < 1 or self.created_store_revision < 0 or self.expires_at <= self.not_before:
            raise ValueError("grant revisions and validity window must be valid")


@dataclass(frozen=True, slots=True)
class StoredReconciliation:
    record: DurableRecordRef
    wave_id: WaveId
    claim_id: ClaimId
    old_generation: OwnerGenerationId
    new_generation: OwnerGenerationId
    coordinator_generation: CoordinatorGenerationId
    rebound_assignment: AssignmentRef
    worktree_exists: bool
    branch: str | None


@dataclass(frozen=True, slots=True)
class OwnershipRefusal:
    code: RefusalCode
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("refusal detail is required")


@dataclass(frozen=True, slots=True)
class RegisterOwner:
    wave_id: WaveId
    role_id: RoleId
    capability_snapshot_id: CapabilitySnapshotId
    policy_revision: int
    grant_id: GrantId


@dataclass(frozen=True, slots=True)
class ReplaceDeadOwner:
    wave_id: WaveId
    role_id: RoleId
    expected_owner_version: int
    expected_generation: OwnerGenerationId
    capability_snapshot_id: CapabilitySnapshotId
    policy_revision: int


@dataclass(frozen=True, slots=True)
class AuthorizedTakeover:
    wave_id: WaveId
    role_id: RoleId
    expected_owner_version: int
    expected_generation: OwnerGenerationId
    capability_snapshot_id: CapabilitySnapshotId
    policy_revision: int
    grant_id: GrantId
    expected_coordinator_generation: CoordinatorGenerationId


@dataclass(frozen=True, slots=True)
class UpdateCapability:
    expected: ExpectedOwnerBindings
    capability_snapshot_id: CapabilitySnapshotId


OwnerChangeIntent: TypeAlias = RegisterOwner | ReplaceDeadOwner | AuthorizedTakeover | UpdateCapability


@dataclass(frozen=True, slots=True)
class PreparedOwnerChange:
    transaction_id: UUID
    expected_owner_version: int | None
    replacement: RoleOwner
    consumed_grant_id: GrantId | None
    fresh_liveness: Liveness | None


@dataclass(frozen=True, slots=True)
class ReserveClaim:
    expected: ExpectedOwnerBindings
    target: PhysicalTargetKey
    repository: RepositoryKey
    issue_number: int
    branch: str
    assignment: AssignmentRef
    file_lane_digest: str


@dataclass(frozen=True, slots=True)
class FinalizeClaim:
    expected: ExpectedOwnerBindings
    claim_id: ClaimId
    expected_claim_version: int


@dataclass(frozen=True, slots=True)
class ReleaseClaim:
    expected: ExpectedOwnerBindings
    claim_id: ClaimId
    expected_claim_version: int


@dataclass(frozen=True, slots=True)
class MarkReconciliationRequired:
    expected: ExpectedOwnerBindings
    claim_id: ClaimId
    expected_claim_version: int


ClaimChangeIntent: TypeAlias = ReserveClaim | FinalizeClaim | ReleaseClaim | MarkReconciliationRequired


@dataclass(frozen=True, slots=True)
class RebindClaimIntent:
    claim_id: ClaimId
    expected_claim_version: int
    expected_state: ClaimState
    expected_old_generation: OwnerGenerationId
    new_generation: OwnerGenerationId
    expected_coordinator_generation: CoordinatorGenerationId
    reconciliation: DurableRecordRef
    rebound_assignment: AssignmentRef


@dataclass(frozen=True, slots=True)
class PreparedClaimChange:
    transaction_id: UUID
    expected_claim_version: int | None
    replacement: WorktreeClaim
    reconciliation: DurableRecordRef | None = None


@dataclass(frozen=True, slots=True)
class BootstrapGrantSpec:
    role_id: RoleId
    thread_id: ThreadId
    purpose: GrantPurpose
    grant_id: GrantId
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class BootstrapRequest:
    wave_id: WaveId
    repository: RepositoryKey
    policy_revision: int
    grants: tuple[BootstrapGrantSpec, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PreparedBootstrap:
    transaction_id: UUID
    request: BootstrapRequest


@dataclass(frozen=True, slots=True)
class RecoveryDelegationRequest:
    wave_id: WaveId
    expected_coordinator_generation: CoordinatorGenerationId
    successor_thread_id: ThreadId
    grant_id: GrantId
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PreparedRecoveryDelegation:
    transaction_id: UUID
    request: RecoveryDelegationRequest


class TransactionClosedError(RuntimeError):
    """A prepared value or evidence escaped its active transaction."""


class TransactionMismatchError(RuntimeError):
    """A transaction-bound value was supplied to another transaction."""


class StageConflictError(RuntimeError):
    """The store rejected a staged CAS or uniqueness constraint."""


def utc_now() -> datetime:
    """Small convenience for adapters; policy code receives an injected clock."""

    return datetime.now(timezone.utc)
