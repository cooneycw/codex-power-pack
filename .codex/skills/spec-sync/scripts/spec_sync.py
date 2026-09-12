#!/usr/bin/env python3
"""Compile approved GitHub Spec Kit artifacts into actionable Flow issues."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

_context_spec = importlib.util.spec_from_file_location("spec_context", Path(__file__).with_name("spec_context.py"))
assert _context_spec is not None and _context_spec.loader is not None
context = importlib.util.module_from_spec(_context_spec)
_context_spec.loader.exec_module(context)

TASK = re.compile(r"^-\s*\[(?P<done>[ xX])\]\s+(?:\*\*)?(?P<id>T\d{3})(?:\*\*)?\s+(?P<body>.+)$")
TASK_LIKE = re.compile(r"^-\s*\[[^]]*\].*\bT\d+\b", re.IGNORECASE)
STAGE = re.compile(r"^#{2,}\s+(?P<kind>Stage|Wave|Phase)\s+(?P<id>\d+)(?:\s*:\s*(?P<title>.+))?$", re.I)
STORY_HEADING = re.compile(r"^(?P<level>#{2,})\s+(?:US|User\s+Story\s+)(?P<id>\d+)(?:\s*[:\-].*|\s*)$", re.I)
STORY = re.compile(r"\[US(?P<id>\d+)\]", re.I)
DEPENDENCY = re.compile(r"\b(?:depends\s+on|blocked\s+by|requires|after)\s+(?P<id>T\d{3})\b", re.I)
CHECKPOINT = re.compile(r"^\*\*Checkpoint:\*\*\s*(?P<body>.+)$", re.I)
PATH_TOKEN = re.compile(r"`(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.*/-]+)`")
PLACEHOLDER = re.compile(r"\[NEEDS CLARIFICATION[^]]*\]|\b(?:TODO|TBD)\b|<placeholder>", re.I)
LEDGER_START = "<!-- spec-sync-ledger:start -->"
LEDGER_END = "<!-- spec-sync-ledger:end -->"
IDENTITY_PREFIX = "spec-sync:v1"
DEPENDENCIES_END = "<!-- spec-sync-dependencies:end -->"
MANAGED_DEPENDENCIES = re.compile(
    ("<!-- spec-sync-dependencies:start sha256=([0-9a-f]{64}) -->\\n(.*?)\\n<!-- spec-sync-dependencies:end -->"), re.S
)
IDENTITY_MARKER = re.compile(r"<!--\s*(spec-sync:v1:[^>\r\n]+?)\s*-->")
ISSUE_LIMIT = 1000


ReadinessError = context.ContextError


Runner = Callable[[list[str], Path], str]


def subprocess_runner(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode:
        message = (completed.stderr or completed.stdout or "command failed").strip().splitlines()[0]
        raise RuntimeError(f"{' '.join(command[:3])}: {message}")
    return completed.stdout.strip()


@dataclass(frozen=True)
class Task:
    task_id: str
    description: str
    line: int
    stage_id: str | None
    stage_title: str | None
    story_ids: tuple[str, ...]
    dependencies: tuple[str, ...]
    paths: tuple[str, ...]


@dataclass
class Group:
    group_id: str
    title: str
    granularity: str
    tasks: list[Task] = field(default_factory=list)
    checkpoint: str = ""

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks)


@dataclass(frozen=True)
class Mapping:
    identity: str
    granularity: str
    group_id: str
    issue_number: int
    url: str
    state: str
    task_ids: tuple[str, ...] = ()


def _strip_tags(text: str) -> str:
    return re.sub(r"\[(?:P|US\d+)\]", "", text, flags=re.I).strip()


def parse_tasks(path: Path, source: str | None = None) -> tuple[list[Task], dict[str, str]]:
    lines = (path.read_bytes().decode("utf-8") if source is None else source).splitlines()
    if not any(line.strip() for line in lines):
        raise ReadinessError(f"{path}: task file is empty")

    tasks: list[Task] = []
    checkpoints: dict[str, str] = {}
    current_stage: tuple[str, str] | None = None
    current_story: str | None = None
    stage_level = story_level = 0
    seen_headings: set[str] = set()
    story_heading_tasks: dict[str, set[str]] = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        heading = re.match(r"^(#{1,6})\s", line)
        if heading:
            level = len(heading.group(1))
            if level <= story_level:
                current_story, story_level = None, 0
            if level <= stage_level:
                current_stage, stage_level = None, 0
        stage = STAGE.match(line)
        story = STORY_HEADING.match(line)
        if stage or story:
            key = f"{stage.group('kind').casefold()}-{stage.group('id')}" if stage else f"us-{story.group('id')}"
            if key in seen_headings:
                raise ReadinessError(f"{path}:{number}: repeated checkpoint owner {key}")
            seen_headings.add(key)
            if stage:
                current_stage = (key, (stage.group("title") or key.replace("-", " ").title()).strip())
                stage_level = len(heading.group(1))
                current_story, story_level = None, 0
            else:
                current_story, story_level = key, len(story.group("level"))
                story_heading_tasks[key] = set()
            continue
        checkpoint = CHECKPOINT.match(line)
        if checkpoint:
            owner = current_story or (current_stage[0] if current_stage else None)
            if not owner:
                raise ReadinessError(f"{path}:{number}: checkpoint has no stage/story owner")
            value = checkpoint.group("body").strip()
            if owner in checkpoints and checkpoints[owner] != value:
                raise ReadinessError(f"{path}:{number}: conflicting checkpoints for {owner}")
            checkpoints[owner] = value
            continue
        match = TASK.match(line)
        if not match:
            if TASK_LIKE.match(line):
                raise ReadinessError(f"{path}:{number}: malformed task-like line: {line}")
            continue
        description = _strip_tags(match.group("body"))
        if not description:
            raise ReadinessError(f"{path}:{number}: {match.group('id')} has no description")
        story_ids = tuple(sorted({f"us-{item.group('id')}" for item in STORY.finditer(match.group("body"))}))
        if current_story:
            if story_ids and story_ids != (current_story,):
                raise ReadinessError(f"{path}:{number}: story tags conflict with heading {current_story}")
            story_ids = (current_story,)
            story_heading_tasks[current_story].add(match.group("id"))
        tasks.append(
            Task(
                task_id=match.group("id"),
                description=description,
                line=number,
                stage_id=current_stage[0] if current_stage else None,
                stage_title=current_stage[1] if current_stage else None,
                story_ids=story_ids,
                dependencies=tuple(sorted({item.group("id").upper() for item in DEPENDENCY.finditer(description)})),
                paths=tuple(item.group("path") for item in PATH_TOKEN.finditer(description)),
            )
        )
    for story_id, owned_tasks in story_heading_tasks.items():
        selected_ids = {task.task_id for task in tasks if story_id in task.story_ids}
        if story_id in checkpoints and selected_ids != owned_tasks:
            raise ReadinessError(f"{path}: checkpoint for {story_id} does not cover its complete task set")
    # A stage checkpoint covers a story only when both own the same complete task set.
    for story_id in {story for task in tasks for story in task.story_ids}:
        selected = [task for task in tasks if story_id in task.story_ids]
        stages = {task.stage_id for task in selected}
        if story_id not in checkpoints and len(stages) == 1:
            stage_id = next(iter(stages))
            stage_tasks = [task for task in tasks if task.stage_id == stage_id]
            if (
                stage_id in checkpoints
                and selected == stage_tasks
                and all(task.story_ids == (story_id,) for task in selected)
            ):
                checkpoints[story_id] = checkpoints[stage_id]
    if not tasks:
        raise ReadinessError(f"{path}: non-empty task file yielded zero canonical TNNN tasks")
    ids = [task.task_id for task in tasks]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise ReadinessError(f"{path}: duplicate task identifiers: {', '.join(duplicates)}")
    return tasks, checkpoints


def _cycle_nodes(tasks: Iterable[Task]) -> set[str]:
    graph = {task.task_id: set(task.dependencies) for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            cycles.update(trail[trail.index(node) :])
            return
        if node in visited:
            return
        visiting.add(node)
        trail.append(node)
        for dependency in graph.get(node, set()):
            if dependency in graph:
                visit(dependency, trail)
        trail.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return cycles


def group_tasks(tasks: list[Task], checkpoints: dict[str, str], granularity: str = "auto") -> list[Group]:
    if granularity == "auto":
        granularity = (
            "stage"
            if all(task.stage_id for task in tasks)
            else "story"
            if all(task.story_ids for task in tasks)
            else ""
        )
        if not granularity:
            raise ReadinessError(
                "automatic grouping is ambiguous; add stage/story boundaries or request task granularity"
            )

    groups: dict[str, Group] = {}
    for task in tasks:
        if granularity == "stage":
            if not task.stage_id:
                raise ReadinessError(f"{task.task_id}: stage grouping requested but no stage heading applies")
            keys = [(task.stage_id, task.stage_title or task.stage_id)]
        elif granularity == "story":
            if len(task.story_ids) != 1:
                raise ReadinessError(f"{task.task_id}: story grouping requires exactly one [USN] tag")
            keys = [(task.story_ids[0], task.story_ids[0].upper().replace("-", " "))]
        elif granularity == "task":
            keys = [(f"task-{task.task_id.casefold()}", f"{task.task_id}: {task.description}")]
        else:
            raise ReadinessError(f"unsupported granularity: {granularity}")
        for key, title in keys:
            group = groups.setdefault(key, Group(key, title, granularity))
            group.tasks.append(task)

    for group in groups.values():
        group.checkpoint = checkpoints.get(group.group_id, "")
        if not group.checkpoint and group.granularity == "task":
            group.checkpoint = f"{group.tasks[0].task_id} is complete and the listed quality commands pass."
        if not group.checkpoint:
            raise ReadinessError(f"{group.group_id}: independently runnable acceptance checkpoint is missing")
    return list(groups.values())


def validate_artifacts(
    tasks_path: Path, artifact_commit: str, analysis_clean: bool, runner: Runner
) -> tuple[Path, Path, str]:
    feature_dir = tasks_path.parent
    spec_path = feature_dir / "spec.md"
    plan_path = feature_dir / "plan.md"
    missing = [str(path) for path in (spec_path, plan_path, tasks_path) if not path.is_file()]
    if missing:
        raise ReadinessError(f"missing required artifacts: {', '.join(missing)}")
    if not analysis_clean:
        raise ReadinessError("official consistency analysis has not been confirmed clean")
    for path in (spec_path, plan_path, tasks_path):
        text = path.read_text(encoding="utf-8")
        marker = PLACEHOLDER.search(text)
        if marker:
            raise ReadinessError(f"{path}: unresolved placeholder {marker.group(0)!r}")
    root = Path(runner(["git", "rev-parse", "--show-toplevel"], tasks_path.parent)).resolve()
    commit = runner(["git", "rev-parse", f"{artifact_commit}^{{commit}}"], root)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReadinessError(f"artifact commit did not resolve immutably: {artifact_commit}")
    for path in (spec_path, plan_path, tasks_path):
        relative = path.resolve().relative_to(root).as_posix()
        runner(["git", "cat-file", "-e", f"{commit}:{relative}"], root)
    return spec_path, plan_path, commit


def validate_groups(tasks: list[Task], groups: list[Group]) -> None:
    known = {task.task_id for task in tasks}
    unresolved = sorted({dependency for task in tasks for dependency in task.dependencies if dependency not in known})
    if unresolved:
        raise ReadinessError(f"unresolved task dependencies: {', '.join(unresolved)}")
    cycles = _cycle_nodes(tasks)
    if cycles:
        raise ReadinessError(f"cyclic task dependencies: {', '.join(sorted(cycles))}")
    for group in groups:
        missing_paths = [
            task.task_id
            for task in group.tasks
            if not task.paths and "path discovery" not in task.description.casefold()
        ]
        if missing_paths:
            raise ReadinessError(f"{group.group_id}: tasks lack exact paths: {', '.join(missing_paths)}")


def dependency_order(groups: list[Group]) -> list[Group]:
    task_to_group = {task.task_id: group.group_id for group in groups for task in group.tasks}
    graph = {
        group.group_id: {task_to_group[dep] for task in group.tasks for dep in task.dependencies} - {group.group_id}
        for group in groups
    }
    ordered: list[Group] = []
    remaining = list(groups)
    while remaining:
        ready = next((group for group in remaining if not graph[group.group_id]), None)
        if ready is None:
            raise ReadinessError(f"cyclic group dependencies: {', '.join(group.group_id for group in remaining)}")
        ordered.append(ready)
        remaining.remove(ready)
        for edges in graph.values():
            edges.discard(ready.group_id)
    return ordered


def dependency_text(numbers: list[int], unresolved: list[str]) -> str:
    return (
        "\n".join(
            [
                *(f"- Blocked by #{number}" for number in numbers),
                *(f"- Pending group `{group}`" for group in unresolved),
            ]
        )
        or "No cross-group prerequisites."
    )


def managed_dependencies(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"<!-- spec-sync-dependencies:start sha256={digest} -->\n{content}\n{DEPENDENCIES_END}"


def stable_identity(repository: str, tasks_path: str, group_id: str) -> str:
    return f"{IDENTITY_PREFIX}:{repository}:{tasks_path}:{group_id}"


def _issue_dependencies(
    group: Group, task_to_group: dict[str, str], mappings: dict[str, Mapping]
) -> tuple[list[int], list[str]]:
    issue_numbers: set[int] = set()
    unresolved: set[str] = set()
    for task in group.tasks:
        for dependency in task.dependencies:
            dependency_group = task_to_group[dependency]
            if dependency_group == group.group_id:
                continue
            mapping = mappings.get(dependency_group)
            if mapping:
                issue_numbers.add(mapping.issue_number)
            else:
                unresolved.add(dependency_group)
    return sorted(issue_numbers), sorted(unresolved)


def render_issue_body(
    group: Group,
    repository: str,
    tasks_relative: str,
    commit: str,
    mappings: dict[str, Mapping],
    all_groups: list[Group],
    view: dict[str, Any],
) -> str:
    identity = stable_identity(repository, tasks_relative, group.group_id)
    task_to_group = {task.task_id: item.group_id for item in all_groups for task in item.tasks}
    issue_dependencies, unresolved = _issue_dependencies(group, task_to_group, mappings)
    metadata, visible = context.make_context(view, repository, context_group(group))
    return "\n".join(
        [
            context.pack(metadata, visible),
            "",
            "## Dependencies",
            managed_dependencies(dependency_text(issue_dependencies, unresolved)),
            "",
            "## Quality commands",
            "- `make verify`",
            "",
            "## Mapping write-back",
            f"After synchronization, update the Issue Sync ledger in `{tasks_relative}` for `{group.group_id}`.",
            "",
            f"<!-- {identity} -->",
        ]
    )


def context_group(group: Group) -> dict[str, Any]:
    return dict(
        id=group.group_id,
        granularity=group.granularity,
        task_ids=list(group.task_ids),
        stories=sorted({story for task in group.tasks for story in task.story_ids}),
        task_text="\n".join(f"- [ ] **{task.task_id}** {task.description}" for task in group.tasks),
        checkpoint=group.checkpoint,
        source_lines=[task.line for task in group.tasks],
    )


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    state: str
    url: str
    identity: str | None

    def mapping(self) -> Mapping:
        assert self.identity is not None
        return Mapping(self.identity, "unknown", self.identity.rsplit(":", 1)[-1], self.number, self.url, self.state)


def parse_issue_inventory(output: str) -> list[Issue]:
    if not output.strip():
        raise ReadinessError("blank GitHub issue inventory; cannot establish absence of mappings")
    payload = json.loads(output)
    if not isinstance(payload, list) or len(payload) >= ISSUE_LIMIT:
        raise ReadinessError(
            ("GitHub issue inventory must be a complete list below the lookup limit; narrow/reconcile the inventory")
        )
    issues: list[Issue] = []
    numbers: set[int] = set()
    identities: set[str] = set()
    for item in payload:
        if (
            not isinstance(item, dict)
            or type(item.get("number")) is not int
            or item["number"] <= 0
            or any(not isinstance(item.get(key), str) for key in ("title", "body", "state", "url"))
            or item["state"] not in ("OPEN", "CLOSED")
            or not item["url"]
        ):
            raise ReadinessError("malformed GitHub issue inventory entry")
        markers = IDENTITY_MARKER.findall(item["body"])
        if len(markers) > 1 or len(markers) != len(re.findall(r"<!--\s*spec-sync:v1", item["body"])):
            raise ReadinessError(f"{item['url']}: conflicting or malformed stable identity markers")
        identity = markers[0] if markers else None
        if identity and not re.fullmatch(r"spec-sync:v1:[^:/\s]+/[^:\s]+:[^\r\n]+:[^:\s]+", identity):
            raise ReadinessError(f"{item['url']}: malformed stable identity {identity}")
        if item["number"] in numbers or (identity and identity in identities):
            raise ReadinessError(f"{item['url']}: duplicate issue/identity claim {identity or item['number']}")
        numbers.add(item["number"])
        if identity:
            identities.add(identity)
        issues.append(Issue(item["number"], item["title"], item["body"], item["state"], item["url"], identity))
    return issues


def parse_existing_issues(output: str) -> dict[str, Mapping]:
    return {issue.identity: issue.mapping() for issue in parse_issue_inventory(output) if issue.identity}


def legacy_candidates(group: Group, issues: list[Issue]) -> list[Issue]:
    candidates = []
    for issue in issues:
        if issue.identity:
            continue
        ids = {match.group("id") for line in issue.body.splitlines() if (match := TASK.match(line.strip()))}
        title = re.match(r"^(?:\*\*|\[)?(T\d{3})(?:\*\*|\])?(?:\s|:|$)", issue.title)
        if title:
            ids.add(title.group(1))
        if ids.intersection(group.task_ids):
            candidates.append(issue)
    return candidates


@dataclass(frozen=True)
class DependencySpan:
    prefix: str
    suffix: str
    old: str

    def replace(self, content: str) -> str:
        return self.prefix + managed_dependencies(content) + self.suffix


def dependency_span(issue: Issue, proposed: str, unresolved: list[str]) -> DependencySpan | None:
    """Only marked, unmodified compiler content is eligible for automatic repair."""
    headings = list(re.finditer(r"^## Dependencies[ \t]*$", issue.body, re.M))
    spans = list(MANAGED_DEPENDENCIES.finditer(issue.body))
    marker_count = issue.body.count("<!-- spec-sync-dependencies:")
    if len(headings) > 1 or (marker_count and (marker_count != 2 or len(spans) != 1)):
        raise ReadinessError(f"{issue.url}: ambiguous/custom dependency span; reconcile and re-preview")
    if not headings:
        if not marker_count and proposed == "No cross-group prerequisites." and not unresolved:
            return None
        raise ReadinessError(f"{issue.url}: dependency section missing; reconcile and re-preview")
    start = headings[0].end()
    following = re.search(r"^#{1,2} ", issue.body[start:], re.M)
    end = start + following.start() if following else len(issue.body)
    if not spans:
        if issue.body[start:end].strip() == proposed and not unresolved:
            return None
        raise ReadinessError(
            f"#{issue.number} ({issue.state}) {issue.url}: unmarked legacy dependency section "
            "needs explicit resolution; "
            f"current={issue.body[start:end].strip()!r}; desired={proposed!r}; "
            "review these edges, preserve human edges outside any managed span, and explicitly reconcile the body "
            "(see spec-sync SKILL.md, Legacy resolution). Then re-run --dry-run and --approve; no edges were changed."
        )
    span = spans[0]
    if not (start <= span.start() < span.end() <= end):
        raise ReadinessError(f"{issue.url}: managed dependencies outside their section")
    old = span.group(2)
    if hashlib.sha256(old.encode("utf-8")).hexdigest() != span.group(1):
        raise ReadinessError(f"{issue.url}: custom/changed managed dependency span; reconcile and re-preview")
    # The checksum detects edits, not authorship. Only this explicit managed span is replaced.
    if old != "No cross-group prerequisites." and not re.fullmatch(
        r"- (?:Blocked by #[1-9]\d*|Pending group `[^`\n]+`)(?:\n- (?:Blocked by #[1-9]\d*|Pending group `[^`\n]+`))*",
        old,
    ):
        raise ReadinessError(f"{issue.url}: noncanonical managed dependencies; reconcile and re-preview")
    return DependencySpan(issue.body[: span.start()], issue.body[span.end() :], old)


def render_ledger(mappings: Iterable[Mapping]) -> str:
    rows = [
        LEDGER_START,
        "| Stable identity | Granularity | Group | Tasks | Issue | URL | State |",
        "|---|---|---|---|---:|---|---|",
    ]
    rows.extend(
        f"| `{item.identity}` | {item.granularity} | `{item.group_id}` | "
        f"{', '.join(item.task_ids)} | #{item.issue_number} | {item.url} | {item.state} |"
        for item in sorted(mappings, key=lambda value: value.group_id)
    )
    rows.append(LEDGER_END)
    return "\n".join(rows)


def validate_ledger(text: str) -> None:
    starts, ends = text.count(LEDGER_START), text.count(LEDGER_END)
    if (starts, ends) != (0, 0) and ((starts, ends) != (1, 1) or text.index(LEDGER_START) >= text.index(LEDGER_END)):
        raise ReadinessError("incomplete, duplicate or reversed Issue Sync ledger markers")


def update_ledger(path: Path, mappings: Iterable[Mapping], expected_text: str | bytes | None = None) -> None:
    raw = path.read_bytes()
    expected = expected_text.encode("utf-8") if isinstance(expected_text, str) else expected_text
    if expected is not None and raw != expected:
        raise ReadinessError(f"{path}: task file changed during synchronization; reconcile and re-preview")
    updated = context.ledger_write(raw, render_ledger(mappings).encode("utf-8"))
    if updated == raw:
        return
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(updated)
            stream.flush()
            os.chmod(temporary, path.stat().st_mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class SynchronizationError(RuntimeError):
    """Carries successful operations and a failed/uncertain step for reconciliation."""

    def __init__(self, result: dict[str, Any]):
        self.result = result
        super().__init__(json.dumps(result, sort_keys=True))


def synchronize(args: argparse.Namespace, runner: Runner = subprocess_runner) -> dict[str, Any]:
    if not args.dry_run and not args.approve:
        raise ReadinessError("GitHub and ledger writes require --approve after reviewing the dry-run")
    tasks_path = Path(args.tasks).absolute()
    spec_path, _, commit = validate_artifacts(tasks_path, args.artifact_commit, args.analysis_clean, runner)
    root = Path(runner(["git", "rev-parse", "--show-toplevel"], spec_path.parent)).resolve()
    tasks_relative = tasks_path.relative_to(root).as_posix()
    view = context.snapshot(root, commit, tasks_relative)
    comparison = context.require_matching(view)
    original_tasks = view["local"]["tasks"]
    tasks, checkpoints = parse_tasks(tasks_path, view["raw"]["tasks"].decode("utf-8"))
    groups = group_tasks(tasks, checkpoints, args.granularity)
    validate_groups(tasks, groups)
    ordered = dependency_order(groups)
    source_repository = context.source_repository(root)
    repository = args.repo or source_repository
    if repository != source_repository:
        raise ReadinessError(
            (
                "cross-repository attestation is unsupported: --repo must mat"
                "ch the trusted source checkout repository; no writes perform"
                "ed"
            )
        )
    refresh = getattr(args, "refresh_context", False)
    revision = getattr(args, "revision_reference", None)
    inventory = parse_issue_inventory(
        runner(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repository,
                "--state",
                "all",
                "--limit",
                str(ISSUE_LIMIT),
                "--json",
                "number,title,body,state,url",
            ],
            root,
        )
    )
    by_identity = {issue.identity: issue for issue in inventory if issue.identity}
    selected: dict[str, Issue] = {}
    mappings: dict[str, Mapping] = {}
    for group in groups:
        identity = stable_identity(repository, tasks_relative, group.group_id)
        current = by_identity.get(identity)
        if current:
            selected[group.group_id] = current
            mappings[group.group_id] = Mapping(
                identity, group.granularity, group.group_id, current.number, current.url, current.state, group.task_ids
            )
        elif candidates := legacy_candidates(group, inventory):
            raise ReadinessError(
                f"{identity}: ambiguous unscoped legacy mapping; resolve explicitly: "
                + ", ".join(issue.url for issue in candidates)
            )
    for source in (view["raw"]["tasks"], original_tasks):
        rows = context.ledger_rows(source)
        verified = []
        for row in rows:
            issue = by_identity.get(row["identity"])
            ledger_groups = group_tasks(tasks, checkpoints, row["granularity"])
            owner = next((item for item in ledger_groups if item.group_id == row["group"]), None)
            expected_identity = stable_identity(repository, tasks_relative, row["group"])
            matching_tasks = owner is not None and row["tasks"] == list(owner.task_ids)
            if issue and owner and not matching_tasks:
                # A real source revision can leave a verified historical mapping in
                # the reviewed ledger. Validate its old objects; never guess new ownership.
                old_record = context.unpack(issue.body)
                if old_record and old_record[0]["identity"] == expected_identity:
                    old_data = old_record[0]
                    old_view = context.snapshot(root, old_data["artifact_commit"], tasks_relative)
                    old_metadata, old_text = context.make_context(
                        old_view,
                        repository,
                        old_data["group"],
                        old_data["previous_snapshot"],
                        old_data["observed_revision"],
                        old_data["previous_artifact_commit"],
                    )
                    old_tasks, old_checkpoints = parse_tasks(tasks_path, old_view["raw"]["tasks"].decode("utf-8"))
                    old_groups = group_tasks(old_tasks, old_checkpoints, row["granularity"])
                    old_owner = next((item for item in old_groups if item.group_id == row["group"]), None)
                    matching_tasks = (
                        old_metadata == old_data
                        and old_text == old_record[1]
                        and old_owner is not None
                        and row["tasks"] == list(old_owner.task_ids)
                    )
            if issue and owner and not matching_tasks:
                predecessor = context.unpack(issue.body)
                predecessor_commit = predecessor[0]["previous_artifact_commit"] if predecessor else None
                if predecessor_commit:
                    predecessor_view = context.snapshot(root, predecessor_commit, tasks_relative)
                    predecessor_tasks, predecessor_checkpoints = parse_tasks(
                        tasks_path, predecessor_view["raw"]["tasks"].decode("utf-8")
                    )
                    predecessor_groups = group_tasks(predecessor_tasks, predecessor_checkpoints, row["granularity"])
                    predecessor_owner = next(
                        (item for item in predecessor_groups if item.group_id == row["group"]), None
                    )
                    matching_tasks = predecessor_owner is not None and row["tasks"] == list(predecessor_owner.task_ids)
            if (
                not issue
                or not owner
                or row["identity"] != expected_identity
                or not matching_tasks
                or row["number"] != issue.number
                or row["url"] != issue.url
            ):
                raise ReadinessError(
                    "invalid ledger mapping claim; reconcile against complete issue inventory and selected groups"
                )
            verified.append(
                Mapping(
                    row["identity"],
                    row["granularity"],
                    row["group"],
                    row["number"],
                    row["url"],
                    row["state"],
                    tuple(row["tasks"]),
                )
            )
        if rows and context.ledger_parts(source)[1] != render_ledger(verified).encode("utf-8"):
            raise ReadinessError("ledger does not match deterministic verified mapping output")
    if comparison["comparison"] == "candidate-ledger-successor":
        comparison["comparison"] = "verified-ledger-successor"
    task_to_group = {task.task_id: group.group_id for group in groups for task in group.tasks}
    spans: dict[str, DependencySpan | None] = {}
    preview: list[dict[str, Any]] = []
    contexts: dict[str, str | None] = {}
    # Validate the ENTIRE plan before its first create/edit, including late existing sections.
    for group in ordered:
        identity = stable_identity(repository, tasks_relative, group.group_id)
        numbers, unresolved = _issue_dependencies(group, task_to_group, mappings)
        proposed = dependency_text(numbers, unresolved)
        current = selected.get(group.group_id)
        span = dependency_span(current, proposed, unresolved) if current else None
        spans[group.group_id] = span
        changed = span is not None and (span.old != proposed or bool(unresolved))
        metadata, visible = context.make_context(view, repository, context_group(group))
        desired = context.pack(metadata, visible)
        contexts[group.group_id] = None
        old_context = context.unpack(current.body) if current else None
        if current:
            if old_context:
                previous = old_context[0]
                if (
                    previous["identity"] != identity
                    or previous["source_repository"] != repository
                    or previous["target_repository"] != repository
                    or previous["tasks_path"] != tasks_relative
                ):
                    raise ReadinessError(f"{current.url}: context/issue identity mismatch; reconcile ownership")
                old_view = context.snapshot(root, previous["artifact_commit"], tasks_relative)
                verified_old, verified_text = context.make_context(
                    old_view,
                    repository,
                    previous["group"],
                    previous["previous_snapshot"],
                    previous["observed_revision"],
                    previous["previous_artifact_commit"],
                )
                if verified_old != previous or verified_text != old_context[1]:
                    raise ReadinessError(
                        f"{current.url}: prior context differs from immutable source; reconcile ownership"
                    )
                # Preserve existing revision chain on same-snapshot retries.
                same_metadata, same_visible = context.make_context(
                    view,
                    repository,
                    context_group(group),
                    previous["previous_snapshot"],
                    previous["observed_revision"],
                    previous["previous_artifact_commit"],
                )
                drift = previous != same_metadata or old_context[1] != same_visible
                if drift:
                    if not refresh:
                        raise ReadinessError(
                            f"{current.url}: governing snapshot changed; unresolved synchronization; "
                            "review --refresh-context --dry-run before any dependency/create/ledger mutation"
                        )
                    metadata, visible = context.make_context(
                        view,
                        repository,
                        context_group(group),
                        previous["snapshot"],
                        revision,
                        previous["artifact_commit"],
                    )
                    desired = context.pack(metadata, visible)
                    contexts[group.group_id] = desired
                    changed = True
            elif refresh or changed:
                raise ReadinessError(
                    f"{current.url}: legacy/unattested governing ownership; explicitly reconcile complete body "
                    f"and preserve human decisions before refresh. Proposed replacement:\n{desired}"
                )
            else:
                # Legacy analysis is usable, but cannot be claimed synchronized to this commit.
                raise ReadinessError(
                    f"{current.url}: legacy/unattested governing view cannot establish synchronized source; "
                    "ordinary analysis remains available; explicitly reconcile ownership before compiler refresh"
                )
        preview.append(
            {
                "action": "would-edit" if changed else "skip" if current else "would-create",
                "group": group.group_id,
                "identity": identity,
                "issue": current.number if current else None,
                "state": current.state if current else "NEW",
                "title": current.title if current else f"{group.title}: {group.tasks[0].description}",
                "old_dependencies": span.old if span else proposed if current else None,
                "proposed_dependencies": proposed,
                "unresolved_new_groups": unresolved,
                "proposed_context": desired,
                "old_context": old_context[0]["snapshot"] if old_context else None,
            }
        )
    result: dict[str, Any] = {
        "tasks": tasks_relative,
        "repository": repository,
        "artifact_commit": commit,
        "granularity": groups[0].granularity,
        "groups": len(groups),
        "actions": [],
        "preview": preview,
        "ledger_updated": False,
        "source_repository": source_repository,
        "ledger_evidence": comparison,
    }
    if args.dry_run:
        # Keep the historical skip shape; full identity and dependency detail lives in preview.
        result["actions"] = [
            {"action": "skip", "group": item["group"], "issue": item["issue"], "state": item["state"]}
            if item["action"] == "skip"
            else item
            for item in preview
        ]
        return result
    operation: dict[str, Any] = {}
    try:
        context.recheck(view)
        for group in ordered:
            context.recheck(view)
            identity = stable_identity(repository, tasks_relative, group.group_id)
            current = selected.get(group.group_id)
            if current:
                span = spans[group.group_id]
                numbers, unresolved = _issue_dependencies(group, task_to_group, mappings)
                proposed = dependency_text(numbers, unresolved)
                replacement = contexts[group.group_id]
                if replacement is not None or (span is not None and span.old != proposed):
                    operation = {
                        "action": "check-before-edit",
                        "group": group.group_id,
                        "issue": current.number,
                        "identity": identity,
                        "outcome": "not-written",
                    }
                    observed = json.loads(
                        runner(
                            [
                                "gh",
                                "issue",
                                "view",
                                str(current.number),
                                "--repo",
                                repository,
                                "--json",
                                "number,title,body,state,url",
                            ],
                            root,
                        )
                    )
                    latest = parse_issue_inventory(json.dumps([observed]))[0]
                    if (
                        latest.number != current.number
                        or latest.body != current.body
                        or latest.identity != identity
                        or latest.state != current.state
                    ):
                        raise ReadinessError(f"{current.url}: issue changed before edit; reconcile and re-preview")
                    final_body = current.body
                    if span is not None:
                        final_body = span.replace(proposed)
                    if replacement is not None:
                        final_body = context.replace_context(final_body, replacement)
                    context.recheck(view)
                    operation = {**operation, "action": "edit", "outcome": "uncertain"}
                    runner(
                        [
                            "gh",
                            "issue",
                            "edit",
                            str(current.number),
                            "--repo",
                            repository,
                            "--body",
                            final_body,
                        ],
                        root,
                    )
                    result["actions"].append(
                        {
                            "action": "edited",
                            "group": group.group_id,
                            "issue": current.number,
                            "identity": identity,
                            "old_dependencies": span.old if span else None,
                            "dependencies": proposed,
                        }
                    )
                else:
                    result["actions"].append(
                        {"action": "skip", "group": group.group_id, "issue": current.number, "state": current.state}
                    )
                continue
            body = render_issue_body(group, repository, tasks_relative, commit, mappings, groups, view)
            operation = {"action": "create", "group": group.group_id, "identity": identity, "outcome": "uncertain"}
            url = runner(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    repository,
                    "--title",
                    f"{group.title}: {group.tasks[0].description}",
                    "--body",
                    body,
                ],
                root,
            )
            number_match = re.fullmatch(rf"https://github\.com/{re.escape(repository)}/issues/([1-9]\d*)", url.strip())
            if not number_match:
                raise RuntimeError("cannot determine created issue number; reconcile stable identity before retry")
            mapping = Mapping(
                identity,
                group.granularity,
                group.group_id,
                int(number_match.group(1)),
                url.strip(),
                "OPEN",
                group.task_ids,
            )
            mappings[group.group_id] = mapping
            result["actions"].append(
                {
                    "action": "created",
                    "group": group.group_id,
                    "issue": mapping.issue_number,
                    "url": mapping.url,
                    "identity": identity,
                }
            )
        operation = {"action": "ledger", "outcome": "uncertain"}
        context.recheck(view)
        successor = context.ledger_write(
            original_tasks, render_ledger([mappings[group.group_id] for group in groups]).encode("utf-8")
        )
        update_ledger(tasks_path, [mappings[group.group_id] for group in groups], original_tasks)
        result["ledger_evidence"].update(
            writer_before_sha256=context.sha(original_tasks),
            writer_after_sha256=context.sha(successor),
            deterministic_successor=True,
        )
        result["ledger_updated"] = True
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        result["failed_operation"] = {**operation, "error": str(exc)}
        result["status"] = "incomplete"
        raise SynchronizationError(result) from exc
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, help="selected .specify/specs/<feature>/tasks.md")
    parser.add_argument("--repo", help="explicit OWNER/REPO target; defaults to origin")
    parser.add_argument("--artifact-commit", required=True, help="reviewed immutable artifact commit or ref")
    parser.add_argument("--granularity", choices=("auto", "stage", "story", "task"), default="auto")
    parser.add_argument("--analysis-clean", action="store_true", help="confirm official consistency analysis is clean")
    parser.add_argument("--dry-run", action="store_true", help="preview groups without GitHub or ledger writes")
    parser.add_argument("--approve", action="store_true", help="approve GitHub writes after reviewing dry-run")
    parser.add_argument(
        "--refresh-context",
        action="store_true",
        help="preview/refresh the whole managed governing view under existing approval",
    )
    parser.add_argument("--revision-reference", help="observed existing decision reference; never an approval token")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.dry_run and not args.approve:
        print("spec-sync: use --dry-run first; writes require --approve", file=sys.stderr)
        return 2
    try:
        result = synchronize(args)
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"spec-sync: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Tasks file: {result['tasks']}")
        print(f"Repository: {result['repository']}")
        print(f"Granularity: {result['granularity']} ({result['groups']} group(s))")
        for action in result["preview"] if args.dry_run else result["actions"]:
            print(json.dumps(action, sort_keys=True))
        print(f"Ledger updated: {'yes' if result['ledger_updated'] else 'no (dry-run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
