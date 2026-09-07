"""Transaction-bound worktree reservation and reconciliation policy."""

from __future__ import annotations

import stat
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .ports import Clock, IdFactory, OwnershipTransaction
from .registry import check_owner, evaluate_assignment_capabilities
from .types import (
    AcceptedProcessEvidence,
    ClaimChangeIntent,
    ClaimState,
    ExpectedOwnerBindings,
    FinalizeClaim,
    MarkReconciliationRequired,
    OwnershipRefusal,
    PhysicalTargetKey,
    PreparedClaimChange,
    RebindClaimIntent,
    RefusalCode,
    ReleaseClaim,
    RepositoryKey,
    ReserveClaim,
    RoleId,
    TransactionClosedError,
    TransactionMismatchError,
    WorktreeClaim,
    WorktreeEvidence,
    WorktreeEvidenceUnavailable,
)


class LocalWorktreeEvidenceProbe:
    """Bounded filesystem/Git-metadata observer used outside the DB lock.

    It never invokes Git or mutates the filesystem. Linked-worktree metadata is
    resolved through ``.git`` and ``commondir`` with every read size-capped.
    """

    def __init__(
        self,
        expected_repository: RepositoryKey,
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        max_metadata_bytes: int = 4096,
    ) -> None:
        if max_metadata_bytes < 64 or max_metadata_bytes > 65536:
            raise ValueError("max_metadata_bytes must be between 64 and 65536")
        self._expected_repository = expected_repository
        self._monotonic_ns = monotonic_ns
        self._max_metadata_bytes = max_metadata_bytes

    def _read_metadata(self, path: Path) -> str:
        with path.open("r", encoding="utf-8") as handle:
            value = handle.read(self._max_metadata_bytes + 1)
        if len(value) > self._max_metadata_bytes:
            raise ValueError(f"metadata file is larger than {self._max_metadata_bytes} bytes")
        return value.strip()

    @staticmethod
    def _has_symlink_component(path: Path) -> bool:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                break
            if stat.S_ISLNK(mode):
                return True
        return False

    def canonicalize_target(self, path: Path) -> PhysicalTargetKey | WorktreeEvidenceUnavailable:
        raw = str(path)
        if "\0" in raw or raw.startswith("//") or not path.is_absolute():
            return WorktreeEvidenceUnavailable("target path spelling is ambiguous or non-absolute")
        try:
            if self._has_symlink_component(path):
                return WorktreeEvidenceUnavailable("target path contains a symlink component")
            if path.exists():
                canonical = path.resolve(strict=True)
            else:
                canonical = path.parent.resolve(strict=True) / path.name
        except (OSError, RuntimeError):
            return WorktreeEvidenceUnavailable("target path cannot be resolved through an existing parent")
        try:
            return PhysicalTargetKey(self._expected_repository.host_instance_id, str(canonical))
        except (TypeError, ValueError) as exc:
            return WorktreeEvidenceUnavailable(f"target path is not canonical: {exc}")

    def inspect(self, target: PhysicalTargetKey) -> WorktreeEvidence | WorktreeEvidenceUnavailable:
        if target.host_instance_id != self._expected_repository.host_instance_id:
            return WorktreeEvidenceUnavailable("target and expected repository are on different hosts")
        path = Path(target.canonical_path)
        canonical = self.canonicalize_target(path)
        if isinstance(canonical, WorktreeEvidenceUnavailable):
            return canonical
        if canonical != target:
            return WorktreeEvidenceUnavailable("target key no longer matches its canonical filesystem identity")
        if not path.exists():
            return WorktreeEvidence(
                target,
                self._expected_repository,
                False,
                None,
                self._monotonic_ns(),
                "bounded-filesystem-git-metadata",
            )
        try:
            if str(path.resolve(strict=True)) != target.canonical_path or not path.is_dir():
                return WorktreeEvidenceUnavailable("materialized target changed identity or is not a directory")
            dot_git = path / ".git"
            if dot_git.is_symlink():
                return WorktreeEvidenceUnavailable("worktree .git metadata cannot be a symlink")
            if dot_git.is_file():
                pointer = self._read_metadata(dot_git)
                if not pointer.startswith("gitdir: "):
                    return WorktreeEvidenceUnavailable("worktree .git pointer is malformed")
                raw_git_dir = Path(pointer.removeprefix("gitdir: "))
                if raw_git_dir.is_absolute():
                    git_dir = raw_git_dir.resolve(strict=True)
                else:
                    git_dir = (path / raw_git_dir).resolve(strict=True)
                if self._has_symlink_component(git_dir):
                    return WorktreeEvidenceUnavailable("linked-worktree admin path contains a symlink")
                backlink_path = git_dir / "gitdir"
                if backlink_path.is_symlink():
                    return WorktreeEvidenceUnavailable("linked-worktree backlink cannot be a symlink")
                backlink = Path(self._read_metadata(backlink_path))
                if not backlink.is_absolute():
                    backlink = git_dir / backlink
                if backlink.resolve(strict=True) != dot_git.resolve(strict=True):
                    return WorktreeEvidenceUnavailable("linked-worktree backlink names a different target")
            elif dot_git.is_dir():
                git_dir = dot_git.resolve(strict=True)
            else:
                return WorktreeEvidenceUnavailable("target is not a Git worktree")
            commondir = git_dir / "commondir"
            if commondir.is_symlink():
                return WorktreeEvidenceUnavailable("Git commondir metadata cannot be a symlink")
            if commondir.is_file():
                common_pointer = Path(self._read_metadata(commondir))
                common_dir = (git_dir / common_pointer).resolve(strict=True)
            else:
                common_dir = git_dir
            observed_repository = RepositoryKey(target.host_instance_id, str(common_dir))
            if observed_repository != self._expected_repository:
                return WorktreeEvidenceUnavailable("target belongs to a foreign Git common directory")
            head_path = git_dir / "HEAD"
            if head_path.is_symlink():
                return WorktreeEvidenceUnavailable("Git HEAD metadata cannot be a symlink")
            head = self._read_metadata(head_path)
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            return WorktreeEvidenceUnavailable(f"worktree metadata is unavailable: {exc}")
        prefix = "ref: refs/heads/"
        if not head.startswith(prefix) or not head.removeprefix(prefix):
            return WorktreeEvidenceUnavailable("detached or malformed worktree HEAD is not claimable")
        return WorktreeEvidence(
            target,
            observed_repository,
            True,
            head.removeprefix(prefix),
            self._monotonic_ns(),
            "bounded-filesystem-git-metadata",
        )


def _refuse(code: RefusalCode, detail: str) -> OwnershipRefusal:
    return OwnershipRefusal(code, detail)


def _checked_owner(
    tx: OwnershipTransaction,
    evidence: AcceptedProcessEvidence,
    expected: ExpectedOwnerBindings,
):
    checked = check_owner(tx, evidence, expected)
    if not checked.allowed:
        assert checked.refusal is not None
        return checked.refusal
    assert checked.owner is not None
    return checked.owner


def prepare_claim_change(
    tx: OwnershipTransaction,
    evidence: AcceptedProcessEvidence,
    intent: ClaimChangeIntent,
    worktree: WorktreeEvidence | None,
    ids: IdFactory,
    clock: Clock,
) -> PreparedClaimChange | OwnershipRefusal:
    """Prepare a claim CAS; callers stage it in the same active transaction."""

    del clock  # The evidence timestamp is recorded; wall time grants no authority.
    owner = _checked_owner(tx, evidence, intent.expected)
    if isinstance(owner, OwnershipRefusal):
        return owner

    if isinstance(intent, ReserveClaim):
        if intent.expected.assignment != intent.assignment:
            return _refuse(RefusalCode.STALE_ASSIGNMENT, "reservation assignment differs from owner check")
        if worktree is None or worktree.target != intent.target or worktree.repository != intent.repository:
            return _refuse(RefusalCode.WORKTREE_EVIDENCE_MISMATCH, "reservation target evidence differs")
        if worktree.exists:
            return _refuse(
                RefusalCode.WORKTREE_EVIDENCE_MISMATCH,
                "an existing materialization requires explicit reconciliation, not reservation",
            )
        conflict = tx.read_active_claim_for_target(intent.target)
        if conflict is not None and conflict.state is not ClaimState.RELEASED:
            return _refuse(
                RefusalCode.CLAIM_CONFLICT,
                "physical target is already reserved, including across repositories or waves",
            )
        claim = WorktreeClaim(
            claim_id=ids.new_claim_id(),
            record_version=1,
            state=ClaimState.RESERVED,
            target=intent.target,
            repository=intent.repository,
            wave_id=owner.wave_id,
            issue_number=intent.issue_number,
            branch=intent.branch,
            assignment=intent.assignment,
            role_id=owner.role_id,
            thread_id=owner.thread_id,
            owner_generation_id=owner.generation_id,
            file_lane_digest=intent.file_lane_digest,
        )
        return PreparedClaimChange(tx.transaction_id, None, claim)

    current = tx.read_claim(intent.claim_id)
    if current is None:
        return _refuse(RefusalCode.CLAIM_MISSING, "claim record is absent")
    if current.record_version != intent.expected_claim_version:
        return _refuse(RefusalCode.STALE_CLAIM, "claim version changed")
    if (
        current.wave_id != owner.wave_id
        or current.role_id != owner.role_id
        or current.thread_id != owner.thread_id
        or current.owner_generation_id != owner.generation_id
    ):
        return _refuse(RefusalCode.STALE_CLAIM, "claim belongs to another owner generation")

    if isinstance(intent, FinalizeClaim):
        if current.state is not ClaimState.RESERVED:
            return _refuse(RefusalCode.CLAIM_STATE_MISMATCH, "only a reserved claim can be finalized")
        if (
            worktree is None
            or not worktree.exists
            or worktree.target != current.target
            or worktree.repository != current.repository
            or worktree.branch != current.branch
        ):
            return _refuse(RefusalCode.WORKTREE_EVIDENCE_MISMATCH, "materialized worktree does not match claim")
        state = ClaimState.MATERIALIZED
    elif isinstance(intent, ReleaseClaim):
        state = ClaimState.RELEASED
    elif isinstance(intent, MarkReconciliationRequired):
        if current.state is ClaimState.RELEASED:
            return _refuse(RefusalCode.CLAIM_STATE_MISMATCH, "released claim cannot require reconciliation")
        state = ClaimState.RECONCILE_REQUIRED
    else:  # pragma: no cover - the closed union is exhaustive
        raise TypeError(f"unsupported claim intent: {type(intent).__name__}")
    return PreparedClaimChange(
        transaction_id=tx.transaction_id,
        expected_claim_version=current.record_version,
        replacement=replace(current, record_version=current.record_version + 1, state=state),
    )


def prepare_claim_reconciliation(
    tx: OwnershipTransaction,
    coordinator_evidence: AcceptedProcessEvidence,
    intent: RebindClaimIntent,
    worktree: WorktreeEvidence,
) -> PreparedClaimChange | OwnershipRefusal:
    """Rebind a crash-preserved claim under current coordinator CAS authority."""

    if not tx.is_active:
        raise TransactionClosedError("claim reconciliation requires an active transaction")
    if coordinator_evidence.transaction_id != tx.transaction_id:
        raise TransactionMismatchError("coordinator evidence belongs to another transaction")
    claim = tx.read_claim(intent.claim_id)
    if claim is None:
        return _refuse(RefusalCode.CLAIM_MISSING, "claim record is absent")
    if claim.record_version != intent.expected_claim_version:
        return _refuse(RefusalCode.STALE_CLAIM, "claim version changed")
    if claim.state is not intent.expected_state or claim.owner_generation_id != intent.expected_old_generation:
        return _refuse(RefusalCode.CLAIM_STATE_MISMATCH, "claim reconciliation compare values changed")
    if claim.state is not ClaimState.RECONCILE_REQUIRED:
        return _refuse(RefusalCode.CLAIM_STATE_MISMATCH, "only reconcile-required claims can be rebound")

    coordinator = tx.read_owner(claim.wave_id, RoleId("coordinator"))
    if coordinator is None:
        return _refuse(RefusalCode.OWNER_MISSING, "current coordinator is absent")
    if (
        coordinator.generation_id.value != intent.expected_coordinator_generation.value
        or coordinator.thread_id != coordinator_evidence.observation.thread_id
        or coordinator.process != coordinator_evidence.observation.process
    ):
        return _refuse(RefusalCode.STALE_OWNER_GENERATION, "coordinator CAS or process evidence changed")

    reconciliation = tx.read_reconciliation(intent.reconciliation)
    if reconciliation is None:
        return _refuse(RefusalCode.RECONCILIATION_MISSING, "durable reconciliation record is absent")
    if (
        reconciliation.record != intent.reconciliation
        or reconciliation.wave_id != claim.wave_id
        or reconciliation.claim_id != claim.claim_id
        or reconciliation.old_generation != intent.expected_old_generation
        or reconciliation.new_generation != intent.new_generation
        or reconciliation.coordinator_generation != intent.expected_coordinator_generation
        or reconciliation.rebound_assignment != intent.rebound_assignment
    ):
        return _refuse(RefusalCode.RECONCILIATION_MISMATCH, "reconciliation authority differs")
    assignment = tx.read_assignment(intent.rebound_assignment)
    if (
        assignment is None
        or not assignment.acknowledged
        or assignment.wave_id != claim.wave_id
        or assignment.role_id != claim.role_id
        or assignment.owner_generation_id != intent.new_generation
    ):
        return _refuse(RefusalCode.STALE_ASSIGNMENT, "rebound assignment is absent, stale, or unacknowledged")
    successor = tx.read_owner(claim.wave_id, claim.role_id)
    if successor is None or successor.generation_id != intent.new_generation:
        return _refuse(RefusalCode.STALE_OWNER_GENERATION, "successor owner generation is not current")
    if tx.read_policy_revision(claim.wave_id) != successor.policy_revision:
        return _refuse(RefusalCode.STALE_POLICY, "wave policy changed before reconciliation")
    if assignment.policy_revision != successor.policy_revision:
        return _refuse(RefusalCode.STALE_POLICY, "rebound assignment policy is stale")
    current_capability = tx.read_capability(successor.capability_snapshot_id)
    if current_capability is None:
        return _refuse(RefusalCode.CAPABILITY_MISSING, "successor capability snapshot is absent")
    if not evaluate_assignment_capabilities(current_capability, assignment).satisfied:
        return _refuse(
            RefusalCode.CAPABILITY_REQUIREMENTS_UNSATISFIED,
            "successor no longer satisfies rebound assignment requirements",
        )
    if (
        worktree.target != claim.target
        or worktree.repository != claim.repository
        or worktree.exists != reconciliation.worktree_exists
        or worktree.branch != reconciliation.branch
    ):
        return _refuse(RefusalCode.WORKTREE_EVIDENCE_MISMATCH, "fresh worktree evidence differs from record")
    state = ClaimState.MATERIALIZED if worktree.exists else ClaimState.RESERVED
    replacement = replace(
        claim,
        record_version=claim.record_version + 1,
        state=state,
        assignment=intent.rebound_assignment,
        thread_id=successor.thread_id,
        owner_generation_id=successor.generation_id,
    )
    return PreparedClaimChange(tx.transaction_id, claim.record_version, replacement, intent.reconciliation)


__all__ = ["LocalWorktreeEvidenceProbe", "prepare_claim_change", "prepare_claim_reconciliation"]
