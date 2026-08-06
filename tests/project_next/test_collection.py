from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.project_next.collect import CollectionError, collect_repository
from lib.project_next.config import ProjectNextConfig


def test_collector_maps_git_github_and_worktree_state(tmp_path: Path) -> None:
    worktree_output = f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"
    outputs = {
        ("git", "rev-parse", "--show-toplevel"): str(tmp_path),
        ("gh", "repo", "view"): json.dumps({"nameWithOwner": "example/repo", "defaultBranchRef": {"name": "main"}}),
        ("gh", "issue", "list"): json.dumps(
            [
                {
                    "number": 1,
                    "title": "Task",
                    "body": "",
                    "labels": [{"name": "p1"}],
                    "assignees": [{"login": "maintainer"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-02T00:00:00Z",
                    "url": "https://example.test/1",
                }
            ]
        ),
        ("gh", "pr", "list"): json.dumps(
            [
                {
                    "number": 2,
                    "title": "Task",
                    "body": "Closes #1",
                    "headRefName": "issue-1-task",
                    "closingIssuesReferences": [{"number": 1}],
                    "isDraft": False,
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "APPROVED",
                    "statusCheckRollup": [{"conclusion": "SUCCESS"}],
                    "url": "https://example.test/pr/2",
                }
            ]
        ),
        ("git", "fetch", "origin"): "",
        ("git", "worktree", "list"): worktree_output,
        ("git", "status", "--short"): "",
        ("git", "log", "--oneline"): "abc current",
        ("git", "branch", "-a"): "main origin/main\nissue-1-task origin/issue-1-task\n",
    }

    def runner(command: list[str], cwd: Path) -> str:
        for prefix, output in outputs.items():
            if tuple(command[: len(prefix)]) == prefix:
                return output
        raise AssertionError(command)

    state = collect_repository(tmp_path, runner=runner)

    assert state.repository == "example/repo"
    assert state.inventory_complete is True
    assert state.issues[0].labels == ("p1",)
    assert state.pull_requests[0].checks_state == "success"
    assert state.worktrees[0].dirty is False
    assert {branch.name for branch in state.branches} == {"main", "issue-1-task"}


def test_collector_marks_truncated_inventory_incomplete(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> str:
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return str(tmp_path)
        if command[:3] == ["gh", "repo", "view"]:
            return json.dumps({"nameWithOwner": "example/repo", "defaultBranchRef": {"name": "main"}})
        if command[:3] == ["gh", "issue", "list"]:
            return json.dumps([{"number": 1, "title": "One"}, {"number": 2, "title": "Two"}])
        if command[:3] == ["gh", "pr", "list"]:
            return "[]"
        if command[:3] == ["git", "worktree", "list"]:
            return ""
        if command[:3] == ["git", "branch", "-a"] or command[:3] == ["git", "fetch", "origin"]:
            return ""
        raise AssertionError(command)

    state = collect_repository(tmp_path, ProjectNextConfig(issue_limit=1), runner)

    assert state.inventory_complete is False
    assert len(state.issues) == 1
    assert "truncated" in state.collector_warnings[0]


def test_collector_stops_when_repository_cannot_be_resolved(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> str:
        raise CollectionError("not a repository")

    with pytest.raises(CollectionError, match="cannot resolve git repository"):
        collect_repository(tmp_path, runner=runner)
