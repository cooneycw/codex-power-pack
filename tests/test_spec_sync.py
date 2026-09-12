"""Behavioral contract for the sole Spec Kit issue compiler."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / ".codex" / "skills" / "spec-sync" / "scripts" / "spec_sync.py"
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


class GitHubFixture:
    """Real disposable Git artifacts; every GitHub operation stays in this fixture."""

    def __init__(self, root: Path):
        import subprocess

        self.root = root
        self.issues: list[dict] = []
        self.calls: list[list[str]] = []
        self.mutations: list[tuple[str, int]] = []
        self.lookup: str | None = None
        self.before_view = None
        self.fail: tuple[str, int, bool] | None = None
        self.counts: dict[str, int] = {}
        for command in (
            ["git", "init", "--quiet"],
            ["git", "add", "."],
            [
                "git",
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "--quiet",
                "-m",
                "artifacts",
            ],
        ):
            subprocess.run(command, cwd=root, check=True, capture_output=True)

    def runner(self, command: list[str], cwd: Path) -> str:
        self.calls.append(command)
        if command[0] == "git":
            return spec_sync.subprocess_runner(command, cwd)
        assert command[:2] == ["gh", "issue"], command
        action = command[2]
        self.counts[action] = self.counts.get(action, 0) + 1
        failure = self.fail if self.fail and self.fail[:2] == (action, self.counts[action]) else None
        if failure and not failure[2]:
            raise RuntimeError(f"injected {action} failure")
        if action == "list":
            result = self.lookup if self.lookup is not None else json.dumps(self.issues)
        elif action == "view":
            issue = next(issue for issue in self.issues if issue["number"] == int(command[3]))
            if self.before_view:
                self.before_view(issue)
            result = json.dumps(issue)
        elif action == "create":
            number = max((issue["number"] for issue in self.issues), default=99) + 1
            issue = self.seed(number, command[command.index("--body") + 1], command[command.index("--title") + 1])
            self.mutations.append((action, number))
            result = issue["url"]
        elif action == "edit":
            issue = next(issue for issue in self.issues if issue["number"] == int(command[3]))
            issue["body"] = command[command.index("--body") + 1]
            self.mutations.append((action, issue["number"]))
            result = issue["url"]
        else:
            raise AssertionError(command)
        if failure:
            raise RuntimeError(f"injected {action} response loss")
        return result

    def seed(self, number: int, body: str, title: str = "Stage", state: str = "OPEN") -> dict:
        issue = {
            "number": number,
            "title": title,
            "body": body,
            "state": state,
            "url": f"https://github.com/example/repo/issues/{number}",
        }
        self.issues.append(issue)
        return issue

    def run(self, path: Path, **overrides) -> dict:
        options = {
            "tasks": str(path),
            "repo": "example/repo",
            "artifact_commit": "HEAD",
            "granularity": "auto",
            "analysis_clean": True,
            "dry_run": False,
            "approve": True,
        }
        options.update(overrides)
        return spec_sync.synchronize(argparse.Namespace(**options), self.runner)


def identity_marker(path: Path, root: Path, group: str) -> str:
    return f"<!-- spec-sync:v1:example/repo:{path.relative_to(root).as_posix()}:{group} -->"


def dependency_body(marker: str, dependencies: str, managed: bool = True) -> str:
    content = spec_sync.managed_dependencies(dependencies) if managed else dependencies
    return f"Human preface\n\n## Dependencies\n{content}\n\nHuman-owned tail.\n\n## Notes\nKeep me.\n{marker}"


FORWARD_TASKS = """# Tasks

## Stage 1: Consumer
- [ ] **T001** [US1] Implement `src/consumer.py`; depends on T002.
**Checkpoint:** Consumer passes.

## Stage 2: Provider
- [ ] T002 [US2] Implement `src/provider.py`.
**Checkpoint:** Provider passes.
"""


@pytest.mark.parametrize("state", ["OPEN", "CLOSED"])
@pytest.mark.parametrize("reverse", [False, True])
def test_two_features_reusing_ids_are_isolated_across_reruns(tmp_path: Path, state: str, reverse: bool) -> None:
    first = write_artifacts(tmp_path / "a", VALID_TASKS.replace("**T001**", "T001"))
    second = write_artifacts(tmp_path / "b", VALID_TASKS)
    github = GitHubFixture(tmp_path)
    github.run(first)
    github.run(second)
    github.issues[0]["state"] = state
    if reverse:
        github.issues.reverse()
    github.run(first)
    github.run(second)
    assert github.mutations == [("create", 100), ("create", 101)]
    assert "| #100 |" in first.read_text()
    assert "| #101 |" in second.read_text()
    assert first.read_text().count(spec_sync.LEDGER_START) == 1
    assert f":{first.relative_to(tmp_path)}:stage-1" in first.read_text()


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("structure", ["title", "body"])
def test_unscoped_legacy_task_candidates_require_resolution(tmp_path: Path, count: int, structure: str) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    for number in range(8, 8 + count):
        github.seed(
            number,
            "- [ ] **T001** Old parser" if structure == "body" else "Old body",
            "T001: Old parser" if structure == "title" else "Old group",
            state="CLOSED",
        )
    with pytest.raises(spec_sync.ReadinessError, match="ambiguous unscoped legacy.*issues/8"):
        github.run(path)
    assert github.mutations == []
    github.seed(90, identity_marker(path, tmp_path, "stage-1"))
    assert github.run(path)["actions"][0]["issue"] == 90  # Exact scoped evidence outranks title guesses.
    assert github.mutations == []


def test_incidental_task_mentions_do_not_fabricate_legacy_collisions(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    github.seed(8, "Discussion mentions T001 in another conversation.", "Discuss parsing T001")
    github.run(path)
    assert github.mutations == [("create", 9)]


@pytest.mark.parametrize("conflict", ["identity", "number", "markers", "malformed-marker"])
def test_conflicting_mapping_evidence_fails_before_writes(tmp_path: Path, conflict: str) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    marker = identity_marker(path, tmp_path, "stage-2")
    github.seed(8, marker)
    if conflict == "identity":
        github.seed(9, marker)
    elif conflict == "number":
        github.seed(8, identity_marker(path, tmp_path, "stage-1"))
    elif conflict == "markers":
        github.issues[0]["body"] += "\n" + identity_marker(path, tmp_path, "stage-1")
    else:
        github.issues[0]["body"] = "<!-- spec-sync:v1:broken -->"
    with pytest.raises(spec_sync.ReadinessError, match="duplicate|conflicting|malformed"):
        github.run(path)
    assert github.mutations == []


@pytest.mark.parametrize(
    "lookup",
    ["", " ", "{}", "null", "not-json", "[null]", '[{"number": 1}]', "[" + ",".join("{}" for _ in range(1000)) + "]"],
)
def test_incomplete_or_malformed_inventory_cannot_prove_absence(tmp_path: Path, lookup: str) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    original = path.read_bytes()
    github = GitHubFixture(tmp_path)
    github.lookup = lookup
    with pytest.raises(ValueError):
        github.run(path)
    assert github.mutations == []
    assert path.read_bytes() == original


def test_failed_lookup_remains_fatal(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    github.fail = ("list", 1, False)
    with pytest.raises(RuntimeError, match="injected list failure"):
        github.run(path)
    assert github.mutations == []


@pytest.mark.parametrize("text", ["- [ ] T01 Broken `src/a.py`.\n", "# Tasks\nNonempty prose.\n"])
def test_unparseable_input_fails_before_github_lookup(tmp_path: Path, text: str) -> None:
    path = write_artifacts(tmp_path, text)
    github = GitHubFixture(tmp_path)
    with pytest.raises(spec_sync.ReadinessError, match="malformed task-like|zero canonical"):
        github.run(path)
    assert not any(command[0] == "gh" for command in github.calls)


def test_forward_dependencies_resolve_before_creation_and_ignore_foreign_features(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    github.seed(8, "<!-- spec-sync:v1:example/repo:.specify/specs/foreign/tasks.md:stage-2 -->")
    preview = github.run(path, dry_run=True, approve=False)
    assert [action["group"] for action in preview["preview"]] == ["stage-2", "stage-1"]
    assert preview["preview"][1]["unresolved_new_groups"] == ["stage-2"]
    assert github.mutations == []
    github.run(path)
    provider, consumer = github.issues[1:]
    assert ":stage-2 -->" in provider["body"]
    assert "- Blocked by #9" in consumer["body"]
    assert "#8" not in consumer["body"] and "Pending group" not in consumer["body"]
    github.run(path)
    assert github.mutations == [("create", 9), ("create", 10)]


@pytest.mark.parametrize("state", ["OPEN", "CLOSED"])
def test_dependency_repair_previews_removals_preserves_human_text_and_converges(tmp_path: Path, state: str) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    github.seed(8, "<!-- spec-sync:v1:example/repo:.specify/specs/foreign/tasks.md:stage-2 -->")
    old = dependency_body(identity_marker(path, tmp_path, "stage-1"), "- Blocked by #8")
    old = old.replace("Human-owned tail.", "- Blocked by #777\nHuman-owned tail.\r\nPreserve spacing.  ")
    consumer = github.seed(20, old, state=state)
    original_tasks = path.read_bytes()
    preview = github.run(path, dry_run=True, approve=False)["preview"][1]
    assert preview["action"] == "would-edit" and preview["issue"] == 20 and preview["state"] == state
    assert preview["old_dependencies"] == "- Blocked by #8"
    assert preview["proposed_dependencies"] == "- Pending group `stage-2`"
    assert path.read_bytes() == original_tasks and consumer["body"] == old
    result = github.run(path)
    assert [action["action"] for action in result["actions"]] == ["created", "edited"]
    before_span = spec_sync.MANAGED_DEPENDENCIES.search(old)
    after_span = spec_sync.MANAGED_DEPENDENCIES.search(consumer["body"])
    assert old[: before_span.start()] == consumer["body"][: after_span.start()]
    assert old[before_span.end() :] == consumer["body"][after_span.end() :]
    assert after_span.group(2) == "- Blocked by #21"
    mutations = list(github.mutations)
    github.run(path)
    assert github.mutations == mutations


@pytest.mark.parametrize("section", ["legacy", "custom", "duplicate", "outside", "missing"])
def test_late_group_unsafe_dependency_section_prevents_earlier_creates(tmp_path: Path, section: str) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    marker = identity_marker(path, tmp_path, "stage-1")
    body = dependency_body(marker, "- Blocked by #8", managed=section != "legacy")
    if section == "custom":
        body = body.replace("- Blocked by #8", "- Blocked by #8\n- Blocked by #9")
    elif section == "duplicate":
        body += "\n## Dependencies\nCustom"
    elif section == "outside":
        body = body.replace("## Dependencies", "## Custom") + "\n## Dependencies\nMissing span"
    elif section == "missing":
        body = marker
    github.seed(20, body)
    with pytest.raises(spec_sync.ReadinessError, match="dependency|dependencies"):
        github.run(path)
    assert github.mutations == []


@pytest.mark.parametrize(
    "suffix",
    [
        spec_sync.LEDGER_START,
        spec_sync.LEDGER_END + spec_sync.LEDGER_START,
        spec_sync.LEDGER_START + spec_sync.LEDGER_END + spec_sync.LEDGER_START + spec_sync.LEDGER_END,
    ],
)
def test_invalid_ledger_markers_fail_before_any_external_write(tmp_path: Path, suffix: str) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS + suffix)
    github = GitHubFixture(tmp_path)
    with pytest.raises(spec_sync.ReadinessError, match="ledger markers"):
        github.run(path)
    assert github.mutations == []


def test_task_dag_can_collapse_to_a_group_cycle_but_intragroup_edges_are_valid(tmp_path: Path) -> None:
    text = """## Stage 1: First
- [ ] T001 Implement `src/a.py`; depends on T003.
- [ ] T002 Implement `src/b.py`.
**Checkpoint:** First passes.
## Stage 2: Second
- [ ] T003 Implement `src/c.py`; depends on T002.
**Checkpoint:** Second passes.
"""
    path = write_artifacts(tmp_path, text)
    github = GitHubFixture(tmp_path)
    with pytest.raises(spec_sync.ReadinessError, match="cyclic group dependencies"):
        github.run(path)
    assert github.mutations == []
    path.write_text(VALID_TASKS)  # T002 -> T001 is within one stage, not a group cycle.
    github.run(path)
    assert len(github.mutations) == 1


@pytest.mark.parametrize("edit", [False, True])
def test_direct_synchronize_requires_approval_for_ledger_only_and_edit_only(tmp_path: Path, edit: bool) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    body = dependency_body(
        identity_marker(path, tmp_path, "stage-1"), "- Blocked by #8" if edit else "No cross-group prerequisites."
    )
    github.seed(20, body)
    original = path.read_bytes()
    preview = github.run(path, dry_run=True, approve=False)
    assert preview["preview"][0]["action"] == ("would-edit" if edit else "skip")
    if edit:
        assert preview["preview"][0]["proposed_dependencies"] == "No cross-group prerequisites."
    with pytest.raises(spec_sync.ReadinessError, match="require --approve"):
        github.run(path, approve=False)
    assert github.mutations == [] and path.read_bytes() == original


@pytest.mark.parametrize("change", ["body", "identity", "state"])
def test_changed_target_is_not_overwritten(tmp_path: Path, change: str) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    issue = github.seed(20, dependency_body(identity_marker(path, tmp_path, "stage-1"), "- Blocked by #8"))

    def before_view(item):
        if change == "state":
            item["state"] = "CLOSED"
        elif change == "identity":
            item["body"] = item["body"].replace(":stage-1 -->", ":stage-99 -->")
        else:
            item["body"] += "\nHuman change"

    github.before_view = before_view
    with pytest.raises(spec_sync.SynchronizationError) as error:
        github.run(path)
    assert error.value.result["failed_operation"]["action"] == "check-before-edit"
    assert "re-preview" in str(error.value)
    assert github.mutations == []
    assert "Human change" in issue["body"] if change == "body" else True


@pytest.mark.parametrize("response_loss", [False, True])
def test_partial_create_failure_records_evidence_and_rerun_recovers(tmp_path: Path, response_loss: bool) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    github.fail = ("create", 2, response_loss)
    with pytest.raises(spec_sync.SynchronizationError) as error:
        github.run(path)
    result = error.value.result
    assert result["actions"][0]["action"] == "created"
    assert result["failed_operation"]["group"] == "stage-1"
    assert result["failed_operation"]["outcome"] == "uncertain"
    assert result["ledger_updated"] is False and result["status"] == "incomplete"
    github.fail = None
    github.run(path)
    assert len(github.issues) == 2
    assert github.mutations == [("create", 100), ("create", 101)]
    assert "| #100 |" in path.read_text() and "| #101 |" in path.read_text()


@pytest.mark.parametrize("response_loss", [False, True])
def test_partial_edit_failure_preserves_successes_and_recovers(tmp_path: Path, response_loss: bool) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    consumer = github.seed(20, dependency_body(identity_marker(path, tmp_path, "stage-1"), "- Blocked by #8"))
    github.fail = ("edit", 1, response_loss)
    with pytest.raises(spec_sync.SynchronizationError) as error:
        github.run(path)
    assert error.value.result["actions"][0]["action"] == "created"
    assert error.value.result["failed_operation"]["action"] == "edit"
    assert error.value.result["failed_operation"]["issue"] == 20
    github.fail = None
    github.run(path)
    assert len(github.issues) == 2 and "- Blocked by #21" in consumer["body"]
    assert github.mutations.count(("edit", 20)) == 1


def test_later_edit_failure_reports_earlier_successful_edit(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    for number, group in ((20, "stage-1"), (21, "stage-2")):
        github.seed(number, dependency_body(identity_marker(path, tmp_path, group), "- Blocked by #8"))
    github.fail = ("edit", 2, False)
    with pytest.raises(spec_sync.SynchronizationError) as error:
        github.run(path)
    assert error.value.result["actions"][0]["action"] == "edited"
    assert error.value.result["actions"][0]["issue"] == 21
    github.fail = None
    github.run(path)
    assert github.mutations == [("edit", 21), ("edit", 20)]


def test_ledger_failure_leaves_successful_github_work_recoverable(tmp_path: Path, monkeypatch) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    original = path.read_bytes()
    update = spec_sync.update_ledger

    def fail_replace(source, target):
        raise OSError("injected ledger replacement failure")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_replace)
        with pytest.raises(spec_sync.SynchronizationError) as error:
            github.run(path)
    assert error.value.result["failed_operation"]["action"] == "ledger"
    assert error.value.result["actions"][0]["action"] == "created"
    assert path.read_bytes() == original
    assert sorted(item.name for item in path.parent.iterdir()) == ["plan.md", "spec.md", "tasks.md"]
    assert spec_sync.update_ledger is update
    github.run(path)
    assert github.mutations == [("create", 100)] and "| #100 |" in path.read_text()


@pytest.mark.parametrize("heading", ["## US1: Parser", "## User Story 1 - Parser"])
def test_story_headings_work_through_synchronize(tmp_path: Path, heading: str) -> None:
    text = f"""{heading}
- [ ] T001 [US1] Implement `src/parser.py`.
**Checkpoint:** Story one passes.
## User Story 2: Coverage
- [ ] **T002** Add `tests/test_parser.py`; depends on T001.
**Checkpoint:** Story two passes.
"""
    path = write_artifacts(tmp_path, text)
    github = GitHubFixture(tmp_path)
    result = github.run(path)
    assert result["granularity"] == "story"
    assert [action["group"] for action in result["actions"]] == ["us-1", "us-2"]
    assert ":us-2 -->" in github.issues[1]["body"] and "- Blocked by #100" in github.issues[1]["body"]
    github.run(path, granularity="story")
    assert len(github.mutations) == 2


def test_exact_single_story_stage_checkpoint_fallback_and_task_mode(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    result = github.run(path, granularity="story")
    assert result["granularity"] == "story" and result["actions"][0]["group"] == "us-1"
    assert "Parser behavior" in github.issues[0]["body"]
    preview = github.run(path, granularity="task", dry_run=True)
    assert [action["group"] for action in preview["actions"]] == ["task-t001", "task-t002"]
    assert preview["actions"][1]["unresolved_new_groups"] == ["task-t001"]


@pytest.mark.parametrize(
    "text",
    [
        VALID_TASKS.replace("**T002** [US1]", "**T002** [US2]"),
        VALID_TASKS.replace("**T002** [US1]", "**T002**"),
        VALID_TASKS + "\n## Stage 2: More\n- [ ] T003 [US1] Add `src/c.py`.\n**Checkpoint:** More passes.\n",
        "## US1: First\n- [ ] T001 [US2] Add `src/a.py`.\n**Checkpoint:** First passes.\n",
        "## US1: First\n- [ ] T001 Add `src/a.py`.\n**Checkpoint:** First passes.\n**Checkpoint:** Different.\n",
        "## US1: First\n- [ ] T001 Add `src/a.py`.\n**Checkpoint:** First passes.\n"
        "## US2: Second\n- [ ] T002 Add `src/b.py`.\n",
        "## US1: First\n- [ ] T001 Add `src/a.py`.\n**Checkpoint:** First passes.\n"
        "## Notes\n- [ ] T002 [US2] Add `src/b.py`.\n**Checkpoint:** Orphan.\n",
    ],
)
def test_story_checkpoint_ambiguity_never_inherits_unrelated_acceptance(tmp_path: Path, text: str) -> None:
    path = write_artifacts(tmp_path, text)
    github = GitHubFixture(tmp_path)
    with pytest.raises(spec_sync.ReadinessError, match="checkpoint|story"):
        github.run(path, granularity="story")
    assert github.mutations == []


@pytest.mark.parametrize("managed_resolution", [False, True])
def test_legacy_resolution_then_rerun_converges_without_claiming_human_edges(
    tmp_path: Path, managed_resolution: bool
) -> None:
    path = write_artifacts(tmp_path, FORWARD_TASKS)
    github = GitHubFixture(tmp_path)
    marker = identity_marker(path, tmp_path, "stage-1")
    consumer = github.seed(20, f"## Dependencies\n- Blocked by #8\n\n## Notes\n{marker}", state="CLOSED")
    if not managed_resolution:
        github.seed(21, identity_marker(path, tmp_path, "stage-2"))
    with pytest.raises(spec_sync.ReadinessError) as error:
        github.run(path, dry_run=True, approve=False)
    message = str(error.value)
    assert "#20 (CLOSED)" in message and "current=" in message and "desired=" in message
    assert "--dry-run and --approve" in message and "explicit resolution" in message
    assert github.mutations == []
    # Explicit maintainer reconciliation, not an automatic compiler adoption.
    if managed_resolution:
        consumer["body"] = dependency_body(marker, "- Pending group `stage-2`")
        consumer["body"] = consumer["body"].replace("Human-owned tail.", "- Blocked by #8\nHuman-owned tail.")
    else:
        consumer["body"] = consumer["body"].replace("- Blocked by #8", "- Blocked by #21")
    github.run(path, dry_run=True, approve=False)
    github.run(path)
    assert "- Blocked by #21" in consumer["body"]
    if managed_resolution:
        assert "- Blocked by #8\nHuman-owned tail." in consumer["body"]
    else:
        assert "spec-sync-dependencies" not in consumer["body"]
        assert github.mutations == []
    mutations = list(github.mutations)
    github.run(path)
    assert github.mutations == mutations


def test_changed_task_file_is_preserved_after_successful_external_edit(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    github.seed(20, dependency_body(identity_marker(path, tmp_path, "stage-1"), "- Blocked by #8"))

    def before_view(issue):
        path.write_text(path.read_text() + "\nLocal author change.\n")

    github.before_view = before_view
    with pytest.raises(spec_sync.SynchronizationError) as error:
        github.run(path)
    assert error.value.result["failed_operation"]["action"] == "ledger"
    assert error.value.result["actions"][0]["action"] == "edited"
    assert "Local author change." in path.read_text()
    assert spec_sync.LEDGER_START not in path.read_text()
    github.before_view = None
    github.run(path)
    assert github.mutations == [("edit", 20)]
    assert "Local author change." in path.read_text() and "| #20 |" in path.read_text()


def test_explicit_story_checkpoint_does_not_cover_tasks_outside_its_heading(tmp_path: Path) -> None:
    path = write_artifacts(
        tmp_path,
        """## US1: First
- [ ] T001 Add `src/a.py`.
**Checkpoint:** First passes.
## Another boundary
- [ ] T002 [US1] Add `src/b.py`.
""",
    )
    github = GitHubFixture(tmp_path)
    with pytest.raises(spec_sync.ReadinessError, match="complete task set"):
        github.run(path, granularity="story")
    assert github.mutations == []


def test_stage_first_grouping_preserves_fields_with_explicit_story_subheadings(tmp_path: Path) -> None:
    path = write_artifacts(
        tmp_path,
        """## Stage 1: Foundation
**Checkpoint:** Entire stage passes.
### US1: First
- [ ] T001 [US1] Add `src/a.py`.
**Checkpoint:** First story passes.
### US2: Second
- [ ] **T002** [US2] Add `src/b.py`; depends on T001.
**Checkpoint:** Second story passes.
""",
    )
    github = GitHubFixture(tmp_path)
    tasks, checkpoints = spec_sync.parse_tasks(path)
    assert tasks[0].stage_id == tasks[1].stage_id == "stage-1"
    assert tasks[1].stage_title == "Foundation" and tasks[1].dependencies == ("T001",)
    assert tasks[0].paths == ("src/a.py",) and tasks[1].story_ids == ("us-2",)
    assert tasks[1].line == 7
    assert checkpoints == {
        "stage-1": "Entire stage passes.",
        "us-1": "First story passes.",
        "us-2": "Second story passes.",
    }
    result = github.run(path)
    assert result["granularity"] == "stage" and result["groups"] == 1
    assert "Entire stage passes." in github.issues[0]["body"]
    stories = github.run(path, granularity="story", dry_run=True)
    assert [action["group"] for action in stories["actions"]] == ["us-1", "us-2"]


def test_unparseable_create_response_is_uncertain_and_recovers_by_identity(tmp_path: Path, monkeypatch) -> None:
    path = write_artifacts(tmp_path, VALID_TASKS)
    github = GitHubFixture(tmp_path)
    original_runner = github.runner

    def lost_number(command, cwd):
        result = original_runner(command, cwd)
        return "" if command[:3] == ["gh", "issue", "create"] else result

    with monkeypatch.context() as patch:
        patch.setattr(github, "runner", lost_number)
        with pytest.raises(spec_sync.SynchronizationError) as error:
            github.run(path)
    assert error.value.result["failed_operation"]["outcome"] == "uncertain"
    assert "stage-1" in error.value.result["failed_operation"]["identity"]
    assert error.value.result["actions"] == []
    github.run(path)
    assert github.mutations == [("create", 100)] and "| #100 |" in path.read_text()


def test_stable_identity_retains_spaces_in_existing_repository_relative_paths(tmp_path: Path) -> None:
    path = write_artifacts(tmp_path / "feature space", VALID_TASKS)
    github = GitHubFixture(tmp_path)
    github.run(path)
    github.run(path)
    assert github.mutations == [("create", 100)]
    expected = f"spec-sync:v1:example/repo:{path.relative_to(tmp_path).as_posix()}:stage-1"
    mappings = spec_sync.parse_existing_issues(json.dumps(github.issues))
    assert mappings[expected].issue_number == 100
