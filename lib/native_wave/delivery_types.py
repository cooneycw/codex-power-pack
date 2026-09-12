"""Delivery observations are not assignment, gate, or completion authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5


class DeliveryError(RuntimeError):
    """A delivery operation could not establish its required evidence."""


def encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


@dataclass(frozen=True)
class RuntimeBinding:
    socket_path: str
    host_id: str
    boot_id: str
    server_pid: int
    server_start_ticks: int
    socket_device: int
    socket_inode: int
    executable_digest: str
    cli_version: str

    def __post_init__(self) -> None:
        if not Path(self.socket_path).is_absolute() or Path(self.socket_path).resolve() != Path(self.socket_path):
            raise DeliveryError("socket must be an explicit canonical absolute path")
        UUID(self.boot_id)
        for value in (self.server_pid, self.server_start_ticks, self.socket_device, self.socket_inode):
            if type(value) is not int or value < 0:
                raise DeliveryError("invalid runtime process/socket coordinates")
        if self.server_pid <= 1 or len(self.executable_digest) != 64 or not self.host_id or not self.cli_version:
            raise DeliveryError("incomplete runtime binding")


@dataclass(frozen=True)
class Permit:
    authority_store_id: str
    wave: str
    event_id: str
    event_digest: str
    issuer_role: str
    issuer_thread: str
    issuer_generation: str
    recipient_role: str
    recipient_thread: str
    recipient_generation: str
    policy_revision: int
    capability_id: str
    runtime: RuntimeBinding
    deadline: int
    max_attempts: int = 3

    def __post_init__(self) -> None:
        for value in (self.event_id, self.issuer_thread, self.issuer_generation,
                      self.recipient_thread, self.recipient_generation):
            if str(UUID(value)) != value:
                raise DeliveryError("permit identity must be a canonical UUID")
        if not all((self.authority_store_id, self.wave, self.event_digest, self.capability_id,
                    self.issuer_role, self.recipient_role)):
            raise DeliveryError("incomplete permit")
        if type(self.policy_revision) is not int or self.policy_revision < 1:
            raise DeliveryError("invalid policy revision")
        if type(self.deadline) is not int or self.deadline < 1:
            raise DeliveryError("invalid deadline")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise DeliveryError("attempt budget must be 1..5")

    @property
    def permit_id(self) -> str:
        key = (self.authority_store_id, self.wave, self.event_id, self.recipient_role, self.recipient_generation)
        return str(uuid5(UUID("d74b320e-1781-46f8-bff6-f588b36346ac"), encode(key)))

    def request(self) -> dict[str, Any]:
        value = asdict(self)
        # Reissue preserves the first deadline and budget; it cannot reset either.
        value.pop("deadline")
        value.pop("max_attempts")
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Permit:
        return cls(**{**value, "runtime": RuntimeBinding(**value["runtime"])})


@dataclass(frozen=True)
class RuntimeObservation:
    state: str
    detail: str = ""


@dataclass(frozen=True)
class QueueEvidence:
    state: str  # queued, started, unknown; absence is never proof of non-delivery
    submission_id: str | None = None


@dataclass(frozen=True)
class Lease:
    permit_id: str
    epoch: int
    token: str
    expires_at: int
