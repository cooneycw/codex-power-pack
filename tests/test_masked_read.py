"""Canary tests for repository reads containing credential-shaped fixtures."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from lib.creds.cli import main
from lib.creds.masked_read import read_masked_paths


def _join(*parts: str) -> str:
    return "".join(parts)


def test_masked_read_redacts_database_and_assignment_shapes(tmp_path: Path) -> None:
    database_value = _join("fixture", "-database", "-value")
    assigned_value = _join("fixture", "-assigned", "-value")
    source = tmp_path / "config.txt"
    source.write_text(
        "postgresql://reader:"
        + database_value
        + "@db.invalid/example\n"
        + "password = "
        + assigned_value
        + "\n",
        encoding="utf-8",
    )
    stdout = io.StringIO()

    assert read_masked_paths([source], stdout=stdout) == 0

    output = stdout.getvalue()
    assert database_value not in output
    assert assigned_value not in output
    assert output.count("****") == 2


def test_masked_read_handles_multiple_files_without_raw_values(tmp_path: Path) -> None:
    first_value = _join("first", "-fixture", "-value")
    second_value = _join("second", "-fixture", "-value")
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text(f"api_key={first_value}\n", encoding="utf-8")
    second.write_text(f"auth_token={second_value}\n", encoding="utf-8")
    stdout = io.StringIO()

    assert read_masked_paths([first, second], stdout=stdout) == 0

    output = stdout.getvalue()
    assert first_value not in output
    assert second_value not in output
    assert str(first) in output
    assert str(second) in output


def test_masked_read_fails_closed_for_detection_only_shape(tmp_path: Path) -> None:
    detection_only_value = _join("a1b2c3d4", "e5f60718", "192a3b4c", "5d6e7f80")
    safe_source = tmp_path / "safe.txt"
    source = tmp_path / "opaque.txt"
    safe_source.write_text("public context\n", encoding="utf-8")
    source.write_text(f"opaque={detection_only_value}\n", encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    assert read_masked_paths([safe_source, source], stdout=stdout, stderr=stderr) == 3

    assert stdout.getvalue() == ""
    assert detection_only_value not in stderr.getvalue()
    assert "no content was emitted" in stderr.getvalue()


def test_masked_read_reports_missing_file_without_path_details(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    stderr = io.StringIO()

    assert read_masked_paths([missing], stderr=stderr) == 2

    assert str(missing) not in stderr.getvalue()
    assert "file 1 could not be read" in stderr.getvalue()


def test_masked_read_cli_routes_through_the_safe_reader(
    tmp_path: Path, capsys: Any
) -> None:
    value = _join("cli", "-fixture", "-value")
    source = tmp_path / "cli.txt"
    source.write_text(f"secret={value}\n", encoding="utf-8")

    assert main(["masked-read", str(source)]) == 0

    output = capsys.readouterr()
    assert value not in output.out
    assert "****" in output.out
