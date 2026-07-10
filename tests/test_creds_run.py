"""Regression tests for secret-safe subprocess execution."""

from __future__ import annotations

import sys
from typing import Any

from lib.creds.base import SecretBundle
from lib.creds.run import run_with_secrets


class _DummyProvider:
    name = "dummy"

    def get_bundle(self, project_id: str) -> SecretBundle:
        return SecretBundle(project_id=project_id, secrets={"DUMMY_SECRET": _secret()})


def _secret() -> str:
    """Keep the dummy value out of source scanners while testing exact masking."""
    return "dummy" + "-secret" + "-value"


def test_run_with_secrets_injects_only_into_child_and_masks_stdout(
    monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setattr("lib.creds.run._get_bundle_provider", lambda _: _DummyProvider())

    exit_code = run_with_secrets(
        [sys.executable, "-c", "import os; print(os.environ['DUMMY_SECRET'])"],
        project_id="test-project",
        provider_name="dummy",
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert _secret() not in output.out
    assert "****" in output.out


def test_run_with_secrets_masks_stderr(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr("lib.creds.run._get_bundle_provider", lambda _: _DummyProvider())

    exit_code = run_with_secrets(
        [
            sys.executable,
            "-c",
            "import os, sys; print(os.environ['DUMMY_SECRET'], file=sys.stderr)",
        ],
        project_id="test-project",
        provider_name="dummy",
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert _secret() not in output.err
    assert "****" in output.err


def test_run_with_secrets_handles_non_utf8_child_output(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr("lib.creds.run._get_bundle_provider", lambda _: _DummyProvider())

    exit_code = run_with_secrets(
        [sys.executable, "-c", "import os; os.write(1, b'\\xff\\n')"],
        project_id="test-project",
        provider_name="dummy",
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert "\ufffd" in output.out
