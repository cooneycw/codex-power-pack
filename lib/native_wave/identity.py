"""Linux process identity observation for native Codex sessions.

The adapter reads only bounded local process metadata.  Queue state, heartbeat
files, terminal labels, and caller prose are intentionally absent: none prove
that a native thread still owns the same host process generation.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from uuid import UUID

from .ports import HostProcessProbe, OwnershipTransaction
from .types import (
    AcceptedProcessEvidence,
    LocalIdentityContext,
    ObservationFailure,
    ProcessCoordinates,
    ProcessObservation,
    ProcessObservationUnavailable,
    ThreadId,
    TransactionClosedError,
)


class LinuxHostProcessProbe(HostProcessProbe):
    """Observe a native Codex ancestor through ``/proc`` without waiting.

    Injectable readers keep the implementation deterministic in unit tests and
    avoid ever launching a live Codex process as proof.
    """

    def __init__(
        self,
        *,
        proc_root: Path = Path("/proc"),
        host_id_path: Path = Path("/etc/machine-id"),
        boot_id_path: Path = Path("/proc/sys/kernel/random/boot_id"),
        environ: Mapping[str, str] | None = None,
        getpid: Callable[[], int] = os.getpid,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        max_ancestors: int = 64,
    ) -> None:
        if max_ancestors < 1 or max_ancestors > 256:
            raise ValueError("max_ancestors must be between 1 and 256")
        self._proc_root = proc_root
        self._host_id_path = host_id_path
        self._boot_id_path = boot_id_path
        self._environ = environ if environ is not None else os.environ
        self._getpid = getpid
        self._monotonic_ns = monotonic_ns
        self._max_ancestors = max_ancestors

    @staticmethod
    def _unavailable(reason: ObservationFailure, detail: str) -> ProcessObservationUnavailable:
        return ProcessObservationUnavailable(reason=reason, detail=detail)

    def _host_and_boot(self) -> tuple[str, UUID] | ProcessObservationUnavailable:
        try:
            host_id = self._host_id_path.read_text(encoding="utf-8").strip().lower()
        except (OSError, UnicodeError):
            return self._unavailable(ObservationFailure.HOST_ID_UNAVAILABLE, "host instance id is unreadable")
        if not host_id or any(character not in "0123456789abcdef" for character in host_id):
            return self._unavailable(ObservationFailure.HOST_ID_UNAVAILABLE, "host instance id is malformed")
        try:
            boot_id = UUID(self._boot_id_path.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeError, ValueError):
            return self._unavailable(ObservationFailure.BOOT_ID_UNAVAILABLE, "boot id is unreadable or malformed")
        return host_id, boot_id

    def _stat(self, pid: int) -> tuple[int, int] | ProcessObservationUnavailable:
        try:
            raw = (self._proc_root / str(pid) / "stat").read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._unavailable(ObservationFailure.PROCESS_MISSING, f"process {pid} is absent")
        except (OSError, UnicodeError):
            return self._unavailable(ObservationFailure.PROBE_UNAVAILABLE, f"process {pid} stat is unreadable")
        close = raw.rfind(")")
        if close < 0:
            return self._unavailable(ObservationFailure.CONTRADICTORY, f"process {pid} stat is malformed")
        fields = raw[close + 2 :].split()
        try:
            parent_pid = int(fields[1])
            start_ticks = int(fields[19])
        except (IndexError, ValueError):
            return self._unavailable(ObservationFailure.CONTRADICTORY, f"process {pid} stat is malformed")
        if parent_pid < 0 or start_ticks < 0:
            return self._unavailable(ObservationFailure.CONTRADICTORY, f"process {pid} stat has negative fields")
        return parent_pid, start_ticks

    def _looks_like_codex(self, pid: int) -> bool:
        try:
            command = (self._proc_root / str(pid) / "comm").read_text(encoding="utf-8").strip().casefold()
            argv0 = (
                (self._proc_root / str(pid) / "cmdline")
                .read_bytes()
                .split(b"\0", 1)[0]
                .decode("utf-8", "replace")
                .casefold()
            )
        except (OSError, UnicodeError):
            return False
        return command in {"codex", "codex-cli"} or Path(argv0).name in {"codex", "codex-cli"}

    def _native_thread(self) -> ThreadId | ProcessObservationUnavailable:
        raw = self._environ.get("CODEX_THREAD_ID", "")
        if not raw:
            return self._unavailable(ObservationFailure.MISSING_THREAD, "CODEX_THREAD_ID is not present")
        try:
            return ThreadId(UUID(raw))
        except ValueError:
            return self._unavailable(ObservationFailure.MALFORMED_THREAD, "CODEX_THREAD_ID is not a UUID")

    def observe_self(
        self, context: LocalIdentityContext
    ) -> ProcessObservation | ProcessObservationUnavailable:
        native_thread = self._native_thread()
        if isinstance(native_thread, ProcessObservationUnavailable):
            return native_thread
        if native_thread != context.thread_id:
            return self._unavailable(
                ObservationFailure.IDENTITY_CHANGED,
                "native thread binding does not match the requested context",
            )
        pid = self._getpid()
        if pid <= 1:
            return self._unavailable(ObservationFailure.NAMESPACE_PID1, "PID 1 cannot prove host ownership")
        host_boot = self._host_and_boot()
        if isinstance(host_boot, ProcessObservationUnavailable):
            return host_boot
        host_id, boot_id = host_boot
        seen: set[int] = set()
        for _ in range(self._max_ancestors):
            if pid <= 1 or pid in seen:
                break
            seen.add(pid)
            stat = self._stat(pid)
            if isinstance(stat, ProcessObservationUnavailable):
                return stat
            parent_pid, start_ticks = stat
            if self._looks_like_codex(pid):
                return ProcessObservation(
                    thread_id=native_thread,
                    process=ProcessCoordinates(host_id, boot_id, pid, start_ticks),
                    observed_monotonic_ns=self._monotonic_ns(),
                    provenance="linux-proc-native-codex-ancestor",
                )
            pid = parent_pid
        return self._unavailable(
            ObservationFailure.NO_CODEX_ANCESTOR,
            "bounded process ancestry contained no native Codex process",
        )

    def revalidate(
        self, observation: ProcessObservation
    ) -> ProcessObservation | ProcessObservationUnavailable:
        refreshed = self.observe_self(LocalIdentityContext(observation.thread_id))
        if isinstance(refreshed, ProcessObservationUnavailable):
            return refreshed
        if refreshed.thread_id != observation.thread_id or refreshed.process != observation.process:
            return self._unavailable(ObservationFailure.IDENTITY_CHANGED, "process identity changed on revalidation")
        return refreshed

    def observe_recorded(
        self, process: ProcessCoordinates
    ) -> ProcessCoordinates | ProcessObservationUnavailable:
        host_boot = self._host_and_boot()
        if isinstance(host_boot, ProcessObservationUnavailable):
            return host_boot
        host_id, boot_id = host_boot
        if host_id != process.host_instance_id:
            return self._unavailable(ObservationFailure.PROBE_UNAVAILABLE, "recorded owner belongs to another host")
        if boot_id != process.boot_id:
            return self._unavailable(ObservationFailure.BOOT_CHANGED, "recorded boot generation is no longer current")
        stat = self._stat(process.pid)
        if isinstance(stat, ProcessObservationUnavailable):
            return stat
        _, start_ticks = stat
        if start_ticks != process.start_ticks:
            return ProcessCoordinates(host_id, boot_id, process.pid, start_ticks)
        return process


def observe_self(
    context: LocalIdentityContext, probe: HostProcessProbe
) -> ProcessObservation | ProcessObservationUnavailable:
    """Discover identity only; the result is not authority until accepted."""

    return probe.observe_self(context)


def accept_process_evidence(
    tx: OwnershipTransaction,
    candidate: ProcessObservation,
    probe: HostProcessProbe,
) -> AcceptedProcessEvidence | ProcessObservationUnavailable:
    """Re-read all process coordinates after the serialized transaction opens."""

    if not tx.is_active:
        raise TransactionClosedError("process evidence requires an active transaction")
    refreshed = probe.revalidate(candidate)
    if isinstance(refreshed, ProcessObservationUnavailable):
        return refreshed
    if refreshed.thread_id != candidate.thread_id or refreshed.process != candidate.process:
        return ProcessObservationUnavailable(
            ObservationFailure.IDENTITY_CHANGED,
            "candidate process evidence changed inside the transaction",
        )
    return AcceptedProcessEvidence(
        transaction_id=tx.transaction_id,
        observation=refreshed,
        revalidated_monotonic_ns=refreshed.observed_monotonic_ns,
    )


__all__ = ["LinuxHostProcessProbe", "accept_process_evidence", "observe_self"]
