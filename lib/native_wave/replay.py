"""Fail-closed journal verification and projection replay for #205."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .event_types import (
    CanonicalRecord,
    CursorState,
    DurableEvent,
    EventDisposition,
    EventValidationError,
    canonical_json_bytes,
    command_from_bytes,
    digest_bytes,
    event_record_digest,
    receipt_from_bytes,
)
from .storage import SQLiteTransaction, SQLiteWaveStore, _parse_datetime
from .types import CorruptStore, WaveId


@dataclass(frozen=True, slots=True)
class ProjectionRow:
    kind: str
    key: str
    value: dict[str, Any]
    source_sequence: int


@dataclass(frozen=True, slots=True)
class CursorRow:
    cursor: CursorState
    source_sequence: int


@dataclass(frozen=True, slots=True)
class ProjectionSnapshot:
    projections: tuple[ProjectionRow, ...]
    cursors: tuple[CursorRow, ...]


@dataclass(frozen=True, slots=True)
class ReplayReport:
    wave_id: WaveId
    event_count: int
    last_sequence: int
    last_event_digest: str | None
    projection_count: int
    cursor_count: int


def _corrupt(message: str, *, last_verified: int, cause: Exception | None = None) -> CorruptStore:
    error = CorruptStore(f"{message}; last verified sequence={last_verified}")
    if cause is not None:
        error.__cause__ = cause
    return error


def verified_events(tx: SQLiteTransaction, wave_id: WaveId) -> tuple[DurableEvent, ...]:
    """Verify and materialize the complete committed event chain for a wave."""

    events: list[DurableEvent] = []
    previous_digest: str | None = None
    last_verified = 0
    page_size = 10_000
    while True:
        rows = tx.read_event_rows(wave_id, after_sequence=last_verified, limit=page_size)
        if not rows:
            break
        for row in rows:
            expected_sequence = last_verified + 1
            try:
                sequence = int(row["sequence"])
                if sequence != expected_sequence:
                    raise EventValidationError("event sequence is not contiguous")
                command_bytes = bytes(row["command_bytes"])
                if digest_bytes(command_bytes) != row["command_digest"]:
                    raise EventValidationError("command digest mismatch")
                command = command_from_bytes(command_bytes)
                if str(command.wave_id) != str(wave_id) or str(command.event_id) != row["event_id"]:
                    raise EventValidationError("event key differs from canonical command")
                if row["previous_event_digest"] != previous_digest:
                    raise EventValidationError("event hash-chain predecessor mismatch")
                raw_facts = bytes(row["validation_facts_json"])
                parsed_facts = json.loads(raw_facts)
                if not isinstance(parsed_facts, dict):
                    raise EventValidationError("validation facts must be an object")
                facts = CanonicalRecord.from_mapping(parsed_facts)
                if canonical_json_bytes(facts) != raw_facts:
                    raise EventValidationError("validation facts are not canonical")
                disposition = EventDisposition(row["disposition"])
                committed_at = _parse_datetime(row["committed_at"])
                computed_event_digest = event_record_digest(
                    command_bytes=command_bytes,
                    sequence=sequence,
                    disposition=disposition,
                    reason=row["reason"],
                    committed_at=committed_at,
                    previous_event_digest=previous_digest,
                    validation_facts=facts,
                )
                if computed_event_digest != row["event_digest"]:
                    raise EventValidationError("event record digest mismatch")
                existing = tx.lookup_event(wave_id, command.event_id)
                if existing is None:
                    raise EventValidationError("event receipt is missing")
                receipt = receipt_from_bytes(existing.receipt_bytes)
                if (
                    str(receipt.wave_id) != str(wave_id)
                    or str(receipt.event_id) != str(command.event_id)
                    or receipt.command_digest != row["command_digest"]
                    or receipt.disposition != disposition
                    or receipt.reason != row["reason"]
                    or receipt.sequence != sequence
                    or receipt.event_digest != computed_event_digest
                    or receipt.committed_at != committed_at
                ):
                    raise EventValidationError("receipt does not match its event")
                event = DurableEvent(
                    command=command,
                    sequence=sequence,
                    disposition=disposition,
                    reason=row["reason"],
                    committed_at=committed_at,
                    previous_event_digest=previous_digest,
                    event_digest=computed_event_digest,
                    validation_facts=facts,
                )
            except (EventValidationError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                raise _corrupt("native-wave event chain verification failed", last_verified=last_verified, cause=exc)
            events.append(event)
            previous_digest = event.event_digest
            last_verified = event.sequence
        if len(rows) < page_size:
            break
    return tuple(events)


def _verify_digest_table(tx: SQLiteTransaction, table: str, blob_column: str, digest_column: str) -> None:
    allowed = {
        ("capabilities", "record_json", "record_digest"),
        ("owners", "record_json", "record_digest"),
        ("assignments", "record_json", "record_digest"),
        ("claims", "record_json", "record_digest"),
        ("projections", "record_json", "record_digest"),
        ("reconciliations", "record_json", "record_json_digest"),
    }
    if (table, blob_column, digest_column) not in allowed:
        raise ValueError("unapproved integrity table")
    for row in tx._connection.execute(f"SELECT {blob_column}, {digest_column} FROM {table}").fetchall():
        encoded = bytes(row[0])
        if digest_bytes(encoded) != row[1]:
            raise CorruptStore(f"{table} record digest mismatch")
        try:
            parsed = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorruptStore(f"{table} record is not valid JSON") from exc
        if canonical_json_bytes(parsed) != encoded:
            raise CorruptStore(f"{table} record is not canonical JSON")


def verify_materialized_state(tx: SQLiteTransaction, wave_id: WaveId) -> tuple[int, int]:
    """Verify digests and source references for projections and cursors."""

    for table, blob, digest in (
        ("capabilities", "record_json", "record_digest"),
        ("owners", "record_json", "record_digest"),
        ("assignments", "record_json", "record_digest"),
        ("claims", "record_json", "record_digest"),
        ("projections", "record_json", "record_digest"),
        ("reconciliations", "record_json", "record_json_digest"),
    ):
        _verify_digest_table(tx, table, blob, digest)

    projection_count = 0
    for row in tx._connection.execute(
        "SELECT source_sequence FROM projections WHERE wave_id = ?", (str(wave_id),)
    ).fetchall():
        if tx._connection.execute(
            "SELECT 1 FROM events WHERE wave_id = ? AND sequence = ?", (str(wave_id), int(row[0]))
        ).fetchone() is None:
            raise CorruptStore("projection references a missing event")
        projection_count += 1

    cursor_count = 0
    for row in tx._connection.execute(
        "SELECT highest_contiguous,sparse_json,gaps_json,source_sequence FROM cursors WHERE wave_id = ?",
        (str(wave_id),),
    ).fetchall():
        for index in (1, 2):
            raw = bytes(row[index])
            value = json.loads(raw)
            if not isinstance(value, list) or canonical_json_bytes(value) != raw:
                raise CorruptStore("cursor sparse/gap state is not canonical")
        if tx._connection.execute(
            "SELECT 1 FROM events WHERE wave_id = ? AND sequence = ?", (str(wave_id), int(row[3]))
        ).fetchone() is None:
            raise CorruptStore("cursor references a missing event")
        cursor_count += 1
    return projection_count, cursor_count


def _verify_rebuilt_snapshot(
    tx: SQLiteTransaction,
    wave_id: WaveId,
    snapshot: ProjectionSnapshot,
) -> None:
    expected_projections = {
        (row.kind, row.key): (canonical_json_bytes(row.value), row.source_sequence)
        for row in snapshot.projections
    }
    actual_projections = {
        (str(row[0]), str(row[1])): (bytes(row[2]), int(row[3]))
        for row in tx._connection.execute(
            "SELECT projection_kind,projection_key,record_json,source_sequence "
            "FROM projections WHERE wave_id=?",
            (str(wave_id),),
        ).fetchall()
    }
    if actual_projections != expected_projections:
        raise CorruptStore("materialized projections differ from verified journal replay")

    expected_cursors = {
        (
            str(row.cursor.role_id),
            str(row.cursor.thread_id),
            str(row.cursor.generation_id),
        ): (
            row.cursor.highest_contiguous,
            canonical_json_bytes(row.cursor.sparse_sequences),
            canonical_json_bytes(row.cursor.gaps),
            row.source_sequence,
        )
        for row in snapshot.cursors
    }
    actual_cursors = {
        (str(row[0]), str(row[1]), str(row[2])): (
            int(row[3]),
            bytes(row[4]),
            bytes(row[5]),
            int(row[6]),
        )
        for row in tx._connection.execute(
            "SELECT role_id,thread_id,generation_id,highest_contiguous,sparse_json,gaps_json,source_sequence "
            "FROM cursors WHERE wave_id=?",
            (str(wave_id),),
        ).fetchall()
    }
    if actual_cursors != expected_cursors:
        raise CorruptStore("materialized cursors differ from verified journal replay")


def verify_wave(store: SQLiteWaveStore, wave_id: WaveId) -> ReplayReport:
    store.full_integrity_check()
    with store.transaction() as tx:
        events = verified_events(tx, wave_id)
        projection_count, cursor_count = verify_materialized_state(tx, wave_id)
        from .events import build_projection_snapshot

        snapshot = build_projection_snapshot(events)
        _verify_rebuilt_snapshot(tx, wave_id, snapshot)
    return ReplayReport(
        wave_id=wave_id,
        event_count=len(events),
        last_sequence=events[-1].sequence if events else 0,
        last_event_digest=events[-1].event_digest if events else None,
        projection_count=projection_count,
        cursor_count=cursor_count,
    )


def rebuild_projections(store: SQLiteWaveStore, wave_id: WaveId) -> ReplayReport:
    """Verify the whole journal, then atomically replace derived state."""

    store.full_integrity_check()
    with store.transaction() as tx:
        events = verified_events(tx, wave_id)
        from .events import build_projection_snapshot

        snapshot: ProjectionSnapshot = build_projection_snapshot(events)
        tx._connection.execute("DELETE FROM projections WHERE wave_id = ?", (str(wave_id),))
        tx._connection.execute("DELETE FROM cursors WHERE wave_id = ?", (str(wave_id),))
        for projection in snapshot.projections:
            tx.put_projection(
                wave_id,
                projection.kind,
                projection.key,
                projection.value,
                projection.source_sequence,
            )
        for cursor in snapshot.cursors:
            tx.put_cursor(cursor.cursor, cursor.source_sequence)
        tx.commit()
    return ReplayReport(
        wave_id=wave_id,
        event_count=len(events),
        last_sequence=events[-1].sequence if events else 0,
        last_event_digest=events[-1].event_digest if events else None,
        projection_count=len(snapshot.projections),
        cursor_count=len(snapshot.cursors),
    )


__all__ = [
    "CursorRow",
    "ProjectionRow",
    "ProjectionSnapshot",
    "ReplayReport",
    "rebuild_projections",
    "verified_events",
    "verify_materialized_state",
    "verify_wave",
]
