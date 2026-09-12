"""Fail-closed journal verification and projection replay for #205."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .cursors import MAX_CURSOR_SPAN, advance_cursor
from .event_types import (
    CanonicalRecord,
    CursorState,
    DurableEvent,
    EventDisposition,
    EventId,
    EventKind,
    EventPage,
    EventValidationError,
    canonical_json_bytes,
    command_from_bytes,
    digest_bytes,
    event_record_digest,
    receipt_from_bytes,
)
from .storage import SQLiteTransaction, SQLiteWaveStore, _parse_datetime
from .types import CorruptStore, StoredAssignment, WaveId


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
class _AuthoritySnapshot:
    wave: dict[str, Any]
    bootstrap_event_id: str
    created_store_revision: int
    allowed_roles: tuple[str, ...]
    capabilities: dict[str, dict[str, Any]]
    owners: dict[str, dict[str, Any]]
    grants: dict[str, dict[str, Any]]
    grant_consumption: dict[str, tuple[str, str]]
    assignments: dict[tuple[str, int], dict[str, Any]]
    reconciliations: dict[str, dict[str, Any]]
    reconciliation_consumption: dict[str, str]
    claims: dict[str, dict[str, Any]]
    participants: dict[tuple[str, str], tuple[str, int]]


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


def _plain(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def _authority_snapshot(
    wave_id: WaveId,
    events: tuple[DurableEvent, ...],
    projections: ProjectionSnapshot,
) -> _AuthoritySnapshot:
    projection_values = {(row.kind, row.key): row.value for row in projections.projections}
    wave = projection_values.get(("wave", str(wave_id)))
    if wave is None:
        raise CorruptStore("verified journal has no applied wave bootstrap")

    bootstrap_event: DurableEvent | None = None
    assignments: dict[tuple[str, int], dict[str, Any]] = {}
    participants: dict[tuple[str, str], tuple[str, int]] = {}
    grant_consumption: dict[str, tuple[str, str]] = {}
    reconciliation_consumption: dict[str, str] = {}
    for event in events:
        if event.disposition == EventDisposition.REJECTED:
            continue
        command = event.command
        facts = event.validation_facts.as_mapping()
        if command.kind.value == "wave.bootstrapped":
            if bootstrap_event is not None:
                raise CorruptStore("verified journal applies wave bootstrap more than once")
            bootstrap_event = event
        if command.kind.value in {
            "owner.registered",
            "owner.replaced",
            "owner.capability_updated",
            "owner.rebriefed",
        }:
            owner = _plain(facts["owner"])
            participant_key = (str(owner["thread_id"]), str(owner["role_id"]))
            participants.setdefault(
                participant_key,
                (str(owner["generation_id"]), event.sequence),
            )
            consumed_grant_id = facts.get("consumed_grant_id")
            if consumed_grant_id is not None:
                grant_consumption[str(consumed_grant_id)] = (
                    str(command.event_id),
                    command.payload_digest(),
                )
        if command.kind.value in {"assignment.queued", "assignment.rebound"}:
            binding = command.assignment
            if binding is None:  # pragma: no cover - command validation already enforces this
                raise CorruptStore("assignment event lacks its binding")
            stored = StoredAssignment(
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
            assignments[(str(binding.ref.assignment_id), binding.ref.revision)] = _plain(stored)
        elif command.kind.value == "assignment.accepted":
            binding = command.assignment
            assert binding is not None
            key = (str(binding.ref.assignment_id), binding.ref.revision)
            current = assignments.get(key)
            if current is None:
                raise CorruptStore("accepted assignment is absent from verified journal")
            current = dict(current)
            current["acknowledged"] = True
            assignments[key] = current
        elif command.kind.value == "claim.rebound":
            reconciliation = facts.get("reconciliation")
            if reconciliation is not None:
                record_id = str(_plain(reconciliation)["record_id"])
                reconciliation_consumption[record_id] = str(command.event_id)

    if bootstrap_event is None:
        raise CorruptStore("verified journal has no applied bootstrap event")
    bootstrap_facts = bootstrap_event.validation_facts.as_mapping()
    request = _plain(bootstrap_facts["request"])
    created_store_revision = bootstrap_facts.get("created_store_revision")
    if isinstance(created_store_revision, bool) or not isinstance(created_store_revision, int):
        raise CorruptStore("bootstrap event lacks a valid created store revision")
    allowed_roles = tuple(sorted({str(grant["role_id"]) for grant in request["grants"]}))

    return _AuthoritySnapshot(
        wave=dict(wave),
        bootstrap_event_id=str(bootstrap_event.command.event_id),
        created_store_revision=created_store_revision,
        allowed_roles=allowed_roles,
        capabilities={
            key: value
            for (kind, key), value in projection_values.items()
            if kind == "capability"
        },
        owners={key: value for (kind, key), value in projection_values.items() if kind == "owner"},
        grants={key: value for (kind, key), value in projection_values.items() if kind == "grant"},
        grant_consumption=grant_consumption,
        assignments=assignments,
        reconciliations={
            key: value
            for (kind, key), value in projection_values.items()
            if kind == "reconciliation"
        },
        reconciliation_consumption=reconciliation_consumption,
        claims={key: value for (kind, key), value in projection_values.items() if kind == "claim"},
        participants=participants,
    )


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


def replay_scan_cursor(event: DurableEvent, current: CursorState) -> CursorState:
    """Validate a committed scan against its preceding reader state, including old journals."""

    target = event.command.payload.get("cursor_highest_contiguous")
    if (
        isinstance(target, bool)
        or not isinstance(target, int)
        or not current.highest_contiguous < target < event.sequence
        or target - current.highest_contiguous > MAX_CURSOR_SPAN
    ):
        raise CorruptStore("committed cursor scan has invalid bounds")
    facts = event.validation_facts.as_mapping()
    # Older journals lack the explicit start; their preceding cursor is authoritative.
    start = facts.get("scan_after_sequence", current.highest_contiguous)
    if isinstance(start, bool) or not isinstance(start, int) or start != current.highest_contiguous:
        raise CorruptStore("committed cursor scan start differs from preceding cursor")
    cursor = advance_cursor(
        current,
        observed_sequences=range(start + 1, target + 1),
        scanned_through=target,
    )
    if (
        event.disposition != EventDisposition.APPLIED
        or event.command.payload.get("cursor_sparse") != cursor.sparse_sequences
        or canonical_json_bytes(facts.get("cursor")) != canonical_json_bytes(cursor)
    ):
        raise CorruptStore("committed cursor scan differs from replayed cursor")
    return cursor


def recover_scan_page(tx: SQLiteTransaction, wave_id: WaveId, event_id: EventId) -> EventPage:
    """Recover an immutable scan response; caller must authorize historical access first.

    Recovery verifies the journal and reconstructs the preceding cursor rather than
    trusting the live cursor. This also supports scans written before explicit start
    metadata existed. It performs no writes and returns at most MAX_CURSOR_SPAN rows.
    """

    from .events import build_projection_snapshot
    from .types import OwnerGenerationId

    events = verified_events(tx, wave_id)
    for index, event in enumerate(events):
        if event.command.event_id != event_id:
            continue
        if event.command.kind != EventKind.CURSOR_ADVANCED:
            raise CorruptStore("scan recovery references a non-scan event")
        actor = event.command.actor
        current = CursorState(wave_id, actor.role_id, actor.thread_id, OwnerGenerationId(actor.generation_id.value))
        try:
            snapshot = build_projection_snapshot(events[:index])
            current = next(
                (
                    row.cursor
                    for row in snapshot.cursors
                    if (row.cursor.wave_id, row.cursor.role_id, row.cursor.thread_id, row.cursor.generation_id)
                    == (current.wave_id, current.role_id, current.thread_id, current.generation_id)
                ),
                current,
            )
            cursor = replay_scan_cursor(event, current)
        except (ValueError, TypeError, KeyError, CorruptStore) as exc:
            raise CorruptStore("scan recovery cannot reconstruct a verified cursor") from exc
        target = event.command.payload.get("cursor_highest_contiguous")
        assert isinstance(target, int)
        return EventPage(events[current.highest_contiguous : target], target, cursor)
    raise CorruptStore("committed scan is missing from the journal")


def _verify_digest_table(tx: SQLiteTransaction, table: str, blob_column: str, digest_column: str) -> None:
    queries = {
        ("capabilities", "record_json", "record_digest"): (
            "SELECT record_json, record_digest FROM capabilities"
        ),
        ("owners", "record_json", "record_digest"): "SELECT record_json, record_digest FROM owners",
        ("assignments", "record_json", "record_digest"): (
            "SELECT record_json, record_digest FROM assignments"
        ),
        ("claims", "record_json", "record_digest"): "SELECT record_json, record_digest FROM claims",
        ("projections", "record_json", "record_digest"): (
            "SELECT record_json, record_digest FROM projections"
        ),
        ("reconciliations", "record_json", "record_json_digest"): (
            "SELECT record_json, record_json_digest FROM reconciliations"
        ),
    }
    query = queries.get((table, blob_column, digest_column))
    if query is None:
        raise ValueError("unapproved integrity table")
    for row in tx._connection.execute(query).fetchall():
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


def _verify_authority_tables(
    tx: SQLiteTransaction,
    wave_id: WaveId,
    expected: _AuthoritySnapshot,
) -> None:
    wave_row = tx._connection.execute(
        "SELECT repository_json,policy_revision,allowed_roles_json,bootstrap_event_id,created_store_revision "
        "FROM waves WHERE wave_id=?",
        (str(wave_id),),
    ).fetchone()
    expected_wave = (
        canonical_json_bytes(expected.wave["repository"]),
        int(expected.wave["policy_revision"]),
        canonical_json_bytes(expected.allowed_roles),
        expected.bootstrap_event_id,
        expected.created_store_revision,
    )
    if wave_row is None or (
        bytes(wave_row[0]),
        int(wave_row[1]),
        bytes(wave_row[2]),
        str(wave_row[3]),
        int(wave_row[4]),
    ) != expected_wave:
        raise CorruptStore("runtime wave authority differs from verified journal")

    def record_rows(table: str, key_column: str) -> dict[str, bytes]:
        queries = {
            ("owners", "role_id"): "SELECT role_id,record_json FROM owners WHERE wave_id=?",
            ("claims", "claim_id"): "SELECT claim_id,record_json FROM claims WHERE wave_id=?",
            ("reconciliations", "record_id"): (
                "SELECT record_id,record_json FROM reconciliations WHERE wave_id=?"
            ),
        }
        query = queries.get((table, key_column))
        if query is None:
            raise ValueError("unsupported authority record table")
        return {
            str(row[0]): bytes(row[1])
            for row in tx._connection.execute(query, (str(wave_id),)).fetchall()
        }

    if record_rows("owners", "role_id") != {
        key: canonical_json_bytes(value) for key, value in expected.owners.items()
    }:
        raise CorruptStore("runtime owner authority differs from verified journal")
    if record_rows("claims", "claim_id") != {
        key: canonical_json_bytes(value) for key, value in expected.claims.items()
    }:
        raise CorruptStore("runtime claim authority differs from verified journal")
    if record_rows("reconciliations", "record_id") != {
        key: canonical_json_bytes(value) for key, value in expected.reconciliations.items()
    }:
        raise CorruptStore("runtime reconciliation authority differs from verified journal")

    actual_capabilities: dict[str, bytes] = {}
    for snapshot_id in expected.capabilities:
        row = tx._connection.execute(
            "SELECT record_json FROM capabilities WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        if row is not None:
            actual_capabilities[snapshot_id] = bytes(row[0])
    if actual_capabilities != {
        key: canonical_json_bytes(value) for key, value in expected.capabilities.items()
    }:
        raise CorruptStore("runtime capability authority differs from verified journal")

    actual_assignments = {
        (str(row[0]), int(row[1])): bytes(row[2])
        for row in tx._connection.execute(
            "SELECT assignment_id,assignment_revision,record_json FROM assignments WHERE wave_id=?",
            (str(wave_id),),
        ).fetchall()
    }
    if actual_assignments != {
        key: canonical_json_bytes(value) for key, value in expected.assignments.items()
    }:
        raise CorruptStore("runtime assignment authority differs from verified journal")

    actual_participants = {
        (str(row[0]), str(row[1])): (str(row[2]), int(row[3]))
        for row in tx._connection.execute(
            "SELECT thread_id,role_id,first_generation_id,first_sequence "
            "FROM participants WHERE wave_id=?",
            (str(wave_id),),
        ).fetchall()
    }
    if actual_participants != expected.participants:
        raise CorruptStore("runtime participant authority differs from verified journal")

    actual_grants: dict[str, dict[str, Any]] = {}
    actual_consumption: dict[str, tuple[str, str]] = {}
    for row in tx._connection.execute("SELECT * FROM grants WHERE wave_id=?", (str(wave_id),)).fetchall():
        grant_id = str(row["grant_id"])
        actual_grants[grant_id] = {
            "authorized_by": row["authorized_by"],
            "consumed": row["consumed_record_id"] is not None,
            "created_store_revision": int(row["created_store_revision"]),
            "expires_at": row["expires_at"],
            "grant_id": grant_id,
            "not_before": row["not_before"],
            "policy_revision": int(row["policy_revision"]),
            "purpose": row["purpose"],
            "role_id": row["role_id"],
            "target_owner_generation": row["target_owner_generation"],
            "target_owner_version": (
                int(row["target_owner_version"])
                if row["target_owner_version"] is not None
                else None
            ),
            "thread_id": row["thread_id"],
            "wave_id": row["wave_id"],
        }
        if row["consumed_record_id"] is not None:
            actual_consumption[grant_id] = (
                str(row["consumed_record_id"]),
                str(row["consumed_record_digest"]),
            )
    if actual_grants != expected.grants or actual_consumption != expected.grant_consumption:
        raise CorruptStore("runtime grant authority differs from verified journal")

    actual_reconciliation_consumption = {
        str(row[0]): str(row[1])
        for row in tx._connection.execute(
            "SELECT record_id,consumed_by_event_id FROM reconciliations "
            "WHERE wave_id=? AND consumed_by_event_id IS NOT NULL",
            (str(wave_id),),
        ).fetchall()
    }
    if actual_reconciliation_consumption != expected.reconciliation_consumption:
        raise CorruptStore("runtime reconciliation consumption differs from verified journal")


def _replace_authority_tables(
    tx: SQLiteTransaction,
    wave_id: WaveId,
    expected: _AuthoritySnapshot,
) -> None:
    """Replace one wave's runtime authority only after its complete journal verifies."""

    wave_text = str(wave_id)
    delete_queries = (
        "DELETE FROM claims WHERE wave_id=?",
        "DELETE FROM assignments WHERE wave_id=?",
        "DELETE FROM owners WHERE wave_id=?",
        "DELETE FROM grants WHERE wave_id=?",
        "DELETE FROM reconciliations WHERE wave_id=?",
        "DELETE FROM participants WHERE wave_id=?",
    )
    for query in delete_queries:
        tx._connection.execute(query, (wave_text,))
    tx._connection.execute("DELETE FROM waves WHERE wave_id=?", (wave_text,))
    tx._connection.execute(
        "INSERT INTO waves(wave_id,repository_json,policy_revision,allowed_roles_json,bootstrap_event_id,"
        "created_store_revision) VALUES (?,?,?,?,?,?)",
        (
            wave_text,
            canonical_json_bytes(expected.wave["repository"]),
            int(expected.wave["policy_revision"]),
            canonical_json_bytes(expected.allowed_roles),
            expected.bootstrap_event_id,
            expected.created_store_revision,
        ),
    )

    for snapshot_id, value in expected.capabilities.items():
        encoded = canonical_json_bytes(value)
        existing = tx._connection.execute(
            "SELECT record_json FROM capabilities WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        if existing is not None and bytes(existing[0]) != encoded:
            raise CorruptStore("capability ID has conflicting bytes during replay")
        tx._connection.execute(
            "INSERT OR IGNORE INTO capabilities(snapshot_id,record_json,record_digest) VALUES (?,?,?)",
            (snapshot_id, encoded, digest_bytes(encoded)),
        )

    for grant_id, value in expected.grants.items():
        consumed = expected.grant_consumption.get(grant_id)
        tx._connection.execute(
            "INSERT INTO grants(grant_id,wave_id,role_id,thread_id,purpose,policy_revision,"
            "target_owner_generation,target_owner_version,created_store_revision,not_before,expires_at,"
            "authorized_by,consumed_record_id,consumed_record_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                grant_id,
                wave_text,
                value["role_id"],
                value["thread_id"],
                value["purpose"],
                int(value["policy_revision"]),
                value["target_owner_generation"],
                value["target_owner_version"],
                int(value["created_store_revision"]),
                value["not_before"],
                value["expires_at"],
                value["authorized_by"],
                consumed[0] if consumed else None,
                consumed[1] if consumed else None,
            ),
        )

    for role_id, value in expected.owners.items():
        encoded = canonical_json_bytes(value)
        tx._connection.execute(
            "INSERT INTO owners(wave_id,role_id,version,record_json,record_digest) VALUES (?,?,?,?,?)",
            (wave_text, role_id, int(value["record_version"]), encoded, digest_bytes(encoded)),
        )
    for (thread_id, role_id), (generation_id, sequence) in expected.participants.items():
        tx._connection.execute(
            "INSERT INTO participants(wave_id,thread_id,role_id,first_generation_id,first_sequence) "
            "VALUES (?,?,?,?,?)",
            (wave_text, thread_id, role_id, generation_id, sequence),
        )
    for (assignment_id, revision), value in expected.assignments.items():
        encoded = canonical_json_bytes(value)
        tx._connection.execute(
            "INSERT INTO assignments(wave_id,assignment_id,assignment_revision,record_json,record_digest) "
            "VALUES (?,?,?,?,?)",
            (wave_text, assignment_id, revision, encoded, digest_bytes(encoded)),
        )
    for record_id, value in expected.reconciliations.items():
        encoded = canonical_json_bytes(value)
        tx._connection.execute(
            "INSERT INTO reconciliations(record_id,record_digest,wave_id,record_json,record_json_digest,"
            "consumed_by_event_id) VALUES (?,?,?,?,?,?)",
            (
                record_id,
                value["record"]["digest"],
                wave_text,
                encoded,
                digest_bytes(encoded),
                expected.reconciliation_consumption.get(record_id),
            ),
        )
    for claim_id, value in expected.claims.items():
        encoded = canonical_json_bytes(value)
        tx._connection.execute(
            "INSERT INTO claims(claim_id,version,state,physical_host_id,physical_path,repository_host_id,"
            "repository_common_dir,wave_id,record_json,record_digest) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                claim_id,
                int(value["record_version"]),
                value["state"],
                value["target"]["host_instance_id"],
                value["target"]["canonical_path"],
                value["repository"]["host_instance_id"],
                value["repository"]["canonical_common_dir"],
                wave_text,
                encoded,
                digest_bytes(encoded),
            ),
        )


def verify_wave(store: SQLiteWaveStore, wave_id: WaveId) -> ReplayReport:
    store.full_integrity_check()
    with store.transaction() as tx:
        events = verified_events(tx, wave_id)
        projection_count, cursor_count = verify_materialized_state(tx, wave_id)
        from .events import build_projection_snapshot

        snapshot = build_projection_snapshot(events)
        authority = _authority_snapshot(wave_id, events, snapshot)
        _verify_rebuilt_snapshot(tx, wave_id, snapshot)
        _verify_authority_tables(tx, wave_id, authority)
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
        authority = _authority_snapshot(wave_id, events, snapshot)
        _replace_authority_tables(tx, wave_id, authority)
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
        _verify_authority_tables(tx, wave_id, authority)
        _verify_rebuilt_snapshot(tx, wave_id, snapshot)
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
