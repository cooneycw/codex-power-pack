"""Private notification journal; never mutates the authoritative wave database."""

from __future__ import annotations

import hmac
import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .delivery_types import DeliveryError, Lease, Permit, digest, encode

_SCHEMA = """
CREATE TABLE meta(id TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE permits(id TEXT PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL,
 state TEXT NOT NULL, state_digest TEXT NOT NULL);
"""


def _private(path: Path, *, directory: bool = False) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise DeliveryError("delivery journal missing or inaccessible; explicit recovery required") from exc
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise DeliveryError("delivery journal must be owner-private and not a symlink")
    return info


class DeliveryStore:
    def __init__(self, path: Path, store_id: str, identity: tuple[int, int]) -> None:
        self.path, self.store_id, self.identity = path, store_id, identity

    @classmethod
    def create(cls, path: Path) -> DeliveryStore:
        path = path.absolute()
        _private(path.parent, directory=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        connection = sqlite3.connect(path)
        store_id = str(uuid4())
        try:
            connection.executescript(_SCHEMA)
            connection.execute("INSERT INTO meta VALUES (?,1)", (store_id,))
            connection.commit()
        finally:
            connection.close()
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return cls.open(path, store_id)

    @classmethod
    def open(cls, path: Path, expected_id: str) -> DeliveryStore:
        path = path.absolute()
        _private(path.parent, directory=True)
        info = _private(path)
        store = cls(path, expected_id, (info.st_dev, info.st_ino))
        with store.transaction():
            pass
        return store

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        _private(self.path.parent, directory=True)
        info = _private(self.path)
        if (info.st_dev, info.st_ino) != self.identity:
            raise DeliveryError("delivery journal replaced")
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=0.25,
                                     isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            meta = connection.execute("SELECT id,version FROM meta").fetchall()
            if len(meta) != 1 or tuple(meta[0]) != (self.store_id, 1):
                raise DeliveryError("delivery journal identity/schema mismatch")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise DeliveryError("delivery journal corrupt")
            info = _private(self.path)
            if (info.st_dev, info.st_ino) != self.identity:
                raise DeliveryError("delivery journal changed while opening")
            yield connection
            connection.commit()
        except sqlite3.DatabaseError as exc:
            raise DeliveryError("delivery journal failure; commit outcome may be unknown") from exc
        finally:
            connection.close()

    @staticmethod
    def _read(connection: sqlite3.Connection, permit_id: str) -> tuple[Permit, dict[str, Any]]:
        row = connection.execute("SELECT * FROM permits WHERE id=?", (permit_id,)).fetchone()
        if row is None:
            raise DeliveryError("permit_missing: reconcile from authoritative events")
        try:
            if len(row["body"].encode()) > 16384 or len(row["state"].encode()) > 4096:
                raise DeliveryError("delivery record byte budget exceeded")
            body, state = json.loads(row["body"]), json.loads(row["state"])
            if digest(body) != row["digest"] or digest(state) != row["state_digest"]:
                raise DeliveryError("delivery journal record digest mismatch")
            permit = Permit.from_dict(body)
            if permit.permit_id != permit_id:
                raise DeliveryError("permit key mismatch")
            required = {"phase", "attempts", "next_at", "epoch", "lease", "lease_until", "submission_id",
                        "fetch_token", "receipt", "detail", "stopped", "external_started"}
            if not isinstance(state, dict) or set(state) != required:
                raise DeliveryError("invalid delivery state schema")
            for field in ("attempts", "next_at", "epoch", "lease_until"):
                if type(state[field]) is not int or state[field] < 0:
                    raise DeliveryError("invalid delivery state counter")
            if state["attempts"] > permit.max_attempts:
                raise DeliveryError("invalid attempt budget")
            if any(type(state[field]) is not bool for field in ("stopped", "external_started")):
                raise DeliveryError("invalid delivery state flag")
            if not isinstance(state["phase"], str) or not isinstance(state["detail"], str):
                raise DeliveryError("invalid delivery observation")
            for field in ("lease", "fetch_token", "submission_id"):
                if state[field] is not None and not isinstance(state[field], str):
                    raise DeliveryError("invalid delivery identifier")
            receipt = state["receipt"]
            if receipt is not None and (not isinstance(receipt, dict)
                    or receipt.get("thread") != permit.recipient_thread
                    or receipt.get("generation") != permit.recipient_generation
                    or receipt.get("event_id") != permit.event_id or type(receipt.get("received_at")) is not int):
                raise DeliveryError("invalid recipient receipt")
            return permit, state
        except (TypeError, ValueError, KeyError) as exc:
            raise DeliveryError("invalid delivery journal record") from exc

    @staticmethod
    def _write(connection: sqlite3.Connection, permit_id: str, state: dict[str, Any]) -> None:
        if len(encode(state).encode()) > 4096:
            raise DeliveryError("delivery state byte budget exceeded")
        connection.execute("UPDATE permits SET state=?,state_digest=? WHERE id=?",
                           (encode(state), digest(state), permit_id))

    def issue(self, permit: Permit) -> Permit:
        with self.transaction() as connection:
            if connection.execute("SELECT 1 FROM permits WHERE id=?", (permit.permit_id,)).fetchone():
                current, _ = self._read(connection, permit.permit_id)
                if current.request() != permit.request():
                    raise DeliveryError("permit_id_payload_conflict")
                return current
            state = {"phase": "pending", "attempts": 0, "next_at": 0, "epoch": 0, "lease": None,
                     "lease_until": 0, "submission_id": None, "fetch_token": None, "receipt": None,
                     "detail": "", "stopped": False, "external_started": False}
            body = asdict(permit)
            if len(encode(body).encode()) > 16384:
                raise DeliveryError("permit byte budget exceeded")
            connection.execute("INSERT INTO permits VALUES (?,?,?,?,?)",
                               (permit.permit_id, encode(body), digest(body), encode(state), digest(state)))
            return permit

    def read(self, permit_id: str) -> tuple[Permit, dict[str, Any]]:
        with self.transaction() as connection:
            return self._read(connection, permit_id)

    def acquire(self, permit_id: str, now: int) -> Lease:
        with self.transaction() as connection:
            permit, state = self._read(connection, permit_id)
            if state["receipt"] or state["stopped"]:
                raise DeliveryError("received_or_stopped")
            if now >= permit.deadline or state["attempts"] >= permit.max_attempts:
                raise DeliveryError("deadline_or_attempt_budget_exhausted: receipt_unknown")
            if now < state["lease_until"] or now < state["next_at"]:
                raise DeliveryError("lease_busy_or_backoff")
            state["epoch"] += 1
            state["lease"] = str(uuid4())
            state["lease_until"] = min(now + 30, permit.deadline)
            state["attempts"] += 1
            self._write(connection, permit_id, state)
            return Lease(permit_id, state["epoch"], state["lease"], state["lease_until"])

    def record(self, lease: Lease, now: int, *, phase: str, detail: str = "",
               submission_id: str | None = None, release: bool = False) -> None:
        with self.transaction() as connection:
            _, state = self._read(connection, lease.permit_id)
            if (state["epoch"] != lease.epoch or state["lease"] != lease.token
                    or now >= state["lease_until"] or state["stopped"]):
                raise DeliveryError("stale_notifier_lease")
            state.update(phase=phase, detail=detail[:512])
            if phase == "enqueue_started":
                if state["external_started"]:
                    raise DeliveryError("enqueue_already_started")
                state["external_started"] = True
            if submission_id is not None:
                state["submission_id"] = submission_id
            if release:
                state["lease_until"] = 0
                state["lease"] = None
                state["next_at"] = now + min(30, 2 ** state["attempts"])
            self._write(connection, lease.permit_id, state)

    def check_lease(self, lease: Lease, now: int) -> None:
        with self.transaction() as connection:
            permit, state = self._read(connection, lease.permit_id)
            if (state["epoch"] != lease.epoch or state["lease"] != lease.token
                    or now >= min(state["lease_until"], permit.deadline) or state["stopped"] or state["receipt"]):
                raise DeliveryError("stale_notifier_lease")

    def fetch_token(self, permit_id: str) -> str:
        with self.transaction() as connection:
            _, state = self._read(connection, permit_id)
            if state["fetch_token"] is None:
                state["fetch_token"] = str(uuid4())
                self._write(connection, permit_id, state)
            return str(state["fetch_token"])

    def receive(self, permit_id: str, token: str, now: int) -> dict[str, Any]:
        """Called only by DeliveryService.receipt after fresh recipient validation."""
        with self.transaction() as connection:
            permit, state = self._read(connection, permit_id)
            if not state["fetch_token"] or not hmac.compare_digest(state["fetch_token"], token):
                raise DeliveryError("receipt_requires_fetch_token")
            if state["receipt"] is None:
                state["receipt"] = {"thread": permit.recipient_thread, "generation": permit.recipient_generation,
                                    "event_id": permit.event_id, "received_at": now}
                self._write(connection, permit_id, state)
            return dict(state["receipt"])

    def stop(self, permit_id: str) -> None:
        with self.transaction() as connection:
            _, state = self._read(connection, permit_id)
            state["stopped"] = True
            state["epoch"] += 1
            self._write(connection, permit_id, state)

    def page(self, after: str = "", limit: int = 100) -> list[tuple[Permit, dict[str, Any]]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DeliveryError("page limit must be 1..100")
        with self.transaction() as connection:
            ids = connection.execute("SELECT id FROM permits WHERE id>? ORDER BY id LIMIT ?", (after, limit))
            return [self._read(connection, row[0]) for row in ids.fetchall()]
