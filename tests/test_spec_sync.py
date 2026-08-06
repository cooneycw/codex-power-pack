"""Behavioral contract for the sole Spec Kit issue compiler."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / ".codex"
    / "skills"
    / "spec-sync"
    / "scripts"
    / "spec_sync.py"
)
_spec = importlib.util.spec_from_file_location("spec_sync", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
spec_sync = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = spec_sync
_spec.loader.exec_module(spec_sync)


def write_artifacts(root: Path, tasks_text: str) -> Path:
    feature = root / ".specify" / "specs" / "feature"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("# Spec\n\nApproved behavior.\n")
    (feature / "plan.md").write_text("# Plan\n\nImplementation plan.\n")
    tasks = feature / "tasks.md"
    tasks.write_text(tasks_text)
    return tasks


VALID_TASKS = """# Tasks

## Stage 1: Foundation

- [ ] **T001** [US1] Implement the parser in `src/parser.py`.
- [ ] **T002** [US1] Add independent coverage in `tests/test_parser.py`; depends on T001.

**Checkpoint:** Parser behavior and its focused tests pass independently.
"""


def test_canonical_tasks_group_by_independently_mergeable_stage(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)

    tasks, checkpoints = spec_sync.parse_tasks(path)
    groups = spec_sync.group_tasks(tasks, checkpoints)
    spec_sync.validate_groups(tasks, groups)

    assert [task.task_id for task in tasks] == ["T001", "T002"]
    assert tasks[1].dependencies == ("T001",)
    assert len(groups) == 1
    assert groups[0].group_id == "stage-1"
    assert groups[0].checkpoint.startswith("Parser behavior")


def test_malformed_or_unparsed_task_input_fails_loudly(tmp_path: Path) -> None:
    malformed = write_artifacts(tmp_path, "- [ ] T01 broken syntax\n")
    with pytest.raises(spec_sync.ReadinessError, match="malformed task-like line"):
        spec_sync.parse_tasks(malformed)

    malformed.write_text("# Tasks\n\nThis file contains prose but no tasks.\n")
    with pytest.raises(spec_sync.ReadinessError, match="yielded zero canonical"):
        spec_sync.parse_tasks(malformed)


def test_automatic_grouping_refuses_ambiguous_boundaries(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, "- [ ] **T001** Implement `src/a.py`.\n")
    tasks, checkpoints = spec_sync.parse_tasks(path)

    with pytest.raises(spec_sync.ReadinessError, match="automatic grouping is ambiguous"):
        spec_sync.group_tasks(tasks, checkpoints)

    groups = spec_sync.group_tasks(tasks, checkpoints, "task")
    assert groups[0].group_id == "task-t001"


def test_readiness_rejects_placeholders_missing_paths_and_cycles(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    (path.parent / "spec.md").write_text("# Spec\n\nTODO\n")

    def runner(command: list[str], cwd: Path) -> str:
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return str(tmp_path)
        if command[:2] == ["git", "rev-parse"]:
            return "a" * 40
        if command[:3] == ["git", "cat-file", "-e"]:
            return ""
        raise AssertionError(command)

    with pytest.raises(spec_sync.ReadinessError, match="unresolved placeholder"):
        spec_sync.validate_artifacts(path, "HEAD", True, runner)

    path.write_text(
        VALID_TASKS.replace("`src/parser.py`", "the parser").replace(
            "depends on T001", "depends on T001 and blocked by T002"
        )
    )
    tasks, checkpoints = spec_sync.parse_tasks(path)
    groups = spec_sync.group_tasks(tasks, checkpoints)
    with pytest.raises(spec_sync.ReadinessError, match="cyclic task dependencies|lack exact paths"):
        spec_sync.validate_groups(tasks, groups)


def test_rich_body_and_ledger_preserve_stable_identity(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    tasks, checkpoints = spec_sync.parse_tasks(path)
    groups = spec_sync.group_tasks(tasks, checkpoints)
    body = spec_sync.render_issue_body(
        groups[0],
        "example/repo",
        ".specify/specs/feature/tasks.md",
        "a" * 40,
        {},
        groups,
    )

    for heading in (
        "## Outcome",
        "## Tasks",
        "## User-story traceability",
        "## Acceptance checkpoint",
        "## Dependencies",
        "## Constraints and non-goals",
        "## Quality commands",
        "## Immutable artifacts",
        "## Mapping write-back",
    ):
        assert heading in body
    identity = "spec-sync:v1:example/repo:.specify/specs/feature/tasks.md:stage-1"
    assert f"<!-- {identity} -->" in body

    mapping = spec_sync.Mapping(identity, "stage", "stage-1", 42, "https://github.com/example/repo/issues/42", "OPEN")
    spec_sync.update_ledger(path, [mapping])
    spec_sync.update_ledger(path, [mapping])
    assert path.read_text().count(spec_sync.LEDGER_START) == 1
    assert "| #42 |" in path.read_text()


def test_dry_run_is_read_only_and_existing_closed_identity_is_idempotent(tmp_path: Path) -> None:
    tasks_path = write_artifacts(tmp_path, VALID_TASKS)
    original = tasks_path.read_text()
    commit = "b" * 40
    identity = "spec-sync:v1:example/repo:.specify/specs/feature/tasks.md:stage-1"
    existing = json.dumps(
        [
            {
                "number": 99,
                "title": "Old title",
                "body": f"<!-- {identity} -->",
                "state": "CLOSED",
                "url": "https://github.com/example/repo/issues/99",
            }
        ]
    )

    def runner(command: list[str], cwd: Path) -> str:
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return str(tmp_path)
        if command[:2] == ["git", "rev-parse"]:
            return commit
        if command[:3] == ["git", "cat-file", "-e"]:
            return ""
        if command[:3] == ["gh", "issue", "list"]:
            return existing
        raise AssertionError(command)

    args = argparse.Namespace(
        tasks=str(tasks_path),
        repo="example/repo",
        artifact_commit="HEAD",
        granularity="auto",
        analysis_clean=True,
        dry_run=True,
        approve=False,
        json=False,
    )
    result = spec_sync.synchronize(args, runner)

    assert result["actions"] == [{"action": "skip", "group": "stage-1", "issue": 99, "state": "CLOSED"}]
    assert tasks_path.read_text() == original
