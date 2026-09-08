"""Actual SQLite durability, concurrency, and transaction witnesses for #205."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from lib.native_wave.event_types import (
    ActorBinding,
    EventDisposition,
    EventId,
    EventKind,
    EventPayload,
    NativeCommand,
    ProvenanceClass,
    ProvenanceEvidence,
    canonical_record,
    receipt_from_bytes,
)
from lib.native_wave.storage import SQLiteWaveStore, StoreConfig, default_store_path
from lib.native_wave.types import (
    BootstrapGrantSpec,
    BootstrapRequest,
    CapabilityEvidence,
    CapabilityField,
    CapabilitySnapshot,
    ClaimId,
    ClaimState,
    CorruptStore,
    DurabilityFailure,
    GrantId,
    GrantPurpose,
    OwnerGenerationId,
    PhysicalTargetKey,
    PreparedBootstrap,
    PreparedClaimChange,
    PreparedOwnerChange,
    ProcessCoordinates,
    RepositoryKey,
    RoleId,
    RoleOwner,
    SerializationConflict,
    StoreBusy,
    StoreUnavailable,
    ThreadId,
    TransactionClosedError,
    TransactionMismatchError,
    WaveId,
    WorktreeClaim,
)

NOW = datetime(2026, 9, 7, 18, 0, tzinfo=timezone.utc)
ROLE = RoleId("worker-A")
THREAD = ThreadId(UUID(int=801))
GENERATION = OwnerGenerationId(UUID(int=802))
ACTOR = ActorBinding(ROLE, THREAD, GENERATION)
DIGEST = "sha256:" + "a" * 64


def _config(tmp_path: Path, *, name: str = "wave.sqlite3", timeout: int = 100) -> StoreConfig:
    tmp_path.chmod(0o700)
    return StoreConfig(tmp_path / name, busy_timeout_ms=timeout)


def _command(
    wave_id: WaveId,
    value: int,
    *,
    kind: EventKind = EventKind.PROSE_MESSAGE,
    payload: EventPayload | None = None,
    effect: Any = None,
) -> NativeCommand:
    if payload is None:
        payload = EventPayload.from_mapping({"text": f"event-{value}"})
    return NativeCommand(
        EventId(UUID(int=value)),
        kind,
        wave_id,
        ACTOR,
        ProvenanceEvidence(ProvenanceClass.REGISTRY_BOUND_LOCAL, "storage-test"),
        payload=payload,
        effect=canonical_record() if effect is None else effect,
    )


def _snapshot(model: str = "worker-model") -> CapabilitySnapshot:
    return CapabilitySnapshot.create(
        schema_version=1,
        cli_version="1.0",
        runtime_version="python-3.11",
        model=model,
        reasoning_effort="high",
        sandbox_mode="danger-full-access",
        approval_policy="never",
        workspace_roots=("/repos",),
        tool_families=("shell",),
        required_plugins=("flow",),
        delivery_mechanisms=("mailbox",),
        wake_mechanisms=("watch",),
        web_mode="disabled",
        captured_at=NOW,
        evidence=(CapabilityEvidence(CapabilityField.MODEL, "runtime", "fixture"),),
    )


def _bootstrap(
    store: SQLiteWaveStore,
    wave_id: WaveId,
    *,
    grant_id: GrantId | None = None,
) -> BootstrapRequest:
    grants = (
        ()
        if grant_id is None
        else (
            BootstrapGrantSpec(
                ROLE,
                THREAD,
                GrantPurpose.REGISTER,
                grant_id,
                NOW + timedelta(hours=1),
            ),
        )
    )
    request = BootstrapRequest(
        wave_id,
        RepositoryKey("test-host", f"/repos/{wave_id}/.git"),
        1,
        grants,
        NOW,
    )
    command = _command(
        wave_id,
        1,
        kind=EventKind.WAVE_BOOTSTRAPPED,
        payload=EventPayload.from_mapping({"operator_reason": "storage fixture"}),
        effect=canonical_record(request=request),
    )
    with store.transaction(administrative_entry="bootstrap") as tx:
        committing_revision = tx.base_store_revision + 1
        tx.append_event(
            command,
            disposition=EventDisposition.APPLIED,
            reason=None,
            validation_facts=canonical_record(created_store_revision=committing_revision),
            committed_at=NOW,
        )
        tx.stage_bootstrap(PreparedBootstrap(tx.transaction_id, request))
        tx.commit()
    return request


def _claim(
    wave_id: WaveId,
    claim_id: ClaimId,
    *,
    target: PhysicalTargetKey,
    version: int = 1,
    state: ClaimState = ClaimState.RESERVED,
) -> WorktreeClaim:
    from lib.native_wave.types import AssignmentRef

    return WorktreeClaim(
        claim_id,
        version,
        state,
        target,
        RepositoryKey("test-host", f"/repos/{wave_id}/.git"),
        wave_id,
        205,
        f"issue-205-{wave_id}",
        AssignmentRef(UUID(int=900), 1, DIGEST),
        ROLE,
        THREAD,
        GENERATION,
        DIGEST,
    )


def test_default_path_secure_create_open_and_existing_only_failures(tmp_path: Path) -> None:
    assert default_store_path({"XDG_STATE_HOME": "/state"}) == Path("/state/codex-power-pack/native-wave-v1.sqlite3")
    for value in ("", "relative"):
        with pytest.raises(StoreUnavailable):
            default_store_path({"XDG_STATE_HOME": value})

    config = _config(tmp_path)
    store = SQLiteWaveStore.create(config)
    before = config.path.stat()
    assert before.st_mode & 0o777 == 0o600
    assert SQLiteWaveStore.open(config).store_id == store.store_id
    with pytest.raises(StoreUnavailable, match="refusing to replace"):
        SQLiteWaveStore.create(config)
    after = config.path.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
    assert SQLiteWaveStore.open(config).store_id == store.store_id

    missing = _config(tmp_path, name="missing.sqlite3")
    with pytest.raises(StoreUnavailable):
        SQLiteWaveStore.open(missing)
    assert not missing.path.exists()

    config.path.unlink()
    with pytest.raises(StoreUnavailable):
        with store.connection():
            pass
    assert not config.path.exists()


def test_secure_parent_and_two_creator_race_preserve_the_winner(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(StoreUnavailable, match="symlinks or aliases"):
        SQLiteWaveStore.create(StoreConfig(alias / "unsafe.sqlite3"))
    assert not (real_parent / "unsafe.sqlite3").exists()

    race_parent = tmp_path / "race"
    race_parent.mkdir(mode=0o700)
    config = StoreConfig(race_parent / "wave.sqlite3", busy_timeout_ms=1_000)
    barrier = threading.Barrier(2)
    successes: list[str] = []
    failures: list[BaseException] = []

    def create() -> None:
        barrier.wait()
        try:
            successes.append(SQLiteWaveStore.create(config).store_id)
        except BaseException as exc:  # captured for deterministic parent-thread assertions
            failures.append(exc)

    threads = [threading.Thread(target=create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)
    assert len(successes) == 1
    assert len(failures) == 1 and isinstance(failures[0], StoreUnavailable)
    assert SQLiteWaveStore.open(config).store_id == successes[0]


def test_transaction_lifetime_rollback_and_grant_commit_revision(tmp_path: Path) -> None:
    store = SQLiteWaveStore.create(_config(tmp_path))
    wave = WaveId("grant-wave")
    grant_id = GrantId(UUID(int=810))
    request = _bootstrap(store, wave, grant_id=grant_id)

    with store.transaction() as tx:
        assert tx.base_store_revision == 1
        grant = tx.read_preexisting_grant(grant_id)
        assert grant is not None
        assert grant.created_store_revision == 1
        row = tx._connection.execute(
            "SELECT validation_facts_json FROM events WHERE wave_id=? AND sequence=1",
            (str(wave),),
        ).fetchone()
        assert row is not None
        assert json.loads(bytes(row[0]))["created_store_revision"] == grant.created_store_revision

        snapshot = _snapshot()
        owner = RoleOwner(
            wave,
            ROLE,
            THREAD,
            GENERATION,
            ProcessCoordinates("test-host", UUID(int=811), 5001, 101),
            snapshot.snapshot_id,
            1,
            1,
        )
        registration = _command(wave, 2)
        tx.append_event(registration, disposition=EventDisposition.APPLIED, reason=None, committed_at=NOW)
        tx.stage_capability(snapshot)
        tx.stage_owner_change(PreparedOwnerChange(tx.transaction_id, None, owner, grant_id, None))
        tx.commit()
    assert not tx.is_active
    with pytest.raises(TransactionClosedError):
        tx.read_preexisting_grant(grant_id)

    with store.transaction() as check:
        grant = check.read_preexisting_grant(grant_id)
        assert grant is not None and grant.consumed
        assert check.read_owner(wave, ROLE) == owner

    stale_owner_event = _command(wave, 5)
    stale_owner = replace(owner, record_version=2)
    with pytest.raises(SerializationConflict, match="owner compare-and-swap"):
        with store.transaction() as stale_tx:
            stale_tx.append_event(
                stale_owner_event,
                disposition=EventDisposition.APPLIED,
                reason=None,
                committed_at=NOW,
            )
            stale_tx.stage_owner_change(PreparedOwnerChange(stale_tx.transaction_id, 99, stale_owner, None, None))
    with store.transaction() as check:
        assert check.lookup_event(wave, stale_owner_event.event_id) is None
        assert check.read_owner(wave, ROLE) == owner

    rollback_command = _command(wave, 3)
    with pytest.raises(RuntimeError, match="rollback fixture"):
        with store.transaction() as rollback:
            rollback.append_event(
                rollback_command,
                disposition=EventDisposition.APPLIED,
                reason=None,
                committed_at=NOW,
            )
            raise RuntimeError("rollback fixture")
    with store.transaction() as check:
        assert check.lookup_event(wave, rollback_command.event_id) is None

    isolated = SQLiteWaveStore.create(_config(tmp_path, name="same-transaction.sqlite3"))
    same_wave = WaveId("same-transaction-wave")
    same_grant = GrantId(UUID(int=812))
    same_request = BootstrapRequest(
        same_wave,
        RepositoryKey("test-host", "/repos/same/.git"),
        1,
        (
            BootstrapGrantSpec(
                ROLE,
                THREAD,
                GrantPurpose.REGISTER,
                same_grant,
                NOW + timedelta(hours=1),
            ),
        ),
        NOW,
    )
    bootstrap = _command(
        same_wave,
        1,
        kind=EventKind.WAVE_BOOTSTRAPPED,
        payload=EventPayload.from_mapping({"operator_reason": "same transaction"}),
        effect=canonical_record(request=same_request),
    )
    with isolated.transaction(administrative_entry="bootstrap") as same_tx:
        same_tx.append_event(bootstrap, disposition=EventDisposition.APPLIED, reason=None, committed_at=NOW)
        same_tx.stage_bootstrap(PreparedBootstrap(same_tx.transaction_id, same_request))
        snapshot = _snapshot("same-transaction")
        same_tx.stage_capability(snapshot)
        owner = replace(owner, wave_id=same_wave, capability_snapshot_id=snapshot.snapshot_id)
        with pytest.raises(SerializationConflict, match="grant consumption"):
            same_tx.stage_owner_change(PreparedOwnerChange(same_tx.transaction_id, None, owner, same_grant, None))
    with isolated.transaction() as check:
        assert not check.wave_exists(same_wave)

    with store.transaction() as wrong_tx:
        wrong_tx.append_event(
            _command(wave, 4),
            disposition=EventDisposition.APPLIED,
            reason=None,
            committed_at=NOW,
        )
        with pytest.raises(TransactionMismatchError):
            wrong_tx.stage_owner_change(PreparedOwnerChange(UUID(int=999), owner.record_version, owner, None, None))
    assert request.wave_id == wave


def test_concurrent_duplicate_append_and_read_visibility_are_atomic(tmp_path: Path) -> None:
    store = SQLiteWaveStore.create(_config(tmp_path, timeout=1_000))
    wave = WaveId("dedup-wave")
    _bootstrap(store, wave)
    command = _command(wave, 20)

    with store.transaction() as writer:
        writer.append_event(command, disposition=EventDisposition.APPLIED, reason=None, committed_at=NOW)
        with store.connection() as reader:
            count = reader.execute(
                "SELECT COUNT(*) FROM events WHERE wave_id=? AND event_id=?",
                (str(wave), str(command.event_id)),
            ).fetchone()
            assert count is not None and int(count[0]) == 0
        writer.rollback()

    barrier = threading.Barrier(2)
    receipts: list[bytes] = []
    errors: list[BaseException] = []

    def append_once() -> None:
        barrier.wait()
        try:
            with store.transaction() as tx:
                existing = tx.lookup_event(wave, command.event_id)
                if existing is None:
                    receipt = tx.append_event(
                        command,
                        disposition=EventDisposition.APPLIED,
                        reason=None,
                        committed_at=NOW,
                    )
                    tx.commit()
                    assert receipt.sequence is not None
                    receipts.append(existing_receipt_bytes(store, wave, command.event_id))
                else:
                    receipts.append(existing.receipt_bytes)
        except BaseException as exc:  # captured for deterministic parent-thread assertions
            errors.append(exc)

    threads = [threading.Thread(target=append_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(receipts) == 2 and receipts[0] == receipts[1]
    receipt = receipt_from_bytes(receipts[0])
    assert receipt.sequence == 2
    with store.transaction() as tx:
        count = tx._connection.execute(
            "SELECT COUNT(*) FROM events WHERE wave_id=? AND event_id=?",
            (str(wave), str(command.event_id)),
        ).fetchone()
        assert count is not None and int(count[0]) == 1


def existing_receipt_bytes(store: SQLiteWaveStore, wave: WaveId, event_id: EventId) -> bytes:
    with store.transaction() as tx:
        existing = tx.lookup_event(wave, event_id)
        assert existing is not None
        return existing.receipt_bytes


def test_claim_cas_cross_wave_target_exclusion_and_atomic_rollback(tmp_path: Path) -> None:
    store = SQLiteWaveStore.create(_config(tmp_path))
    wave_a = WaveId("claim-wave-a")
    wave_b = WaveId("claim-wave-b")
    _bootstrap(store, wave_a)
    _bootstrap(store, wave_b)
    target = PhysicalTargetKey("test-host", "/worktrees/shared-target")
    claim_a = _claim(wave_a, ClaimId(UUID(int=820)), target=target)
    claim_b = _claim(wave_b, ClaimId(UUID(int=821)), target=target)

    with store.transaction() as tx:
        tx.append_event(_command(wave_a, 30), disposition=EventDisposition.APPLIED, reason=None, committed_at=NOW)
        tx.stage_claim_change(PreparedClaimChange(tx.transaction_id, None, claim_a))
        tx.commit()

    conflicting_event = _command(wave_b, 31)
    with pytest.raises(SerializationConflict, match="physical target"):
        with store.transaction() as tx:
            tx.append_event(
                conflicting_event,
                disposition=EventDisposition.APPLIED,
                reason=None,
                committed_at=NOW,
            )
            tx.stage_claim_change(PreparedClaimChange(tx.transaction_id, None, claim_b))
    with store.transaction() as tx:
        assert tx.lookup_event(wave_b, conflicting_event.event_id) is None
        assert tx.read_claim(claim_b.claim_id) is None
        assert tx.read_active_claim_for_target(target) == claim_a

    barrier = threading.Barrier(2)
    winners: list[WorktreeClaim] = []
    conflicts: list[BaseException] = []
    candidates = (
        replace(claim_a, record_version=2, state=ClaimState.MATERIALIZED),
        replace(claim_a, record_version=2, state=ClaimState.RECONCILE_REQUIRED),
    )

    def update_claim(value: int, replacement: WorktreeClaim) -> None:
        barrier.wait()
        try:
            with store.transaction() as tx:
                tx.append_event(
                    _command(wave_a, value),
                    disposition=EventDisposition.APPLIED,
                    reason=None,
                    committed_at=NOW,
                )
                tx.stage_claim_change(PreparedClaimChange(tx.transaction_id, 1, replacement))
                tx.commit()
                winners.append(replacement)
        except BaseException as exc:  # captured for deterministic parent-thread assertions
            conflicts.append(exc)

    threads = [
        threading.Thread(target=update_claim, args=(40 + index, candidate))
        for index, candidate in enumerate(candidates)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)
    assert len(winners) == 1
    assert len(conflicts) == 1 and isinstance(conflicts[0], SerializationConflict)
    current_claim = winners[0]
    with store.transaction() as tx:
        assert tx.read_claim(claim_a.claim_id) == current_claim
        committed = sum(tx.lookup_event(wave_a, EventId(UUID(int=value))) is not None for value in (40, 41))
        assert committed == 1

    wrong_cas_event = _command(wave_a, 32)
    released = replace(current_claim, record_version=3, state=ClaimState.RELEASED)
    with pytest.raises(SerializationConflict, match="compare-and-swap"):
        with store.transaction() as tx:
            tx.append_event(
                wrong_cas_event,
                disposition=EventDisposition.APPLIED,
                reason=None,
                committed_at=NOW,
            )
            tx.stage_claim_change(PreparedClaimChange(tx.transaction_id, 99, released))
    with store.transaction() as tx:
        assert tx.lookup_event(wave_a, wrong_cas_event.event_id) is None
        assert tx.read_claim(claim_a.claim_id) == current_claim

    with store.transaction() as tx:
        tx.append_event(_command(wave_a, 33), disposition=EventDisposition.APPLIED, reason=None, committed_at=NOW)
        tx.stage_claim_change(PreparedClaimChange(tx.transaction_id, 2, released))
        tx.commit()
    with store.transaction() as tx:
        assert tx.read_claim(claim_a.claim_id) == released


def test_bounded_lock_timeout_and_uncertain_commit_same_id_recovery(tmp_path: Path) -> None:
    store = SQLiteWaveStore.create(_config(tmp_path, timeout=30))
    wave = WaveId("durability-wave")
    _bootstrap(store, wave)
    with store.connection() as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        with pytest.raises(StoreBusy, match="timed out"):
            with store.transaction():
                pass
        assert time.monotonic() - started < 1
        blocker.rollback()

    command = _command(wave, 40)

    class CommitThenRaise:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection

        def __getattr__(self, name: str) -> Any:
            return getattr(self.connection, name)

        def commit(self) -> None:
            self.connection.commit()
            raise sqlite3.OperationalError("simulated acknowledgement loss")

    with store.transaction() as tx:
        original = tx.append_event(
            command,
            disposition=EventDisposition.APPLIED,
            reason=None,
            committed_at=NOW,
        )
        tx._connection = CommitThenRaise(tx._connection)  # type: ignore[assignment]
        with pytest.raises(DurabilityFailure, match="outcome is unknown"):
            tx.commit()
    assert not tx.is_active
    with store.transaction() as recovered:
        existing = recovered.lookup_event(wave, command.event_id)
        assert existing is not None
        replayed = receipt_from_bytes(existing.receipt_bytes)
        assert replayed == original


def test_schema_corruption_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    SQLiteWaveStore.create(config)
    connection = sqlite3.connect(config.path)
    try:
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(CorruptStore, match="schema version"):
        SQLiteWaveStore.open(config)
    assert os.path.exists(config.path)
