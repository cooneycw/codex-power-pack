"""Unit tests for scripts/skills_install_codex.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills_install_codex import (  # type: ignore[import-not-found]  # noqa: E402
    _install_one,
    discover_repo_skills,
    inspect_target,
)


def _write_skill(root: Path, name: str, body: str = "name: test\n") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def test_discover_repo_skills_filters_to_directories_with_skill_md(tmp_path: Path) -> None:
    skills_root = tmp_path / ".codex" / "skills"
    _write_skill(skills_root, "flow-help")
    (skills_root / "not-a-skill").mkdir(parents=True, exist_ok=True)

    discovered = discover_repo_skills(skills_root)
    assert [path.name for path in discovered] == ["flow-help"]


def test_install_one_creates_symlink_for_missing_target(tmp_path: Path) -> None:
    source = _write_skill(tmp_path / "repo", "flow-help")
    target = tmp_path / "codex" / "skills" / "flow-help"

    result = _install_one(source, target, overwrite=False, dry_run=False)
    assert result.status == "installed"
    assert target.is_symlink()
    assert target.resolve() == source.resolve()


def test_install_one_reports_conflict_without_overwrite(tmp_path: Path) -> None:
    source = _write_skill(tmp_path / "repo", "flow-help", body="source\n")
    target = _write_skill(tmp_path / "codex" / "skills", "flow-help", body="different\n")

    result = _install_one(source, target, overwrite=False, dry_run=False)
    assert result.status == "conflict"
    assert target.is_dir()


def test_install_one_replaces_conflict_with_overwrite(tmp_path: Path) -> None:
    source = _write_skill(tmp_path / "repo", "flow-help", body="source\n")
    target = _write_skill(tmp_path / "codex" / "skills", "flow-help", body="different\n")

    result = _install_one(source, target, overwrite=True, dry_run=False)
    assert result.status == "replaced"
    assert target.is_symlink()
    assert target.resolve() == source.resolve()

    backups = list((tmp_path / "codex" / "skills").glob("flow-help.bak.*"))
    assert backups


def test_inspect_target_reports_copied_for_matching_directory(tmp_path: Path) -> None:
    source = _write_skill(tmp_path / "repo", "flow-help", body="same\n")
    target = _write_skill(tmp_path / "codex" / "skills", "flow-help", body="same\n")

    status = inspect_target(source, target)
    assert status.status == "copied"
