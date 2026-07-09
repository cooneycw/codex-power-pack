"""Tests for the Codex friction telemetry writer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

import pytest

from lib.creds.masking import OutputMasker
from lib.friction.hooks import event_from_hook_payload
from lib.friction.models import FrictionEvent, FrictionEventError
from lib.friction.writer import FrictionWriter


class FakeRunner:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = '{"stored":"shared","harness":"codex","fingerprint":"cpp-fp"}',
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[Sequence[str]] = []
        self.env: Mapping[str, str] | None = None

    def __call__(
        self,
        argv: Sequence[str],
        cwd: Path | None,
        env: Mapping[str, str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        self.env = dict(env)
        return subprocess.CompletedProcess(list(argv), self.returncode, self.stdout, self.stderr)


def _event(summary: str = "psql failed with password=supersecret") -> dict[str, object]:
    return {
        "event_type": "command_failure",
        "event_source": "hook:PostToolUse:Bash",
        "severity": "warning",
        "repo": "cooneycw/codex-power-pack",
        "branch": "issue-95-test",
        "issue": 95,
        "summary": summary,
    }


def test_writer_masks_event_before_cpp_memory_call() -> None:
    runner = FakeRunner()
    writer = FrictionWriter(command=["cpp-memory"], runner=runner, env={})

    result = writer.write(_event())

    assert result.ok is True
    assert result.stored == "shared"
    assert runner.env is not None
    assert runner.env["CPP_HARNESS"] == "codex"
    argv_text = "\n".join(runner.calls[0])
    assert "supersecret" not in argv_text
    assert "password=****" in argv_text
    assert "--harness" in runner.calls[0]
    assert "codex" in runner.calls[0]


def test_writer_overrides_caller_harness() -> None:
    runner = FakeRunner(stdout='{"stored":"shared","harness":"claude"}')
    writer = FrictionWriter(command=["cpp-memory"], runner=runner, env={})

    result = writer.write({**_event(), "harness": "claude"})

    assert result.event is not None
    assert result.event["harness"] == "codex"
    assert result.ledger is not None
    assert result.ledger["harness"] == "codex"


def test_forbidden_raw_fields_are_rejected() -> None:
    with pytest.raises(FrictionEventError, match="forbidden event field"):
        FrictionEvent.from_mapping({
            "event_type": "command_failure",
            "summary": "bad",
            "tool_output": "raw password=supersecret",
        })


def test_oversized_summary_is_truncated_after_masking() -> None:
    runner = FakeRunner()
    writer = FrictionWriter(command=["cpp-memory"], runner=runner, env={})
    long_secret = "password=supersecret " + "x" * 800

    result = writer.write(_event(long_secret))

    assert result.event is not None
    summary = str(result.event["summary"])
    assert len(summary) <= 512
    assert "supersecret" not in summary
    assert "..." in summary


def test_ledger_down_fails_open_and_writes_masked_local_buffer(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=1, stderr="dial postgres://user:secret@db/internal failed")
    queue = tmp_path / "friction-failures.jsonl"
    writer = FrictionWriter(command=["cpp-memory"], runner=runner, queue_path=queue, env={})

    result = writer.write(_event())

    assert result.ok is True
    assert result.stored == "local-buffer"
    assert result.local_path == str(queue)
    line = queue.read_text().strip()
    assert "supersecret" not in line
    assert "secret@db" not in line
    assert "postgres://user:****@db" in line
    record = json.loads(line)
    assert record["event_type"] == "ledger_write_failure"
    assert record["harness"] == "codex"


def test_missing_cpp_memory_is_skipped_without_error(tmp_path: Path) -> None:
    writer = FrictionWriter(command=["definitely-not-cpp-memory"], queue_path=tmp_path / "q.jsonl", env={})
    # Simulate post-resolution failure from the OS path, not test process PATH.
    writer.command = None

    result = writer.write(_event())

    assert result.ok is True
    assert result.stored == "local-buffer"


def test_permission_hook_extracts_minimized_event() -> None:
    event = event_from_hook_payload(
        "PermissionRequest",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo password=supersecret"},
            "repo": "cooneycw/codex-power-pack",
            "branch": "issue-95-test",
        },
    )

    assert event is not None
    masked = event.masked(OutputMasker())
    assert masked.event_type == "approval_prompt"
    assert masked.summary == "Permission requested for Bash"
    assert "supersecret" not in json.dumps(masked.public_dict())


def test_post_tool_secret_hit_does_not_copy_raw_output() -> None:
    event = event_from_hook_payload(
        "PostToolUse",
        {
            "tool_name": "Bash",
            "tool_output": "connecting with postgresql://user:secretpass@db/app",
        },
    )

    assert event is not None
    assert event.event_type == "secret_mask_hit"
    assert "secretpass" not in event.summary
