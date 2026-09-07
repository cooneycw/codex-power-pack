"""Dependency-inversion ports for native wave ownership.

The storage implementation belongs to issue #205.  These protocols keep #200
pure and ensure every authority-bearing decision is made against one active,
serialized snapshot.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from .types import (
    AssignmentRef,
    CapabilitySnapshot,
    CapabilitySnapshotId,
    ClaimId,
    CorruptStore,
    DurabilityFailure,
    DurableRecordRef,
    GrantId,
    LocalIdentityContext,
    OwnerGenerationId,
    PhysicalTargetKey,
    PreparedBootstrap,
    PreparedClaimChange,
    PreparedOwnerChange,
    PreparedRecoveryDelegation,
    ProcessCoordinates,
    ProcessObservation,
    ProcessObservationUnavailable,
    RoleId,
    RoleOwner,
    SerializationConflict,
    StoreBusy,
    StoredAssignment,
    StoredGrant,
    StoredReconciliation,
    StoreUnavailable,
    WaveId,
    WorktreeClaim,
    WorktreeEvidence,
    WorktreeEvidenceUnavailable,
)


class HostProcessProbe(Protocol):
    """Bounded, read-only process observer; never waits or mutates."""

    def observe_self(
        self, context: "LocalIdentityContext"
    ) -> ProcessObservation | ProcessObservationUnavailable: ...

    def revalidate(
        self, observation: ProcessObservation
    ) -> ProcessObservation | ProcessObservationUnavailable: ...

    def observe_recorded(
        self, process: ProcessCoordinates
    ) -> ProcessCoordinates | ProcessObservationUnavailable: ...


class WorktreeEvidenceProbe(Protocol):
    def canonicalize_target(self, path: Path) -> PhysicalTargetKey | WorktreeEvidenceUnavailable: ...

    def inspect(self, target: PhysicalTargetKey) -> WorktreeEvidence | WorktreeEvidenceUnavailable: ...


class Clock(Protocol):
    def now_utc(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class IdFactory(Protocol):
    def new_owner_generation_id(self) -> OwnerGenerationId: ...

    def new_claim_id(self) -> ClaimId: ...


class OwnershipTransaction(Protocol):
    @property
    def transaction_id(self) -> UUID: ...

    @property
    def is_active(self) -> bool: ...

    @property
    def base_store_revision(self) -> int: ...

    def read_owner(self, wave_id: WaveId, role_id: RoleId) -> RoleOwner | None: ...

    def read_policy_revision(self, wave_id: WaveId) -> int: ...

    def read_capability(self, snapshot_id: CapabilitySnapshotId) -> CapabilitySnapshot | None: ...

    def read_preexisting_grant(self, grant_id: GrantId) -> StoredGrant | None: ...

    def read_assignment(self, assignment: AssignmentRef) -> StoredAssignment | None: ...

    def read_reconciliation(self, record: DurableRecordRef) -> StoredReconciliation | None: ...

    def read_claim(self, claim_id: ClaimId) -> WorktreeClaim | None: ...

    def read_active_claim_for_target(self, target: PhysicalTargetKey) -> WorktreeClaim | None: ...

    def stage_owner_change(self, change: PreparedOwnerChange) -> None: ...

    def stage_claim_change(self, change: PreparedClaimChange) -> None: ...


class BootstrapTransaction(Protocol):
    @property
    def transaction_id(self) -> UUID: ...

    @property
    def is_active(self) -> bool: ...

    @property
    def base_store_revision(self) -> int: ...

    @property
    def administrative_entry(self) -> Literal["bootstrap", "recovery"]: ...

    def wave_exists(self, wave_id: WaveId) -> bool: ...

    def read_owner(self, wave_id: WaveId, role_id: RoleId) -> RoleOwner | None: ...

    def stage_bootstrap(self, change: PreparedBootstrap) -> None: ...

    def stage_recovery_delegation(self, change: PreparedRecoveryDelegation) -> None: ...


__all__ = [
    "BootstrapTransaction",
    "Clock",
    "CorruptStore",
    "DurabilityFailure",
    "HostProcessProbe",
    "IdFactory",
    "OwnershipTransaction",
    "SerializationConflict",
    "StoreBusy",
    "StoreUnavailable",
    "WorktreeEvidenceProbe",
]
