"""Isolated, bounded, and summary-only live Codex evaluation lane."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import BinaryIO

from .models import EvaluationCase, LiveControls, Observation
from .naming import normalize_selected_skill

SECRET_PATTERNS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
SAFE_ENV = {
    "CODEX_HOME",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "NO_PROXY",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TERM",
    "USER",
}


def redact(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted[:500]


def _evaluation_prompt(case: EvaluationCase) -> str:
    checkpoints = ", ".join(case.expectation.required_checkpoints) or "none"
    output_fields = ", ".join(case.expectation.required_output_fields) or "none"
    return f"""{case.prompt}

---
EVALUATION OVERRIDE: The request above is the routing subject only. This is a
read-only skill-routing evaluation. Do not call tools,
change files, contact services, or perform the requested work.

Analyze how you would respond to the original request using the skills visible
in this session. Return only the JSON object required by the output schema.
`selected_skill` is the one skill you would activate, or null when no skill
should activate. Include only checkpoint identifiers that the chosen workflow
requires and only output fields it promises. List any external or mutating
actions it would attempt, but do not perform them. Return the bare skill name
without a plugin namespace or `$` prefix.

Checkpoint identifiers under test: {checkpoints}
Output field identifiers under test: {output_fields}

"""


def _environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in SAFE_ENV}
    env["CODEX_SKILL_EVAL"] = "1"
    return env


def _tokens(events: bytes) -> int | None:
    totals: list[int] = []
    for raw in events.splitlines():
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        usage = event.get("usage") if isinstance(event, dict) else None
        if not isinstance(usage, dict):
            continue
        total = usage.get("total_tokens")
        if isinstance(total, int):
            totals.append(total)
            continue
        parts = [usage.get(key) for key in ("input_tokens", "output_tokens", "reasoning_output_tokens")]
        if any(isinstance(value, int) for value in parts):
            totals.append(sum(value for value in parts if isinstance(value, int)))
    return max(totals) if totals else None


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def _bounded_communicate(
    process: subprocess.Popen[bytes], timeout_seconds: int, max_output_bytes: int
) -> tuple[bytes, bytes, bool, bool]:
    buffers: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    byte_count = 0
    lock = threading.Lock()
    exceeded = threading.Event()

    def read_stream(name: str, stream: BinaryIO) -> None:
        nonlocal byte_count
        while chunk := stream.read(4096):
            with lock:
                remaining = max(0, max_output_bytes - byte_count)
                if remaining:
                    buffers[name].append(chunk[:remaining])
                byte_count += len(chunk)
                if byte_count > max_output_bytes:
                    exceeded.set()
                    return

    assert process.stdout is not None and process.stderr is not None
    threads = [
        threading.Thread(target=read_stream, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=read_stream, args=("stderr", process.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    while process.poll() is None and not exceeded.is_set():
        if time.monotonic() >= deadline:
            timed_out = True
            break
        time.sleep(0.02)
    if timed_out or exceeded.is_set():
        _terminate(process)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _terminate(process)
        process.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=1)
    return b"".join(buffers["stdout"]), b"".join(buffers["stderr"]), timed_out, exceeded.is_set()


def _safe_items(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(redact(str(item))[:64] for item in value[:32])


def _explicit_unavailable(case: EvaluationCase, selected: str | None) -> bool:
    return "explicit" in case.tags and case.expectation.selected_skill is not None and selected is None


def run_case(
    case: EvaluationCase,
    controls: LiveControls,
    output_schema: Path,
    skill_families: dict[str, str],
    *,
    model: str | None = None,
) -> Observation:
    codex = shutil.which("codex")
    if codex is None:
        return Observation(case_id=case.case_id, available=False, runtime_error="Codex CLI is unavailable")

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cxpp-skill-eval-") as temp_name:
        temp = Path(temp_name)
        final_message = temp / "result.json"
        command = [
            codex,
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--output-schema",
            str(output_schema),
            "--output-last-message",
            str(final_message),
            "-C",
            str(temp),
        ]
        selected_model = model or controls.model
        if selected_model:
            command.extend(["--model", selected_model])
        command.append(_evaluation_prompt(case))
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_environment(),
            start_new_session=True,
        )
        stdout, stderr, timed_out, output_exceeded = _bounded_communicate(
            process, controls.timeout_seconds, controls.max_output_bytes
        )
        if timed_out:
            return Observation(
                case_id=case.case_id,
                timed_out=True,
                latency_ms=int((time.monotonic() - started) * 1000),
                runtime_error=f"live evaluation exceeded {controls.timeout_seconds}s",
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        if output_exceeded:
            return Observation(
                case_id=case.case_id,
                exit_code=process.returncode,
                latency_ms=latency_ms,
                runtime_error=f"Codex event output exceeded {controls.max_output_bytes} bytes",
            )
        if process.returncode != 0:
            return Observation(
                case_id=case.case_id,
                exit_code=process.returncode,
                latency_ms=latency_ms,
                runtime_error=redact(stderr.decode("utf-8", errors="replace")),
            )
        try:
            payload = json.loads(final_message.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return Observation(
                case_id=case.case_id,
                latency_ms=latency_ms,
                runtime_error=f"invalid constrained Codex response: {exc}",
            )

        selected, selected_raw = normalize_selected_skill(
            payload.get("selected_skill"), case.expectation.selected_skill, skill_families
        )
        explicit_unavailable = _explicit_unavailable(case, selected)
        return Observation(
            case_id=case.case_id,
            available=not explicit_unavailable,
            selected_skill=selected,
            selected_skill_raw=redact(selected_raw)[:64] if selected_raw else None,
            checkpoints=_safe_items(payload.get("checkpoints")),
            output_fields=_safe_items(payload.get("output_fields")),
            actions=_safe_items(payload.get("actions")),
            contracts={},
            latency_ms=latency_ms,
            total_tokens=_tokens(stdout),
            runtime_error=(
                "codex exec cannot attach the explicit skill input required by this installed skill"
                if explicit_unavailable
                else None
            ),
            summary=redact(str(payload.get("summary", "bounded live evaluation completed"))),
        )
