"""End-to-end contract for the native project scaffold (#99)."""

import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".codex" / "skills" / "project-init" / "scripts" / "project-scaffold.py"


def test_scaffold_creates_codex_project_and_initial_commit(tmp_path: Path) -> None:
    if which("git") is None:
        pytest.skip("the CI validate image intentionally has no Git executable")
    target = tmp_path / "demo-project"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "demo-project",
            "--path",
            str(target),
            "--git",
            "--initial-commit",
            "--author-name",
            "Codex Test",
            "--author-email",
            "codex-test@example.test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for path in [
        "AGENTS.md",
        "Makefile",
        ".codex/cicd.yml",
        ".github/workflows/ci.yml",
        "pyproject.toml",
        "src/demo_project/__init__.py",
        "tests/test_demo_project.py",
    ]:
        assert (target / path).is_file(), path

    workflow = (target / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert workflow.index("name: gitleaks") < workflow.index("uv sync --extra dev")

    commit = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=target, capture_output=True, text=True, check=True
    )
    assert commit.stdout.strip() == "Initial Codex project scaffold"


def test_scaffold_rejects_partial_commit_identity(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "bad-project", "--path", str(tmp_path / "bad"), "--author-name", "Only Name"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must be provided together" in result.stderr
