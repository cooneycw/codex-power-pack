"""Isolated project-init through Spec Sync and project-next evaluation fixtures."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "tasks"
SNAPSHOTS = json.loads((FIXTURES.parent / "issue-body-snapshots.json").read_text(encoding="utf-8"))
SCAFFOLD = ROOT / ".codex" / "skills" / "project-init" / "scripts" / "project-scaffold.py"
SPEC_SYNC = ROOT / ".codex" / "skills" / "spec-sync" / "scripts" / "spec_sync.py"
_spec = importlib.util.spec_from_file_location("skill_eval_spec_sync", SPEC_SYNC)
assert _spec is not None and _spec.loader is not None
spec_sync = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = spec_sync
_spec.loader.exec_module(spec_sync)


def test_parser_fixture_matrix_names_parser_failures() -> None:
    tasks, checkpoints = spec_sync.parse_tasks(FIXTURES / "canonical.md")
    assert [task.task_id for task in tasks] == ["T001", "T002"]
    assert spec_sync.group_tasks(tasks, checkpoints)[0].group_id == "stage-1"

    multiline, _ = spec_sync.parse_tasks(FIXTURES / "multiline.md")
    assert [task.task_id for task in multiline] == ["T001", "T002"]
    with pytest.raises(spec_sync.ReadinessError, match="malformed task-like line"):
        spec_sync.parse_tasks(FIXTURES / "malformed.md")
    with pytest.raises(spec_sync.ReadinessError, match="zero canonical"):
        spec_sync.parse_tasks(FIXTURES / "zero.md")


def test_project_handoff_fixtures_keep_consent_boundaries_separate() -> None:
    handoffs = json.loads((FIXTURES.parent / "project-handoffs.json").read_text(encoding="utf-8"))
    assert handoffs["local_default"]["allowed"] == ["local-files"]
    assert "approval" in handoffs["explicit_publication"]["requires"]
    assert handoffs["declined_publication"]["allowed"] == ["local-files"]
    assert "immutable-ref" in handoffs["spec_kit_opt_in"]["requires"]
    assert handoffs["declined_adoption"]["allowed"] == ["local-files"]


def test_stage_story_task_golden_bodies_and_mapping_idempotency(tmp_path: Path) -> None:
    tasks, checkpoints = spec_sync.parse_tasks(FIXTURES / "canonical.md")
    commit = "a" * 40
    for granularity in ("stage", "story", "task"):
        grouping_checkpoints = {**checkpoints, "us-1": "The user story passes independently."}
        groups = spec_sync.group_tasks(tasks, grouping_checkpoints, granularity)
        body = spec_sync.render_issue_body(
            groups[0],
            "example/repo",
            ".specify/specs/demo/tasks.md",
            commit,
            {},
            groups,
        )
        assert body == SNAPSHOTS[granularity]

    ledger = tmp_path / "tasks.md"
    ledger.write_text((FIXTURES / "canonical.md").read_text(encoding="utf-8"), encoding="utf-8")
    mapping = spec_sync.Mapping(
        "spec-sync:v1:example/repo:.specify/specs/demo/tasks.md:stage-1",
        "stage",
        "stage-1",
        42,
        "https://github.com/example/repo/issues/42",
        "CLOSED",
        ("T001", "T002"),
    )
    spec_sync.update_ledger(ledger, [mapping])
    spec_sync.update_ledger(ledger, [mapping])
    assert ledger.read_text(encoding="utf-8").count(spec_sync.LEDGER_START) == 1


def test_scaffold_to_mapping_to_project_next_dry_run_is_local(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    completed = subprocess.run(
        [sys.executable, str(SCAFFOLD), "demo", "--path", str(project)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not (project / ".git").exists()
    assert not (project / ".specify").exists()

    feature = project / ".specify" / "specs" / "demo"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("# Spec\n\nApproved behavior.\n", encoding="utf-8")
    (feature / "plan.md").write_text("# Plan\n\nPinned Spec Kit adoption fixture.\n", encoding="utf-8")
    (project / ".specify" / "spec-kit-version.json").write_text(
        json.dumps(
            {
                "version": "v0.16.0",
                "commit": "5dce710ce099067c7d3f2ef47a37b9a1c300b327",
                "integration": "codex",
            }
        ),
        encoding="utf-8",
    )
    tasks_path = feature / "tasks.md"
    tasks_path.write_text((FIXTURES / "canonical.md").read_text(encoding="utf-8"), encoding="utf-8")
    tasks, checkpoints = spec_sync.parse_tasks(tasks_path)
    groups = spec_sync.group_tasks(tasks, checkpoints)
    before_preview = tasks_path.read_text(encoding="utf-8")

    def preview_runner(command: list[str], cwd: Path) -> str:
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return str(project)
        if command[:2] == ["git", "rev-parse"]:
            return "a" * 40
        if command[:3] == ["git", "cat-file", "-e"]:
            return ""
        if command[:3] == ["gh", "issue", "list"]:
            return "[]"
        raise AssertionError(command)

    preview_args = type(
        "Args",
        (),
        {
            "tasks": str(tasks_path),
            "repo": "example/demo",
            "artifact_commit": "HEAD",
            "granularity": "auto",
            "analysis_clean": True,
            "dry_run": True,
            "approve": False,
        },
    )()
    preview = spec_sync.synchronize(preview_args, preview_runner)
    assert preview["actions"][0]["action"] == "would-create"
    assert tasks_path.read_text(encoding="utf-8") == before_preview
    mapping = spec_sync.Mapping(
        f"spec-sync:v1:example/demo:.specify/specs/demo/tasks.md:{groups[0].group_id}",
        "stage",
        groups[0].group_id,
        7,
        "https://github.com/example/demo/issues/7",
        "OPEN",
        groups[0].task_ids,
    )
    spec_sync.update_ledger(tasks_path, [mapping])

    state = RepositoryState.from_dict(
        {
            "repository": "example/demo",
            "default_branch": "main",
            "issues": [{"number": 7, "title": "Parser", "labels": ["task"]}],
            "spec_tasks": [
                {
                    "task_id": "T001",
                    "title": "Parser",
                    "feature": "demo",
                    "source": ".specify/specs/demo/tasks.md",
                    "issue_numbers": [7],
                    "synchronized": True,
                    "group_id": "stage-1",
                    "stable_identity": mapping.identity,
                    "mapping_status": "mapped",
                    "mapping_state": "OPEN",
                }
            ],
        }
    )
    result = recommend(state)
    assert result.next_startable_issue == 7
    assert result.unsynchronized_spec_tasks == ()


def test_placeholder_and_multiple_feature_directories_are_unambiguous(tmp_path: Path) -> None:
    first = tmp_path / ".specify" / "specs" / "one"
    second = tmp_path / ".specify" / "specs" / "two"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    for directory in (first, second):
        (directory / "spec.md").write_text("# Spec\n\nApproved.\n", encoding="utf-8")
        (directory / "plan.md").write_text("# Plan\n\nApproved.\n", encoding="utf-8")
    (first / "tasks.md").write_text((FIXTURES / "canonical.md").read_text(encoding="utf-8"), encoding="utf-8")
    (second / "tasks.md").write_text((FIXTURES / "placeholder.md").read_text(encoding="utf-8"), encoding="utf-8")

    selected, _ = spec_sync.parse_tasks(first / "tasks.md")
    assert [task.task_id for task in selected] == ["T001", "T002"]

    def runner(command: list[str], cwd: Path) -> str:
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return str(tmp_path)
        if command[:2] == ["git", "rev-parse"]:
            return "a" * 40
        if command[:3] == ["git", "cat-file", "-e"]:
            return ""
        raise AssertionError(command)

    with pytest.raises(spec_sync.ReadinessError, match="unresolved placeholder"):
        spec_sync.validate_artifacts(second / "tasks.md", "HEAD", True, runner)
