"""Fail-open writer for Codex friction telemetry."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from lib.creds.masking import OutputMasker

from .models import HARNESS, FrictionEvent, FrictionEventError, truncate, utc_now

CPP_MEMORY_ENV = "CXPP_CPP_MEMORY_CMD"
QUEUE_ENV = "CXPP_FRICTION_QUEUE"

Runner = Callable[
    [Sequence[str], Path | None, Mapping[str, str], int],
    subprocess.CompletedProcess[str],
]


@dataclass(frozen=True)
class FrictionWriteResult:
    """Result of a friction write attempt.

    `ok` means the caller workflow may continue. Ledger outages and missing
    clients are represented as `ok=True` with a non-shared `stored` value.
    """

    ok: bool
    stored: str
    event: dict[str, object] | None = None
    ledger: dict[str, object] | None = None
    reason: str | None = None
    local_path: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "stored": self.stored,
            "event": self.event,
            "ledger": self.ledger,
            "reason": self.reason,
            "local_path": self.local_path,
        }


def _default_runner(
    argv: Sequence[str],
    cwd: Path | None,
    env: Mapping[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd) if cwd else None,
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _resolve_command(command: Sequence[str] | str | None) -> list[str] | None:
    if command:
        return shlex.split(command) if isinstance(command, str) else list(command)

    env_command = os.environ.get(CPP_MEMORY_ENV, "").strip()
    if env_command:
        return shlex.split(env_command)

    found = shutil.which("cpp-memory")
    if found:
        return [found]

    return None


class FrictionWriter:
    """Validate, mask, fingerprint, and write Codex friction events."""

    def __init__(
        self,
        *,
        command: Sequence[str] | str | None = None,
        queue_path: Path | str | None = None,
        cwd: Path | str | None = None,
        timeout: int = 10,
        masker: OutputMasker | None = None,
        runner: Runner | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.command = _resolve_command(command)
        self.queue_path = Path(queue_path) if queue_path else self._queue_from_env()
        self.cwd = Path(cwd) if cwd else None
        self.timeout = timeout
        self.masker = masker or OutputMasker()
        self.runner = runner or _default_runner
        self.env = dict(os.environ if env is None else env)
        self.env["CPP_HARNESS"] = HARNESS

    @staticmethod
    def _queue_from_env() -> Path | None:
        value = os.environ.get(QUEUE_ENV, "").strip()
        return Path(value) if value else None

    def write(self, data: Mapping[str, Any] | FrictionEvent) -> FrictionWriteResult:
        """Write an event and never fail because the ledger is down."""

        event = data if isinstance(data, FrictionEvent) else FrictionEvent.from_mapping(data)
        event = event.masked(self.masker)

        if not self.command:
            return self._fallback(event, reason="cpp-memory unavailable")

        argv = [
            *self.command,
            "record",
            "--class",
            "infra_trap",
            "--scope",
            "knowledge",
            "--title",
            event.ledger_title(),
            "--body",
            event.ledger_body(),
            "--confidence",
            "0.8",
            "--harness",
            HARNESS,
        ]

        try:
            proc = self.runner(argv, self.cwd, self.env, self.timeout)
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
            return self._fallback(event, reason=f"cpp-memory failed: {self._safe_error(str(exc))}")

        stdout = self.masker.mask(proc.stdout or "").strip()
        stderr = self.masker.mask(proc.stderr or "").strip()

        if proc.returncode != 0:
            detail = stderr or stdout or f"exit {proc.returncode}"
            return self._fallback(event, reason=f"cpp-memory failed: {self._safe_error(detail)}")

        ledger = self._parse_ledger(stdout)
        if ledger.get("harness") != HARNESS:
            ledger["harness"] = HARNESS

        return FrictionWriteResult(
            ok=True,
            stored=str(ledger.get("stored") or "shared"),
            event=event.public_dict(),
            ledger=ledger,
        )

    def _parse_ledger(self, stdout: str) -> dict[str, object]:
        if not stdout:
            return {"stored": "shared", "harness": HARNESS}
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return {
                "stored": "shared",
                "harness": HARNESS,
                "raw": truncate(stdout, 512),
            }
        return parsed if isinstance(parsed, dict) else {"stored": "shared", "harness": HARNESS}

    def _fallback(self, event: FrictionEvent, *, reason: str) -> FrictionWriteResult:
        local_path = self._append_local(event, reason)
        return FrictionWriteResult(
            ok=True,
            stored="local-buffer" if local_path else "skipped",
            event=event.public_dict(),
            reason=reason,
            local_path=str(local_path) if local_path else None,
        )

    def _append_local(self, event: FrictionEvent, reason: str) -> Path | None:
        if not self.queue_path:
            return None

        record = {
            "created_at": utc_now(),
            "event_type": "ledger_write_failure",
            "harness": HARNESS,
            "reason": self._safe_error(reason),
            "event": event.public_dict(),
        }
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))

        try:
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.queue_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            return None
        return self.queue_path

    def _safe_error(self, value: str) -> str:
        return truncate(self.masker.mask(value).replace("\n", " "), 512)


def write_event(data: Mapping[str, Any] | FrictionEvent, **kwargs: Any) -> FrictionWriteResult:
    """Convenience wrapper around :class:`FrictionWriter`."""

    return FrictionWriter(**kwargs).write(data)


def reject_event(data: Mapping[str, Any]) -> FrictionWriteResult:
    """Return a structured rejection for CLI callers."""

    try:
        FrictionEvent.from_mapping(data)
    except FrictionEventError as exc:
        return FrictionWriteResult(ok=False, stored="rejected", reason=str(exc))
    return FrictionWriteResult(ok=False, stored="rejected", reason="event was not rejected")
