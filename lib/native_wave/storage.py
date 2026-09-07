"""SQLite durability and transaction core for native-wave state (#205)."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import UUID, uuid4

from .event_types import (
    AppendReceipt,
    CanonicalRecord,
    CursorState,
    EventDisposition,
    EventId,
    NativeCommand,
    canonical_json_bytes,
    digest_bytes,
    event_record_digest,
    receipt_bytes,
)
from .types import (
    AssignmentRef,
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
    CorruptStore,
    DurabilityFailure,
    DurableRecordRef,
    GrantId,
    GrantPurpose,
    OwnerGenerationId,
    PhysicalTargetKey,
    PreparedBootstrap,
    PreparedClaimChange,
    PreparedOwnerChange,
    PreparedRecoveryDelegation,
    ProcessCoordinates,
    RecoveryDelegationRequest,
    RepositoryKey,
    RoleId,
    RoleOwner,
    SerializationConflict,
    StoreBusy,
    StoredAssignment,
    StoredGrant,
    StoredReconciliation,
    StoreUnavailable,
    ThreadId,
    TransactionClosedError,
    TransactionMismatchError,
    WaveId,
    WorktreeClaim,
)

SCHEMA_VERSION = 1
DEFAULT_BUSY_TIMEOUT_MS = 5_000
STORE_FILENAME = "native-wave-v1.sqlite3"

_SCHEMA = """
PRAGMA user_version = 1;

CREATE TABLE store_meta (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    store_id TEXT NOT NULL UNIQUE,
    store_revision INTEGER NOT NULL CHECK (store_revision >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE waves (
    wave_id TEXT PRIMARY KEY,
    repository_json BLOB NOT NULL,
    policy_revision INTEGER NOT NULL CHECK (policy_revision > 0),
    allowed_roles_json BLOB NOT NULL,
    bootstrap_event_id TEXT NOT NULL,
    created_store_revision INTEGER NOT NULL CHECK (created_store_revision > 0)
);

CREATE TABLE participants (
    wave_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    first_generation_id TEXT NOT NULL,
    first_sequence INTEGER NOT NULL CHECK (first_sequence > 0),
    PRIMARY KEY (wave_id, thread_id, role_id),
    FOREIGN KEY (wave_id) REFERENCES waves(wave_id)
);

CREATE TABLE capabilities (
    snapshot_id TEXT PRIMARY KEY,
    record_json BLOB NOT NULL,
    record_digest TEXT NOT NULL
);

CREATE TABLE owners (
    wave_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    record_json BLOB NOT NULL,
    record_digest TEXT NOT NULL,
    PRIMARY KEY (wave_id, role_id),
    FOREIGN KEY (wave_id) REFERENCES waves(wave_id)
);

CREATE TABLE grants (
    grant_id TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    policy_revision INTEGER NOT NULL CHECK (policy_revision > 0),
    target_owner_generation TEXT,
    target_owner_version INTEGER CHECK (target_owner_version IS NULL OR target_owner_version > 0),
    created_store_revision INTEGER NOT NULL CHECK (created_store_revision >= 0),
    not_before TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    authorized_by TEXT,
    consumed_record_id TEXT,
    consumed_record_digest TEXT,
    FOREIGN KEY (wave_id) REFERENCES waves(wave_id),
    CHECK ((consumed_record_id IS NULL) = (consumed_record_digest IS NULL))
);

CREATE TABLE assignments (
    wave_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    assignment_revision INTEGER NOT NULL CHECK (assignment_revision > 0),
    record_json BLOB NOT NULL,
    record_digest TEXT NOT NULL,
    PRIMARY KEY (wave_id, assignment_id, assignment_revision),
    UNIQUE (assignment_id, assignment_revision),
    FOREIGN KEY (wave_id) REFERENCES waves(wave_id)
);

CREATE TABLE reconciliations (
    record_id TEXT PRIMARY KEY,
    record_digest TEXT NOT NULL,
    wave_id TEXT NOT NULL,
    record_json BLOB NOT NULL,
    record_json_digest TEXT NOT NULL,
    consumed_by_event_id TEXT,
    FOREIGN KEY (wave_id) REFERENCES waves(wave_id)
);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL CHECK (version > 0),
    state TEXT NOT NULL CHECK (state IN ('reserved', 'materialized', 'reconcile_required', 'released')),
    physical_host_id TEXT NOT NULL,
    physical_path TEXT NOT NULL,
    repository_host_id TEXT NOT NULL,
    repository_common_dir TEXT NOT NULL,
    wave_id TEXT NOT NULL,
    record_json BLOB NOT NULL,
    record_digest TEXT NOT NULL,
    FOREIGN KEY (wave_id) REFERENCES waves(wave_id)
);

CREATE UNIQUE INDEX active_physical_target
    ON claims(physical_host_id, physical_path)
    WHERE state != 'released';

CREATE TABLE events (
    wave_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    command_bytes BLOB NOT NULL,
    command_digest TEXT NOT NULL,
    disposition TEXT NOT NULL,
    reason TEXT,
    committed_at TEXT NOT NULL,
    previous_event_digest TEXT,
    event_digest TEXT NOT NULL,
    validation_facts_json BLOB NOT NULL,
    PRIMARY KEY (wave_id, event_id),
    UNIQUE (wave_id, sequence)
);

CREATE TABLE receipts (
    wave_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    command_digest TEXT NOT NULL,
    receipt_bytes BLOB NOT NULL,
    receipt_digest TEXT NOT NULL,
    PRIMARY KEY (wave_id, event_id),
    FOREIGN KEY (wave_id, event_id) REFERENCES events(wave_id, event_id)
);

CREATE TABLE projections (
    wave_id TEXT NOT NULL,
    projection_kind TEXT NOT NULL,
    projection_key TEXT NOT NULL,
    record_json BLOB NOT NULL,
    record_digest TEXT NOT NULL,
    source_sequence INTEGER NOT NULL CHECK (source_sequence > 0),
    PRIMARY KEY (wave_id, projection_kind, projection_key),
    FOREIGN KEY (wave_id, source_sequence) REFERENCES events(wave_id, sequence)
);

CREATE TABLE cursors (
    wave_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    highest_contiguous INTEGER NOT NULL CHECK (highest_contiguous >= 0),
    sparse_json BLOB NOT NULL,
    gaps_json BLOB NOT NULL,
    source_sequence INTEGER NOT NULL CHECK (source_sequence > 0),
    PRIMARY KEY (wave_id, role_id, thread_id, generation_id),
    FOREIGN KEY (wave_id, source_sequence) REFERENCES events(wave_id, sequence)
);
"""


def default_store_path(environ: dict[str, str] | None = None) -> Path:
    """Return the persistent host-wide store path without creating it."""

    values = os.environ if environ is None else environ
    if "XDG_STATE_HOME" in values:
        raw = values["XDG_STATE_HOME"]
        if not raw:
            raise StoreUnavailable("XDG_STATE_HOME is set but empty")
        base = Path(raw)
        if not base.is_absolute():
            raise StoreUnavailable("XDG_STATE_HOME must be absolute")
    else:
        base = Path.home() / ".local" / "state"
    return base / "codex-power-pack" / STORE_FILENAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _id_text(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _record_payload(value: Any) -> dict[str, Any]:
    encoded = canonical_json_bytes(value)
    payload = json.loads(encoded)
    if not isinstance(payload, dict):
        raise TypeError("durable record must encode as an object")
    return payload


def _record_bytes(value: Any) -> bytes:
    return canonical_json_bytes(_record_payload(value))


def _record_ref(payload: dict[str, Any]) -> DurableRecordRef:
    return DurableRecordRef(UUID(payload["record_id"]), payload["digest"])


def _assignment_ref(payload: dict[str, Any]) -> AssignmentRef:
    return AssignmentRef(UUID(payload["assignment_id"]), int(payload["revision"]), payload["digest"])


def _process_coordinates(payload: dict[str, Any]) -> ProcessCoordinates:
    return ProcessCoordinates(
        host_instance_id=payload["host_instance_id"],
        boot_id=UUID(payload["boot_id"]),
        pid=int(payload["pid"]),
        start_ticks=int(payload["start_ticks"]),
    )


def _capability_requirements(payload: dict[str, Any]) -> CapabilityRequirements:
    return CapabilityRequirements(
        schema_version=int(payload["schema_version"]),
        fields=tuple(
            CapabilityFieldRequirement(
                field=CapabilityField(item["field"]),
                accepted_values=tuple(item["accepted_values"]),
            )
            for item in payload["fields"]
        ),
        digest=payload["digest"],
    )


def _decode_capability(encoded: bytes) -> CapabilitySnapshot:
    payload = json.loads(encoded)
    return CapabilitySnapshot(
        schema_version=int(payload["schema_version"]),
        cli_version=payload["cli_version"],
        runtime_version=payload["runtime_version"],
        model=payload["model"],
        reasoning_effort=payload["reasoning_effort"],
        sandbox_mode=payload["sandbox_mode"],
        approval_policy=payload["approval_policy"],
        workspace_roots=tuple(payload["workspace_roots"]),
        additional_writable_roots=tuple(payload["additional_writable_roots"]),
        tool_families=tuple(payload["tool_families"]),
        required_apps=tuple(payload["required_apps"]),
        required_plugins=tuple(payload["required_plugins"]),
        delivery_mechanisms=tuple(payload["delivery_mechanisms"]),
        wake_mechanisms=tuple(payload["wake_mechanisms"]),
        web_mode=payload["web_mode"],
        captured_at=_parse_datetime(payload["captured_at"]),
        evidence=tuple(
            CapabilityEvidence(
                field=CapabilityField(item["field"]),
                evidence_class=item["evidence_class"],
                provenance=item["provenance"],
            )
            for item in payload["evidence"]
        ),
        snapshot_id=CapabilitySnapshotId(payload["snapshot_id"]),
    )


def _decode_owner(encoded: bytes) -> RoleOwner:
    payload = json.loads(encoded)
    return RoleOwner(
        wave_id=WaveId(payload["wave_id"]),
        role_id=RoleId(payload["role_id"]),
        thread_id=ThreadId(UUID(payload["thread_id"])),
        generation_id=OwnerGenerationId(UUID(payload["generation_id"])),
        process=_process_coordinates(payload["process"]),
        capability_snapshot_id=CapabilitySnapshotId(payload["capability_snapshot_id"]),
        policy_revision=int(payload["policy_revision"]),
        record_version=int(payload["record_version"]),
    )


def _decode_assignment(encoded: bytes) -> StoredAssignment:
    payload = json.loads(encoded)
    return StoredAssignment(
        assignment=_assignment_ref(payload["assignment"]),
        wave_id=WaveId(payload["wave_id"]),
        role_id=RoleId(payload["role_id"]),
        owner_generation_id=OwnerGenerationId(UUID(payload["owner_generation_id"])),
        capability_snapshot_id=CapabilitySnapshotId(payload["capability_snapshot_id"]),
        capability_requirements=_capability_requirements(payload["capability_requirements"]),
        required_evidence=tuple(_record_ref(item) for item in payload["required_evidence"]),
        policy_revision=int(payload["policy_revision"]),
        acknowledged=bool(payload["acknowledged"]),
    )


def _decode_grant(row: sqlite3.Row) -> StoredGrant:
    return StoredGrant(
        grant_id=GrantId(UUID(row["grant_id"])),
        wave_id=WaveId(row["wave_id"]),
        role_id=RoleId(row["role_id"]),
        thread_id=ThreadId(UUID(row["thread_id"])),
        purpose=GrantPurpose(row["purpose"]),
        policy_revision=int(row["policy_revision"]),
        created_store_revision=int(row["created_store_revision"]),
        not_before=_parse_datetime(row["not_before"]),
        expires_at=_parse_datetime(row["expires_at"]),
        consumed=row["consumed_record_id"] is not None,
        authorized_by=(
            CoordinatorGenerationId(UUID(row["authorized_by"])) if row["authorized_by"] is not None else None
        ),
        target_owner_generation=(
            OwnerGenerationId(UUID(row["target_owner_generation"]))
            if row["target_owner_generation"] is not None
            else None
        ),
        target_owner_version=(
            int(row["target_owner_version"]) if row["target_owner_version"] is not None else None
        ),
    )


def _decode_reconciliation(encoded: bytes) -> StoredReconciliation:
    payload = json.loads(encoded)
    return StoredReconciliation(
        record=_record_ref(payload["record"]),
        wave_id=WaveId(payload["wave_id"]),
        claim_id=ClaimId(UUID(payload["claim_id"])),
        old_generation=OwnerGenerationId(UUID(payload["old_generation"])),
        new_generation=OwnerGenerationId(UUID(payload["new_generation"])),
        coordinator_generation=CoordinatorGenerationId(UUID(payload["coordinator_generation"])),
        rebound_assignment=_assignment_ref(payload["rebound_assignment"]),
        worktree_exists=bool(payload["worktree_exists"]),
        branch=payload["branch"],
    )


def _decode_claim(encoded: bytes) -> WorktreeClaim:
    payload = json.loads(encoded)
    return WorktreeClaim(
        claim_id=ClaimId(UUID(payload["claim_id"])),
        record_version=int(payload["record_version"]),
        state=ClaimState(payload["state"]),
        target=PhysicalTargetKey(**payload["target"]),
        repository=RepositoryKey(**payload["repository"]),
        wave_id=WaveId(payload["wave_id"]),
        issue_number=int(payload["issue_number"]),
        branch=payload["branch"],
        assignment=_assignment_ref(payload["assignment"]),
        role_id=RoleId(payload["role_id"]),
        thread_id=ThreadId(UUID(payload["thread_id"])),
        owner_generation_id=OwnerGenerationId(UUID(payload["owner_generation_id"])),
        file_lane_digest=payload["file_lane_digest"],
    )


def _secure_parent(path: Path, *, create: bool) -> None:
    parent = path.parent
    if create:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        parent_stat = parent.lstat()
    except OSError as exc:
        raise StoreUnavailable(f"cannot inspect store directory: {parent}") from exc
    if stat.S_ISLNK(parent_stat.st_mode) or parent.resolve(strict=True) != parent.absolute():
        raise StoreUnavailable("native-wave state directory must not traverse symlinks or aliases")
    if parent_stat.st_uid != os.getuid():
        raise StoreUnavailable("native-wave state directory must be owned by the current user")
    if stat.S_IMODE(parent_stat.st_mode) & 0o077:
        raise StoreUnavailable("native-wave state directory must be owner-only")


def _secure_database(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise StoreUnavailable(f"cannot inspect native-wave store: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise StoreUnavailable("native-wave store must be a regular non-symlink file")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise StoreUnavailable("native-wave store must be owner-owned and mode 0600")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class StoreConfig:
    path: Path
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise StoreUnavailable("native-wave store path must be absolute")
        if self.busy_timeout_ms < 0 or self.busy_timeout_ms > 60_000:
            raise ValueError("busy_timeout_ms must be between 0 and 60000")


@dataclass(frozen=True, slots=True)
class ExistingEvent:
    command_bytes: bytes
    receipt_bytes: bytes
    receipt_digest: str


class SQLiteWaveStore:
    """Explicitly opened durable store; importing this module creates nothing."""

    def __init__(self, config: StoreConfig, *, store_id: str, file_identity: tuple[int, int]) -> None:
        self.config = config
        self.store_id = store_id
        self._file_identity = file_identity

    @classmethod
    def create(cls, config: StoreConfig) -> SQLiteWaveStore:
        path = config.path
        _secure_parent(path, create=True)
        connection: sqlite3.Connection | None = None
        reserved_identity: tuple[int, int] | None = None
        try:
            flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError as exc:
                raise StoreUnavailable(f"refusing to replace existing native-wave store: {path}") from exc
            try:
                reserved = os.fstat(descriptor)
                reserved_identity = (reserved.st_dev, reserved.st_ino)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            connection = sqlite3.connect(path.as_uri() + "?mode=rw", isolation_level=None, uri=True)
            connection.execute(f"PRAGMA busy_timeout = {config.busy_timeout_ms}")
            connection.execute("PRAGMA foreign_keys = ON")
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()
            if mode is None or str(mode[0]).lower() != "wal":
                raise StoreUnavailable("SQLite WAL mode is unavailable")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(_SCHEMA)
            connection.execute(
                "INSERT INTO store_meta(singleton, schema_version, store_id, store_revision, created_at) "
                "VALUES (1, ?, ?, 0, ?)",
                (SCHEMA_VERSION, str(uuid4()), _datetime_text(_utc_now())),
            )
            connection.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            if connection is not None:
                connection.close()
            try:
                current = path.lstat()
                current_identity = (current.st_dev, current.st_ino)
            except OSError:
                current_identity = None
            if reserved_identity is not None and current_identity == reserved_identity:
                for candidate in (Path(f"{path}-wal"), Path(f"{path}-shm"), path):
                    try:
                        candidate.unlink(missing_ok=True)
                    except OSError:
                        pass
            raise
        finally:
            if connection is not None:
                connection.close()
        _fsync_directory(path.parent)
        return cls.open(config)

    @classmethod
    def open(cls, config: StoreConfig) -> SQLiteWaveStore:
        _secure_parent(config.path, create=False)
        _secure_database(config.path)
        before = config.path.stat()
        try:
            connection = sqlite3.connect(config.path.as_uri() + "?mode=rw", isolation_level=None, uri=True)
            connection.row_factory = sqlite3.Row
            version_row = connection.execute("PRAGMA user_version").fetchone()
            meta = connection.execute(
                "SELECT schema_version, store_id FROM store_meta WHERE singleton = 1"
            ).fetchone()
            mode_row = connection.execute("PRAGMA journal_mode").fetchone()
            quick_row = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise CorruptStore("native-wave store schema cannot be read") from exc
        finally:
            if "connection" in locals():
                connection.close()
        if version_row is None or int(version_row[0]) != SCHEMA_VERSION:
            raise CorruptStore("native-wave PRAGMA schema version is missing or incompatible")
        if meta is None or int(meta["schema_version"]) != SCHEMA_VERSION:
            raise CorruptStore("native-wave store metadata is missing or incompatible")
        if mode_row is None or str(mode_row[0]).lower() != "wal":
            raise CorruptStore("native-wave store is not in required WAL mode")
        if quick_row is None or str(quick_row[0]) != "ok":
            raise CorruptStore(f"SQLite quick_check failed: {quick_row!r}")
        after = config.path.stat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise StoreUnavailable("native-wave store was replaced while opening")
        return cls(
            config,
            store_id=str(meta["store_id"]),
            file_identity=(after.st_dev, after.st_ino),
        )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        _secure_parent(self.config.path, create=False)
        _secure_database(self.config.path)
        before = self.config.path.stat()
        if (before.st_dev, before.st_ino) != self._file_identity:
            raise StoreUnavailable("native-wave store file identity changed")
        try:
            connection = sqlite3.connect(
                self.config.path.as_uri() + "?mode=rw",
                isolation_level=None,
                timeout=self.config.busy_timeout_ms / 1000,
                uri=True,
            )
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout = {self.config.busy_timeout_ms}")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            version_row = connection.execute("PRAGMA user_version").fetchone()
            meta = connection.execute(
                "SELECT schema_version, store_id FROM store_meta WHERE singleton = 1"
            ).fetchone()
            mode_row = connection.execute("PRAGMA journal_mode").fetchone()
            quick_row = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise StoreUnavailable("cannot open native-wave store") from exc
        after = self.config.path.stat()
        if (
            (after.st_dev, after.st_ino) != self._file_identity
            or version_row is None
            or int(version_row[0]) != SCHEMA_VERSION
            or meta is None
            or int(meta["schema_version"]) != SCHEMA_VERSION
            or str(meta["store_id"]) != self.store_id
            or mode_row is None
            or str(mode_row[0]).lower() != "wal"
            or quick_row is None
            or str(quick_row[0]) != "ok"
        ):
            connection.close()
            raise CorruptStore("native-wave store identity/schema/integrity validation failed")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(
        self,
        *,
        administrative_entry: Literal["bootstrap", "recovery"] | None = None,
    ) -> Iterator[SQLiteTransaction]:
        with self.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                    raise StoreBusy("native-wave store write lock timed out") from exc
                raise StoreUnavailable("cannot begin native-wave transaction") from exc
            tx = SQLiteTransaction(connection, administrative_entry=administrative_entry)
            try:
                yield tx
            except BaseException:
                tx.rollback()
                raise
            finally:
                if tx.is_active:
                    tx.rollback()

    def full_integrity_check(self) -> None:
        with self.connection() as connection:
            try:
                rows = connection.execute("PRAGMA integrity_check").fetchall()
            except sqlite3.DatabaseError as exc:
                raise CorruptStore("SQLite integrity_check could not run") from exc
        results = [str(row[0]) for row in rows]
        if results != ["ok"]:
            raise CorruptStore(f"SQLite integrity_check failed: {results!r}")


class SQLiteTransaction:
    """One serialized write transaction used by all protocol views."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        administrative_entry: Literal["bootstrap", "recovery"] | None,
    ) -> None:
        self._connection = connection
        self._transaction_id = uuid4()
        self._administrative_entry = administrative_entry
        self._active = True
        self._audit_record: tuple[str, str, str] | None = None
        self._savepoint_counter = 0
        row = connection.execute("SELECT store_revision FROM store_meta WHERE singleton = 1").fetchone()
        if row is None:
            raise CorruptStore("store metadata disappeared")
        self._base_store_revision = int(row[0])

    @property
    def transaction_id(self) -> UUID:
        return self._transaction_id

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def base_store_revision(self) -> int:
        return self._base_store_revision

    @property
    def administrative_entry(self) -> Literal["bootstrap", "recovery"]:
        self._ensure_active()
        if self._administrative_entry is None:
            raise TransactionMismatchError("ordinary transaction has no administrative entry")
        return self._administrative_entry

    def _ensure_active(self) -> None:
        if not self._active:
            raise TransactionClosedError("native-wave transaction is closed")

    def _ensure_transaction(self, value: Any) -> None:
        self._ensure_active()
        if getattr(value, "transaction_id", None) != self.transaction_id:
            raise TransactionMismatchError("prepared value belongs to another transaction")

    @contextmanager
    def savepoint(self) -> Iterator[None]:
        """Keep speculative validation writes only when the block succeeds."""

        self._ensure_active()
        self._savepoint_counter += 1
        name = f"native_wave_stage_{self._savepoint_counter}"
        self._connection.execute(f"SAVEPOINT {name}")
        try:
            yield
        except BaseException:
            self._connection.execute(f"ROLLBACK TO {name}")
            self._connection.execute(f"RELEASE {name}")
            raise
        else:
            self._connection.execute(f"RELEASE {name}")

    def bind_audit_record(self, wave_id: WaveId, event_id: EventId, command_digest: str) -> None:
        self._ensure_active()
        binding = (_id_text(wave_id), str(event_id), command_digest)
        if self._audit_record is not None and self._audit_record != binding:
            raise TransactionMismatchError("transaction already has a different audit record")
        self._audit_record = binding

    def commit(self) -> None:
        self._ensure_active()
        try:
            self._connection.execute(
                "UPDATE store_meta SET store_revision = store_revision + 1 WHERE singleton = 1"
            )
            self._connection.commit()
        except sqlite3.DatabaseError as exc:
            self._active = False
            raise DurabilityFailure(
                "SQLite commit failed; outcome is unknown until same-event recovery"
            ) from exc
        self._active = False

    def rollback(self) -> None:
        if not self._active:
            return
        try:
            self._connection.rollback()
        finally:
            self._active = False

    def wave_exists(self, wave_id: WaveId) -> bool:
        self._ensure_active()
        row = self._connection.execute("SELECT 1 FROM waves WHERE wave_id = ?", (_id_text(wave_id),)).fetchone()
        return row is not None

    def policy_revision(self, wave_id: WaveId) -> int | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT policy_revision FROM waves WHERE wave_id = ?", (_id_text(wave_id),)
        ).fetchone()
        return None if row is None else int(row[0])

    def read_policy_revision(self, wave_id: WaveId) -> int:
        revision = self.policy_revision(wave_id)
        return 0 if revision is None else revision

    def stage_policy_revision(self, wave_id: WaveId, expected_revision: int, new_revision: int) -> None:
        self._ensure_active()
        self._require_audit()
        if new_revision <= expected_revision:
            raise SerializationConflict("wave policy revision must advance")
        result = self._connection.execute(
            "UPDATE waves SET policy_revision=? WHERE wave_id=? AND policy_revision=?",
            (new_revision, _id_text(wave_id), expected_revision),
        )
        if result.rowcount != 1:
            raise SerializationConflict("wave policy compare-and-swap lost")

    def read_owner(self, wave_id: WaveId, role_id: RoleId) -> RoleOwner | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json,record_digest FROM owners WHERE wave_id=? AND role_id=?",
            (_id_text(wave_id), _id_text(role_id)),
        ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore("owner record digest mismatch")
        return _decode_owner(encoded)

    def read_capability(self, snapshot_id: CapabilitySnapshotId) -> CapabilitySnapshot | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json,record_digest FROM capabilities WHERE snapshot_id=?",
            (_id_text(snapshot_id),),
        ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore("capability record digest mismatch")
        return _decode_capability(encoded)

    def read_preexisting_grant(self, grant_id: GrantId) -> StoredGrant | None:
        self._ensure_active()
        row = self._connection.execute("SELECT * FROM grants WHERE grant_id=?", (_id_text(grant_id),)).fetchone()
        return None if row is None else _decode_grant(row)

    def read_assignment(self, assignment: AssignmentRef) -> StoredAssignment | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json,record_digest FROM assignments "
            "WHERE assignment_id=? AND assignment_revision=?",
            (str(assignment.assignment_id), assignment.revision),
        ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore("assignment record digest mismatch")
        stored = _decode_assignment(encoded)
        return stored if stored.assignment == assignment else None

    def read_reconciliation(self, record: DurableRecordRef) -> StoredReconciliation | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json,record_digest,record_json_digest FROM reconciliations WHERE record_id=?",
            (str(record.record_id),),
        ).fetchone()
        if row is None or row[1] != record.digest:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[2]:
            raise CorruptStore("reconciliation record digest mismatch")
        return _decode_reconciliation(encoded)

    def read_claim(self, claim_id: ClaimId) -> WorktreeClaim | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json,record_digest FROM claims WHERE claim_id=?", (_id_text(claim_id),)
        ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore("claim record digest mismatch")
        return _decode_claim(encoded)

    def read_active_claim_for_target(self, target: PhysicalTargetKey) -> WorktreeClaim | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json,record_digest FROM claims "
            "WHERE physical_host_id=? AND physical_path=? AND state!='released'",
            (target.host_instance_id, target.canonical_path),
        ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore("active claim record digest mismatch")
        return _decode_claim(encoded)

    def stage_capability(self, snapshot: CapabilitySnapshot) -> None:
        self._ensure_active()
        encoded = _record_bytes(snapshot)
        digest = digest_bytes(encoded)
        row = self._connection.execute(
            "SELECT record_digest FROM capabilities WHERE snapshot_id=?", (_id_text(snapshot.snapshot_id),)
        ).fetchone()
        if row is not None and row[0] != digest:
            raise SerializationConflict("capability snapshot ID has conflicting bytes")
        self._connection.execute(
            "INSERT OR IGNORE INTO capabilities(snapshot_id,record_json,record_digest) VALUES (?,?,?)",
            (_id_text(snapshot.snapshot_id), encoded, digest),
        )

    def _require_audit(self) -> tuple[str, str, str]:
        self._ensure_active()
        if self._audit_record is None:
            raise TransactionMismatchError("a staged authority change requires its audit event")
        return self._audit_record

    def stage_owner_change(self, change: PreparedOwnerChange) -> None:
        self._ensure_transaction(change)
        wave_id, event_id, command_digest = self._require_audit()
        replacement = change.replacement
        current = self.read_owner(replacement.wave_id, replacement.role_id)
        current_version = None if current is None else current.record_version
        if current_version != change.expected_owner_version:
            raise SerializationConflict("owner compare-and-swap lost")
        encoded = _record_bytes(replacement)
        try:
            if current is None:
                self._connection.execute(
                    "INSERT INTO owners(wave_id,role_id,version,record_json,record_digest) VALUES (?,?,?,?,?)",
                    (
                        _id_text(replacement.wave_id),
                        _id_text(replacement.role_id),
                        replacement.record_version,
                        encoded,
                        digest_bytes(encoded),
                    ),
                )
            else:
                result = self._connection.execute(
                    "UPDATE owners SET version=?,record_json=?,record_digest=? "
                    "WHERE wave_id=? AND role_id=? AND version=?",
                    (
                        replacement.record_version,
                        encoded,
                        digest_bytes(encoded),
                        _id_text(replacement.wave_id),
                        _id_text(replacement.role_id),
                        change.expected_owner_version,
                    ),
                )
                if result.rowcount != 1:
                    raise SerializationConflict("owner compare-and-swap lost")
        except sqlite3.IntegrityError as exc:
            raise SerializationConflict("owner uniqueness constraint failed") from exc
        if change.consumed_grant_id is not None:
            result = self._connection.execute(
                "UPDATE grants SET consumed_record_id=?,consumed_record_digest=? "
                "WHERE grant_id=? AND consumed_record_id IS NULL AND created_store_revision < ?",
                (event_id, command_digest, _id_text(change.consumed_grant_id), self.base_store_revision),
            )
            if result.rowcount != 1:
                raise SerializationConflict("grant consumption compare-and-swap lost")
        event_row = self._connection.execute(
            "SELECT sequence FROM events WHERE wave_id=? AND event_id=?", (wave_id, event_id)
        ).fetchone()
        if event_row is None:
            raise TransactionMismatchError("owner audit event is missing")
        self._connection.execute(
            "INSERT OR IGNORE INTO participants(wave_id,thread_id,role_id,first_generation_id,first_sequence) "
            "VALUES (?,?,?,?,?)",
            (
                _id_text(replacement.wave_id),
                _id_text(replacement.thread_id),
                _id_text(replacement.role_id),
                _id_text(replacement.generation_id),
                int(event_row[0]),
            ),
        )

    def stage_claim_change(self, change: PreparedClaimChange) -> None:
        self._ensure_transaction(change)
        self._require_audit()
        replacement = change.replacement
        current = self.read_claim(replacement.claim_id)
        current_version = None if current is None else current.record_version
        if current_version != change.expected_claim_version:
            raise SerializationConflict("claim compare-and-swap lost")
        encoded = _record_bytes(replacement)
        values = (
            replacement.record_version,
            replacement.state.value,
            replacement.target.host_instance_id,
            replacement.target.canonical_path,
            replacement.repository.host_instance_id,
            replacement.repository.canonical_common_dir,
            _id_text(replacement.wave_id),
            encoded,
            digest_bytes(encoded),
        )
        try:
            if current is None:
                self._connection.execute(
                    "INSERT INTO claims(claim_id,version,state,physical_host_id,physical_path,repository_host_id,"
                    "repository_common_dir,wave_id,record_json,record_digest) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (_id_text(replacement.claim_id), *values),
                )
            else:
                result = self._connection.execute(
                    "UPDATE claims SET version=?,state=?,physical_host_id=?,physical_path=?,repository_host_id=?,"
                    "repository_common_dir=?,wave_id=?,record_json=?,record_digest=? WHERE claim_id=? AND version=?",
                    (*values, _id_text(replacement.claim_id), change.expected_claim_version),
                )
                if result.rowcount != 1:
                    raise SerializationConflict("claim compare-and-swap lost")
        except sqlite3.IntegrityError as exc:
            raise SerializationConflict("active physical target is already claimed") from exc
        if change.reconciliation is not None:
            _, event_id, _ = self._require_audit()
            result = self._connection.execute(
                "UPDATE reconciliations SET consumed_by_event_id=? "
                "WHERE record_id=? AND record_digest=? AND consumed_by_event_id IS NULL",
                (event_id, str(change.reconciliation.record_id), change.reconciliation.digest),
            )
            if result.rowcount != 1:
                raise SerializationConflict("reconciliation consumption compare-and-swap lost")

    def stage_assignment(self, assignment: StoredAssignment) -> None:
        self._ensure_active()
        self._require_audit()
        encoded = _record_bytes(assignment)
        try:
            self._connection.execute(
                "INSERT INTO assignments(wave_id,assignment_id,assignment_revision,record_json,record_digest) "
                "VALUES (?,?,?,?,?)",
                (
                    _id_text(assignment.wave_id),
                    str(assignment.assignment.assignment_id),
                    assignment.assignment.revision,
                    encoded,
                    digest_bytes(encoded),
                ),
            )
        except sqlite3.IntegrityError as exc:
            row = self._connection.execute(
                "SELECT record_digest FROM assignments WHERE wave_id=? AND assignment_id=? AND assignment_revision=?",
                (
                    _id_text(assignment.wave_id),
                    str(assignment.assignment.assignment_id),
                    assignment.assignment.revision,
                ),
            ).fetchone()
            if row is None or row[0] != digest_bytes(encoded):
                raise SerializationConflict("assignment revision has conflicting durable bytes") from exc

    def set_assignment_acknowledged(self, assignment: AssignmentRef) -> None:
        self._ensure_active()
        self._require_audit()
        current = self.read_assignment(assignment)
        if current is None:
            raise SerializationConflict("assignment acknowledgement target is missing")
        if current.acknowledged:
            return
        prior = _record_bytes(current)
        replacement = _record_bytes(replace(current, acknowledged=True))
        result = self._connection.execute(
            "UPDATE assignments SET record_json=?,record_digest=? "
            "WHERE assignment_id=? AND assignment_revision=? AND record_digest=?",
            (
                replacement,
                digest_bytes(replacement),
                str(assignment.assignment_id),
                assignment.revision,
                digest_bytes(prior),
            ),
        )
        if result.rowcount != 1:
            raise SerializationConflict("assignment acknowledgement compare-and-swap lost")

    def stage_reconciliation(self, reconciliation: StoredReconciliation) -> None:
        self._ensure_active()
        self._require_audit()
        encoded = _record_bytes(reconciliation)
        try:
            self._connection.execute(
                "INSERT INTO reconciliations("
                "record_id,record_digest,wave_id,record_json,record_json_digest"
                ") VALUES (?,?,?,?,?)",
                (
                    str(reconciliation.record.record_id),
                    reconciliation.record.digest,
                    _id_text(reconciliation.wave_id),
                    encoded,
                    digest_bytes(encoded),
                ),
            )
        except sqlite3.IntegrityError as exc:
            existing = self._connection.execute(
                "SELECT record_digest, record_json FROM reconciliations WHERE record_id = ?",
                (str(reconciliation.record.record_id),),
            ).fetchone()
            if (
                existing is None
                or existing["record_digest"] != reconciliation.record.digest
                or bytes(existing["record_json"]) != encoded
            ):
                raise SerializationConflict("reconciliation record ID has conflicting durable bytes") from exc

    def stage_bootstrap(self, change: PreparedBootstrap) -> None:
        self._ensure_transaction(change)
        if self.administrative_entry != "bootstrap":
            raise TransactionMismatchError("wave bootstrap requires bootstrap administrative entry")
        _, event_id, _ = self._require_audit()
        request: BootstrapRequest = change.request
        if self.wave_exists(request.wave_id):
            raise SerializationConflict("wave is already bootstrapped")
        roles = tuple(sorted({_id_text(grant.role_id) for grant in request.grants}))
        self._connection.execute(
            "INSERT INTO waves(wave_id,repository_json,policy_revision,allowed_roles_json,bootstrap_event_id,"
            "created_store_revision) VALUES (?,?,?,?,?,?)",
            (
                _id_text(request.wave_id),
                _record_bytes(request.repository),
                request.policy_revision,
                canonical_json_bytes(roles),
                event_id,
                self.base_store_revision + 1,
            ),
        )
        for grant in request.grants:
            self._connection.execute(
                "INSERT INTO grants(grant_id,wave_id,role_id,thread_id,purpose,policy_revision,"
                "target_owner_generation,target_owner_version,created_store_revision,not_before,expires_at,"
                "authorized_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    _id_text(grant.grant_id),
                    _id_text(request.wave_id),
                    _id_text(grant.role_id),
                    _id_text(grant.thread_id),
                    grant.purpose.value,
                    request.policy_revision,
                    None,
                    None,
                    self.base_store_revision,
                    _datetime_text(request.created_at),
                    _datetime_text(grant.expires_at),
                    None,
                ),
            )

    def stage_recovery_delegation(self, change: PreparedRecoveryDelegation) -> None:
        self._ensure_transaction(change)
        if self.administrative_entry != "recovery":
            raise TransactionMismatchError("recovery delegation requires recovery administrative entry")
        self._require_audit()
        request: RecoveryDelegationRequest = change.request
        if not self.wave_exists(request.wave_id):
            raise SerializationConflict("recovery delegation wave is missing")
        coordinator = self.read_owner(request.wave_id, RoleId("coordinator"))
        if coordinator is None:
            raise SerializationConflict("recovery delegation coordinator is missing")
        self._connection.execute(
            "INSERT INTO grants(grant_id,wave_id,role_id,thread_id,purpose,policy_revision,"
            "target_owner_generation,target_owner_version,created_store_revision,not_before,expires_at,"
            "authorized_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                _id_text(request.grant_id),
                _id_text(request.wave_id),
                "coordinator",
                _id_text(request.successor_thread_id),
                GrantPurpose.COORDINATOR_RECOVERY.value,
                self.read_policy_revision(request.wave_id),
                _id_text(coordinator.generation_id),
                coordinator.record_version,
                self.base_store_revision,
                _datetime_text(request.created_at),
                _datetime_text(request.expires_at),
                _id_text(request.expected_coordinator_generation),
            ),
        )

    def participant_exists(self, wave_id: WaveId, thread_id: ThreadId) -> bool:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT 1 FROM participants WHERE wave_id = ? AND thread_id = ? LIMIT 1",
            (_id_text(wave_id), _id_text(thread_id)),
        ).fetchone()
        return row is not None

    def lookup_event(self, wave_id: WaveId, event_id: EventId) -> ExistingEvent | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT e.command_bytes, r.receipt_bytes, r.receipt_digest "
            "FROM events e JOIN receipts r USING (wave_id, event_id) "
            "WHERE e.wave_id = ? AND e.event_id = ?",
            (_id_text(wave_id), str(event_id)),
        ).fetchone()
        if row is None:
            return None
        receipt = bytes(row[1])
        if digest_bytes(receipt) != row[2]:
            raise CorruptStore("stored receipt digest mismatch")
        return ExistingEvent(bytes(row[0]), receipt, str(row[2]))

    def append_event(
        self,
        command: NativeCommand,
        *,
        disposition: EventDisposition,
        reason: str | None,
        validation_facts: CanonicalRecord = CanonicalRecord(),
        committed_at: datetime | None = None,
    ) -> AppendReceipt:
        self._ensure_active()
        command_bytes = command.canonical_bytes()
        command_digest = digest_bytes(command_bytes)
        existing = self.lookup_event(command.wave_id, command.event_id)
        if existing is not None:
            raise TransactionMismatchError("append_event called for an existing event ID")
        sequence_row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE wave_id = ?",
            (_id_text(command.wave_id),),
        ).fetchone()
        sequence = int(sequence_row[0])
        previous_row = self._connection.execute(
            "SELECT event_digest FROM events WHERE wave_id = ? ORDER BY sequence DESC LIMIT 1",
            (_id_text(command.wave_id),),
        ).fetchone()
        previous_digest = None if previous_row is None else str(previous_row[0])
        timestamp = _utc_now() if committed_at is None else committed_at
        event_digest = event_record_digest(
            command_bytes=command_bytes,
            sequence=sequence,
            disposition=disposition,
            reason=reason,
            committed_at=timestamp,
            previous_event_digest=previous_digest,
            validation_facts=validation_facts,
        )
        receipt = AppendReceipt(
            wave_id=command.wave_id,
            event_id=command.event_id,
            command_digest=command_digest,
            disposition=disposition,
            reason=reason,
            sequence=sequence,
            event_digest=event_digest,
            committed_at=timestamp,
        )
        encoded_receipt = receipt_bytes(receipt)
        self._connection.execute(
            "INSERT INTO events(wave_id,event_id,sequence,command_bytes,command_digest,disposition,reason,"
            "committed_at,previous_event_digest,event_digest,validation_facts_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                _id_text(command.wave_id),
                str(command.event_id),
                sequence,
                command_bytes,
                command_digest,
                disposition.value,
                reason,
                _datetime_text(timestamp),
                previous_digest,
                event_digest,
                canonical_json_bytes(validation_facts),
            ),
        )
        self._connection.execute(
            "INSERT INTO receipts(wave_id,event_id,command_digest,receipt_bytes,receipt_digest) VALUES (?,?,?,?,?)",
            (
                _id_text(command.wave_id),
                str(command.event_id),
                command_digest,
                encoded_receipt,
                digest_bytes(encoded_receipt),
            ),
        )
        self.bind_audit_record(command.wave_id, command.event_id, command_digest)
        return receipt

    def read_event_rows(self, wave_id: WaveId, *, after_sequence: int = 0, limit: int = 1000) -> list[sqlite3.Row]:
        self._ensure_active()
        if after_sequence < 0 or limit <= 0 or limit > 10_000:
            raise ValueError("invalid event page bounds")
        return list(
            self._connection.execute(
                "SELECT * FROM events WHERE wave_id = ? AND sequence > ? ORDER BY sequence LIMIT ?",
                (_id_text(wave_id), after_sequence, limit),
            ).fetchall()
        )

    def get_projection(self, wave_id: WaveId, kind: str, key: str) -> dict[str, Any] | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT record_json, record_digest FROM projections "
            "WHERE wave_id = ? AND projection_kind = ? AND projection_key = ?",
            (_id_text(wave_id), kind, key),
        ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore("projection digest mismatch")
        value = json.loads(encoded)
        if not isinstance(value, dict):
            raise CorruptStore("projection is not an object")
        return value

    def put_projection(self, wave_id: WaveId, kind: str, key: str, value: dict[str, Any], sequence: int) -> None:
        self._ensure_active()
        encoded = canonical_json_bytes(value)
        self._connection.execute(
            "INSERT INTO projections(wave_id,projection_kind,projection_key,record_json,record_digest,source_sequence) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(wave_id,projection_kind,projection_key) DO UPDATE SET "
            "record_json=excluded.record_json,record_digest=excluded.record_digest,source_sequence=excluded.source_sequence",
            (_id_text(wave_id), kind, key, encoded, digest_bytes(encoded), sequence),
        )

    def read_cursor(
        self,
        wave_id: WaveId,
        role_id: RoleId,
        thread_id: ThreadId,
        generation_id: Any,
    ) -> CursorState | None:
        self._ensure_active()
        row = self._connection.execute(
            "SELECT highest_contiguous,sparse_json,gaps_json FROM cursors "
            "WHERE wave_id=? AND role_id=? AND thread_id=? AND generation_id=?",
            (_id_text(wave_id), _id_text(role_id), _id_text(thread_id), _id_text(generation_id)),
        ).fetchone()
        if row is None:
            return None
        return CursorState(
            wave_id=wave_id,
            role_id=role_id,
            thread_id=thread_id,
            generation_id=generation_id,
            highest_contiguous=int(row[0]),
            sparse_sequences=tuple(json.loads(bytes(row[1]))),
            gaps=tuple(json.loads(bytes(row[2]))),
        )

    def put_cursor(self, cursor: CursorState, source_sequence: int) -> None:
        self._ensure_active()
        sparse = canonical_json_bytes(cursor.sparse_sequences)
        gaps = canonical_json_bytes(cursor.gaps)
        self._connection.execute(
            "INSERT INTO cursors("
            "wave_id,role_id,thread_id,generation_id,highest_contiguous,sparse_json,gaps_json,source_sequence"
            ") "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(wave_id,role_id,thread_id,generation_id) DO UPDATE SET "
            "highest_contiguous=excluded.highest_contiguous,sparse_json=excluded.sparse_json,"
            "gaps_json=excluded.gaps_json,source_sequence=excluded.source_sequence",
            (
                _id_text(cursor.wave_id),
                _id_text(cursor.role_id),
                _id_text(cursor.thread_id),
                _id_text(cursor.generation_id),
                cursor.highest_contiguous,
                sparse,
                gaps,
                source_sequence,
            ),
        )


__all__ = [
    "DEFAULT_BUSY_TIMEOUT_MS",
    "ExistingEvent",
    "SCHEMA_VERSION",
    "STORE_FILENAME",
    "SQLiteTransaction",
    "SQLiteWaveStore",
    "StoreConfig",
    "default_store_path",
]
