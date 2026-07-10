"""Regression contract for the locally runnable post-demolition quality gate (#98)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_verify_composes_every_required_local_quality_gate() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    verify = next(line for line in makefile.splitlines() if line.startswith("verify:"))

    assert verify.split()[1:] == [
        "lint",
        "test",
        "typecheck",
        "codex-skills-check",
        "harness-lint",
    ]


def test_drift_and_harness_gates_have_repo_local_implementations() -> None:
    assert (REPO_ROOT / "scripts" / "codex_skills_sync.py").is_file()
    assert (REPO_ROOT / "scripts" / "harness_lint.py").is_file()
