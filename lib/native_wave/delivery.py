"""Fresh actor checks for recipients; delivery-only operations for notifiers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from uuid import UUID, uuid5

from .delivery_store import DeliveryStore
from .delivery_types import DeliveryError, Permit, QueueEvidence, RuntimeBinding, RuntimeObservation, encode
from .event_types import (
    DurableEvent,
    EventDisposition,
    EventId,
    EventKind,
    ProvenanceClass,
    receipt_from_bytes,
)
from .identity import accept_process_evidence, observe_self
from .ports import HostProcessProbe
from .registry import check_owner
from .storage import SQLiteTransaction, SQLiteWaveStore
from .types import (
    CapabilitySnapshot,
    ExpectedOwnerBindings,
    LocalIdentityContext,
    ProcessObservationUnavailable,
    RoleId,
    RoleOwner,
    WaveId,
)


class DeliveryTransport(Protocol):
    def inspect(self, runtime: RuntimeBinding, thread: str, capability: CapabilitySnapshot) -> RuntimeObservation: ...
    def enqueue(self, runtime: RuntimeBinding, thread: str, pointer: str, command_id: str,
                *, before_send: Callable[[], None]) -> str: ...
    def reconcile(self, runtime: RuntimeBinding, thread: str, pointer: str, command_id: str) -> QueueEvidence: ...


@dataclass(frozen=True)
class Snapshot:
    event: DurableEvent
    issuer: RoleOwner
    recipient: RoleOwner
    capability: CapabilitySnapshot
    restriction: str | None


def event_recipient(event: DurableEvent) -> str | None:
    """Only validated event shape decides routes; prose never grants control authority."""
    command = event.command
    if event.disposition == EventDisposition.REJECTED:
        return None
    if command.assignment is not None:
        if str(command.actor.role_id) == "coordinator":
            return str(command.assignment.worker_role)
        if (command.actor.role_id == command.assignment.worker_role
                and command.actor.thread_id == command.assignment.worker_thread):
            return "coordinator"
    if (command.kind == EventKind.PROSE_MESSAGE and str(command.actor.role_id) != "coordinator"
            and command.provenance.classification == ProvenanceClass.REGISTRY_BOUND_LOCAL
            and event.disposition == EventDisposition.OBSERVED):
        return "coordinator"  # Information only; recipient cannot turn this into a gate.
    return None


class DeliveryService:
    def __init__(self, authority: SQLiteWaveStore, journal: DeliveryStore, probe: HostProcessProbe,
                 *, now: Callable[[], int] = lambda: int(time.time())) -> None:
        self.authority, self.journal, self.probe, self.now = authority, journal, probe, now

    def _actor(self, tx: SQLiteTransaction, wave: WaveId, role: RoleId,
               context: LocalIdentityContext) -> RoleOwner:
        owner = tx.read_owner(wave, role)
        if owner is None:
            raise DeliveryError("owner_missing")
        candidate = observe_self(context, self.probe)
        if isinstance(candidate, ProcessObservationUnavailable):
            raise DeliveryError("fresh_process_evidence_unavailable")
        evidence = accept_process_evidence(tx, candidate, self.probe)
        if isinstance(evidence, ProcessObservationUnavailable):
            raise DeliveryError("fresh_process_evidence_changed")
        expected = ExpectedOwnerBindings(wave, role, owner.thread_id, owner.generation_id,
                                         owner.capability_snapshot_id, owner.policy_revision, owner.record_version)
        result = check_owner(tx, evidence, expected)
        if not result.allowed:
            assert result.refusal is not None
            raise DeliveryError(result.refusal.code.value)
        return owner

    @staticmethod
    def _event(tx: SQLiteTransaction, wave: WaveId, event_id: EventId) -> DurableEvent:
        existing = tx.lookup_event(wave, event_id)
        if existing is None:
            raise DeliveryError("authoritative_event_missing")
        if len(existing.command_bytes) > 1_048_576:
            raise DeliveryError("authoritative event exceeds delivery byte budget")
        receipt = receipt_from_bytes(existing.receipt_bytes)
        if receipt.sequence is None:
            raise DeliveryError("event_not_committed")
        return tx.read_event_page(wave, after_sequence=receipt.sequence - 1, limit=1)[0]

    def snapshot(self, wave: str, event_id: str, *, context: LocalIdentityContext | None = None,
                 actor_role: str | None = None) -> Snapshot:
        """Short serialized snapshot; no sidecar or RPC call while this transaction lives."""
        with self.authority.transaction() as tx:
            event = self._event(tx, WaveId(wave), EventId.parse(event_id))
            route = event_recipient(event)
            if route is None:
                raise DeliveryError("event_route_unresolved_or_rejected")
            command = event.command
            issuer = tx.read_owner(command.wave_id, command.actor.role_id)
            recipient = tx.read_owner(command.wave_id, RoleId(route))
            policy = tx.read_policy_revision(command.wave_id)
            if issuer is None or recipient is None:
                raise DeliveryError("current_owner_missing")
            if (issuer.thread_id != command.actor.thread_id
                    or str(issuer.generation_id) != str(command.actor.generation_id)):
                raise DeliveryError("event_author_generation_stale")
            if issuer.policy_revision != policy or recipient.policy_revision != policy:
                raise DeliveryError("stale_policy")
            if context is not None:
                if actor_role not in {str(issuer.role_id), str(recipient.role_id), "coordinator"}:
                    raise DeliveryError("caller_role_not_on_route")
                self._actor(tx, command.wave_id, RoleId(str(actor_role)), context)
            restriction = None
            binding = command.assignment
            if binding is not None:
                worker = tx.read_owner(command.wave_id, binding.worker_role)
                coordinator = tx.read_owner(command.wave_id, RoleId("coordinator"))
                projection = tx.get_projection(command.wave_id, "assignment", str(binding.ref.assignment_id))
                if (worker is None or coordinator is None or projection is None
                        or worker.thread_id != binding.worker_thread
                        or worker.generation_id != binding.worker_generation
                        or worker.capability_snapshot_id != binding.capability_snapshot_id
                        or str(coordinator.generation_id) != str(binding.coordinator_generation)
                        or binding.policy_revision != policy
                        or projection["assignment_revision"] != binding.ref.revision
                        or projection["assignment_digest"] != binding.ref.digest
                        or projection["issue"] != binding.issue):
                    raise DeliveryError("assignment_binding_stale")
                if projection["state"] in {"held", "cancelled", "completed"}:
                    restriction = str(projection["state"])
            capability = tx.read_capability(recipient.capability_snapshot_id)
            if capability is None:
                raise DeliveryError("capability_missing")
            return Snapshot(event, issuer, recipient, capability, restriction)

    def _validate(self, permit: Permit, *, context: LocalIdentityContext | None = None,
                  recipient: bool = False) -> Snapshot:
        if permit.authority_store_id != self.authority.store_id:
            raise DeliveryError("authoritative_store_replaced")
        snapshot = self.snapshot(permit.wave, permit.event_id, context=context,
                                 actor_role=permit.recipient_role if recipient else permit.issuer_role)
        if (snapshot.event.event_digest != permit.event_digest
                or str(snapshot.issuer.role_id) != permit.issuer_role
                or str(snapshot.issuer.thread_id) != permit.issuer_thread
                or str(snapshot.issuer.generation_id) != permit.issuer_generation
                or str(snapshot.recipient.role_id) != permit.recipient_role
                or str(snapshot.recipient.thread_id) != permit.recipient_thread
                or str(snapshot.recipient.generation_id) != permit.recipient_generation
                or snapshot.recipient.policy_revision != permit.policy_revision
                or str(snapshot.capability.snapshot_id) != permit.capability_id
                or snapshot.recipient.process.host_instance_id != permit.runtime.host_id
                or str(snapshot.recipient.process.boot_id) != permit.runtime.boot_id):
            raise DeliveryError("permit_binding_stale")
        return snapshot

    def issue(self, wave: str, event_id: str, issuer_role: str, context: LocalIdentityContext,
              runtime: RuntimeBinding, *, deadline: int, max_attempts: int = 3) -> Permit:
        snapshot = self.snapshot(wave, event_id, context=context, actor_role=issuer_role)
        if issuer_role not in {str(snapshot.issuer.role_id), "coordinator"}:
            raise DeliveryError("only_event_author_or_coordinator_may_issue")
        if deadline <= self.now() or deadline > self.now() + 900:
            raise DeliveryError("deadline must be within the next 900 seconds")
        permit = Permit(self.authority.store_id, wave, event_id, snapshot.event.event_digest,
                        str(snapshot.issuer.role_id), str(snapshot.issuer.thread_id),
                        str(snapshot.issuer.generation_id), str(snapshot.recipient.role_id),
                        str(snapshot.recipient.thread_id), str(snapshot.recipient.generation_id),
                        snapshot.recipient.policy_revision, str(snapshot.capability.snapshot_id), runtime,
                        deadline, max_attempts)
        self._validate(permit)
        return self.journal.issue(permit)

    def fetch(self, permit_id: str, context: LocalIdentityContext) -> dict[str, Any]:
        permit, _ = self.journal.read(permit_id)
        snapshot = self._validate(permit, context=context, recipient=True)
        event_bytes = snapshot.event.command.canonical_bytes()
        if len(event_bytes) > 65536:
            raise DeliveryError("fetch output byte budget exceeded; no receipt recorded")
        return {"permit_id": permit_id, "event": event_bytes.decode(),
                "event_digest": snapshot.event.event_digest, "restriction": snapshot.restriction,
                "fetch_token": self.journal.fetch_token(permit_id), "receipt_confirmed": False}

    def receipt(self, permit_id: str, token: str, context: LocalIdentityContext) -> dict[str, Any]:
        permit, _ = self.journal.read(permit_id)
        self._validate(permit, context=context, recipient=True)
        return self.journal.receive(permit_id, token, self.now())

    def status(self, permit_id: str) -> dict[str, Any]:
        permit, state = self.journal.read(permit_id)
        current = True
        try:
            self._validate(permit)
        except DeliveryError:
            current = False
        return {"permit_id": permit_id, "phase": state["phase"], "detail": state["detail"],
                "attempts": state["attempts"], "deadline": permit.deadline,
                "current_binding": current, "receipt_confirmed": bool(state["receipt"]) and current,
                "historical_receipt": state["receipt"], "stopped": state["stopped"]}

    def stop(self, permit_id: str, context: LocalIdentityContext) -> None:
        permit, _ = self.journal.read(permit_id)
        self.snapshot(permit.wave, permit.event_id, context=context, actor_role="coordinator")
        self.journal.stop(permit_id)

    def pointer(self, permit: Permit) -> str:
        return (f"CxPP durable event pointer: journal={self.journal.store_id} permit={permit.permit_id} "
                f"wave={permit.wave} event={permit.event_id}. Fetch and inspect through the registered "
                "native-wave-delivery adapter; then explicitly receipt with its fetch token. "
                "This pointer is not an assignment acceptance or gate authorization.")

    def notify(self, permit_id: str, transport: DeliveryTransport) -> dict[str, Any]:
        permit, _ = self.journal.read(permit_id)
        self._validate(permit)
        lease = self.journal.acquire(permit_id, self.now())
        try:
            snapshot = self._validate(permit)
            if snapshot.restriction:
                raise DeliveryError("wave_" + snapshot.restriction)
            for owner in (snapshot.issuer, snapshot.recipient):
                if self.probe.observe_recorded(owner.process) != owner.process:
                    raise DeliveryError("owner_process_changed_or_unknown")
            observed = transport.inspect(permit.runtime, permit.recipient_thread, snapshot.capability)
            if observed.state not in {"idle", "busy"}:
                raise DeliveryError(observed.state + ": " + observed.detail)
            _, state = self.journal.read(permit_id)
            pointer = self.pointer(permit)
            if not state["external_started"]:
                # Commit BEFORE enqueue. A crash or ambiguous result can never return to pending.
                self._validate(permit)
                self.journal.record(lease, self.now(), phase="enqueue_started")
                def before_send() -> None:
                    current = self._validate(permit)
                    if current.restriction:
                        raise DeliveryError("wave_" + current.restriction)
                    self.journal.check_lease(lease, self.now())
                submission = transport.enqueue(permit.runtime, permit.recipient_thread, pointer, permit_id,
                                                before_send=before_send)
                self.journal.record(lease, self.now(), phase="queued", submission_id=submission)
            self._validate(permit)
            evidence = transport.reconcile(permit.runtime, permit.recipient_thread, pointer, permit_id)
            self.journal.record(lease, self.now(), phase=evidence.state, submission_id=evidence.submission_id,
                                detail="transport observation; recipient receipt remains independent", release=True)
        except DeliveryError as exc:
            # Preserve uncertainty even if an external call committed but its response was lost.
            try:
                self.journal.record(lease, self.now(), phase="unknown", detail=str(exc), release=True)
            except DeliveryError as record_error:
                if str(record_error) != "stale_notifier_lease":
                    raise
                # The pre-call record is already durable. A newer lease owns observation.
                return {**self.status(permit_id), "attempt_error": "stale_notifier_lease"}
        return self.status(permit_id)

    def pending(self, wave: str, role: str, context: LocalIdentityContext,
                *, after_sequence: int = 0, limit: int = 100) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DeliveryError("pending page limit must be 1..100")
        # Even an empty event page must not conceal a missing/replaced sidecar.
        self.journal.page(limit=1)
        with self.authority.transaction() as tx:
            self._actor(tx, WaveId(wave), RoleId(role), context)
            events = tx.read_event_page(WaveId(wave), after_sequence=after_sequence, limit=limit)
        rows: list[dict[str, Any]] = []
        for event in events:
            route = event_recipient(event)
            if route is None or (route != role and str(event.command.actor.role_id) != role):
                if (route is None and event.command.kind == EventKind.PROSE_MESSAGE
                        and str(event.command.actor.role_id) == role):
                    rows.append({"event_id": str(event.command.event_id), "state": "issuer_route_unresolved"})
                continue
            try:
                snapshot = self.snapshot(wave, str(event.command.event_id))
            except DeliveryError:
                continue  # Stale/terminal historical revisions cannot become current work.
            key = (self.authority.store_id, wave, str(event.command.event_id), route,
                   str(snapshot.recipient.generation_id))
            permit_id = str(uuid5(UUID("d74b320e-1781-46f8-bff6-f588b36346ac"), encode(key)))
            try:
                _, delivery = self.journal.read(permit_id)
            except DeliveryError as exc:
                if not str(exc).startswith("permit_missing:"):
                    raise
                rows.append({"event_id": str(event.command.event_id), "state": "event_without_permit",
                             "restriction": snapshot.restriction})
                continue
            if delivery["receipt"] is None:
                rows.append({"event_id": str(event.command.event_id), "permit_id": permit_id,
                             "state": "receipt_outstanding", "restriction": snapshot.restriction})
            if event.command.kind in {EventKind.ASSIGNMENT_QUEUED, EventKind.ASSIGNMENT_REBOUND}:
                with self.authority.transaction() as tx:
                    assert event.command.assignment is not None
                    current = tx.read_assignment(event.command.assignment.ref)
                if current is not None and not current.acknowledged and snapshot.restriction is None:
                    rows.append({"event_id": str(event.command.event_id), "state": "assignment_unaccepted"})
        result = {"events": rows, "next_sequence": events[-1].sequence if events else after_sequence,
                  "more_possible": len(events) == limit, "cursor_advanced": False}
        if len(encode(result).encode()) > 65536:
            raise DeliveryError("pending byte budget exceeded; request a smaller page")
        return result
