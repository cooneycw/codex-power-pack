#!/usr/bin/env python3
"""Compile approved GitHub Spec Kit artifacts into actionable Flow issues."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

TASK = re.compile(r"^-\s*\[(?P<done>[ xX])\]\s+(?:\*\*)?(?P<id>T\d{3})(?:\*\*)?\s+(?P<body>.+)$")
TASK_LIKE = re.compile(r"^-\s*\[[^]]*\].*\bT\d+\b", re.IGNORECASE)
STAGE = re.compile(r"^#{2,}\s+(?P<kind>Stage|Wave|Phase)\s+(?P<id>\d+)(?:\s*:\s*(?P<title>.+))?$", re.I)
STORY = re.compile(r"\[US(?P<id>\d+)\]", re.I)
DEPENDENCY = re.compile(r"\b(?:depends\s+on|blocked\s+by|requires|after)\s+(?P<id>T\d{3})\b", re.I)
CHECKPOINT = re.compile(r"^\*\*Checkpoint:\*\*\s*(?P<body>.+)$", re.I)
PATH_TOKEN = re.compile(r"`(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.*/-]+)`")
PLACEHOLDER = re.compile(r"\[NEEDS CLARIFICATION[^]]*\]|\b(?:TODO|TBD)\b|<placeholder>", re.I)
LEDGER_START = "<!-- spec-sync-ledger:start -->"
LEDGER_END = "<!-- spec-sync-ledger:end -->"
IDENTITY_PREFIX = "spec-sync:v1"


class ReadinessError(ValueError):
    """Artifacts do not satisfy the issue-compilation contract."""


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


def parse_tasks(path: Path) -> tuple[list[Task], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not any(line.strip() for line in lines):
        raise ReadinessError(f"{path}: task file is empty")

    tasks: list[Task] = []
    checkpoints: dict[str, str] = {}
    current_stage: tuple[str, str] | None = None
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        stage = STAGE.match(line)
        if stage:
            stage_id = f"{stage.group('kind').casefold()}-{stage.group('id')}"
            current_stage = (stage_id, (stage.group("title") or stage_id.replace("-", " ").title()).strip())
            continue
        checkpoint = CHECKPOINT.match(line)
        if checkpoint and current_stage:
            checkpoints[current_stage[0]] = checkpoint.group("body").strip()
            continue
        match = TASK.match(line)
        if not match:
            if TASK_LIKE.match(line):
                raise ReadinessError(f"{path}:{number}: malformed task-like line: {line}")
            continue
        description = _strip_tags(match.group("body"))
        if not description:
            raise ReadinessError(f"{path}:{number}: {match.group('id')} has no description")
        tasks.append(
            Task(
                task_id=match.group("id"),
                description=description,
                line=number,
                stage_id=current_stage[0] if current_stage else None,
                stage_title=current_stage[1] if current_stage else None,
                story_ids=tuple(sorted({f"us-{item.group('id')}" for item in STORY.finditer(match.group("body"))})),
                dependencies=tuple(sorted({item.group("id").upper() for item in DEPENDENCY.finditer(description)})),
                paths=tuple(item.group("path") for item in PATH_TOKEN.finditer(description)),
            )
        )
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
        granularity = "stage" if all(task.stage_id for task in tasks) else "story" if all(task.story_ids for task in tasks) else ""
        if not granularity:
            raise ReadinessError("automatic grouping is ambiguous; add stage/story boundaries or request task granularity")

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


def validate_artifacts(tasks_path: Path, artifact_commit: str, analysis_clean: bool, runner: Runner) -> tuple[Path, Path, str]:
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
        missing_paths = [task.task_id for task in group.tasks if not task.paths and "path discovery" not in task.description.casefold()]
        if missing_paths:
            raise ReadinessError(f"{group.group_id}: tasks lack exact paths: {', '.join(missing_paths)}")


def stable_identity(repository: str, tasks_path: str, group_id: str) -> str:
    return f"{IDENTITY_PREFIX}:{repository}:{tasks_path}:{group_id}"


def _issue_dependencies(group: Group, task_to_group: dict[str, str], mappings: dict[str, Mapping]) -> tuple[list[int], list[str]]:
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
) -> str:
    identity = stable_identity(repository, tasks_relative, group.group_id)
    task_to_group = {task.task_id: item.group_id for item in all_groups for task in item.tasks}
    issue_dependencies, unresolved = _issue_dependencies(group, task_to_group, mappings)
    base = f"https://github.com/{repository}/blob/{commit}/{Path(tasks_relative).parent.as_posix()}"
    task_lines = "\n".join(f"- [ ] **{task.task_id}** {task.description}" for task in group.tasks)
    story_ids = sorted({story for task in group.tasks for story in task.story_ids})
    dependency_lines = [*(f"- Blocked by #{number}" for number in issue_dependencies), *(f"- Pending group `{item}`" for item in unresolved)]
    return "\n".join(
        [
            "## Outcome",
            f"Deliver the independently mergeable **{group.title}** group from the approved Spec Kit artifacts.",
            "",
            "## Tasks",
            task_lines,
            "",
            "## User-story traceability",
            ", ".join(f"`{item.upper()}`" for item in story_ids) if story_ids else "No user-story tag is declared; stage traceability applies.",
            "",
            "## Acceptance checkpoint",
            group.checkpoint,
            "",
            "## Dependencies",
            "\n".join(dependency_lines) if dependency_lines else "No cross-group prerequisites.",
            "",
            "## Constraints and non-goals",
            "Preserve the approved artifact boundary. Do not absorb tasks from another synchronization group.",
            "",
            "## Quality commands",
            "- `make verify`",
            "",
            "## Immutable artifacts",
            f"- [spec.md]({base}/spec.md)",
            f"- [plan.md]({base}/plan.md)",
            f"- [tasks.md]({base}/tasks.md)",
            "",
            "## Mapping write-back",
            f"After synchronization, update the Issue Sync ledger in `{tasks_relative}` for `{group.group_id}`.",
            "",
            f"<!-- {identity} -->",
        ]
    )


def parse_existing_issues(output: str) -> dict[str, Mapping]:
    payload = json.loads(output or "[]")
    mappings: dict[str, Mapping] = {}
    for item in payload:
        body = str(item.get("body") or "")
        match = re.search(r"<!--\s*(spec-sync:v1:[^>]+)\s*-->", body)
        if not match:
            continue
        identity = match.group(1).strip()
        group_id = identity.rsplit(":", 1)[-1]
        mappings[group_id] = Mapping(
            identity=identity,
            granularity="unknown",
            group_id=group_id,
            issue_number=int(item["number"]),
            url=str(item.get("url") or ""),
            state=str(item.get("state") or "UNKNOWN").upper(),
            task_ids=(),
        )
    return mappings


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


def update_ledger(path: Path, mappings: Iterable[Mapping]) -> None:
    text = path.read_text(encoding="utf-8")
    ledger = render_ledger(mappings)
    if LEDGER_START in text or LEDGER_END in text:
        if LEDGER_START not in text or LEDGER_END not in text:
            raise ReadinessError(f"{path}: incomplete Issue Sync ledger markers")
        start = text.index(LEDGER_START)
        end = text.index(LEDGER_END) + len(LEDGER_END)
        text = text[:start] + ledger + text[end:]
    else:
        text = text.rstrip() + "\n\n## Issue Sync Ledger\n\n" + ledger + "\n"
    path.write_text(text, encoding="utf-8")


def synchronize(args: argparse.Namespace, runner: Runner = subprocess_runner) -> dict[str, Any]:
    tasks_path = Path(args.tasks).resolve()
    tasks, checkpoints = parse_tasks(tasks_path)
    groups = group_tasks(tasks, checkpoints, args.granularity)
    spec_path, _, commit = validate_artifacts(tasks_path, args.artifact_commit, args.analysis_clean, runner)
    validate_groups(tasks, groups)
    root = Path(runner(["git", "rev-parse", "--show-toplevel"], spec_path.parent)).resolve()
    tasks_relative = tasks_path.relative_to(root).as_posix()
    repository = args.repo or json.loads(runner(["gh", "repo", "view", "--json", "nameWithOwner"], root))["nameWithOwner"]
    existing = parse_existing_issues(
        runner(
            ["gh", "issue", "list", "--repo", repository, "--state", "all", "--limit", "1000", "--json", "number,title,body,state,url"],
            root,
        )
    )
    actions: list[dict[str, Any]] = []
    mappings = dict(existing)
    for group in groups:
        identity = stable_identity(repository, tasks_relative, group.group_id)
        current = mappings.get(group.group_id)
        if current and current.identity == identity:
            mappings[group.group_id] = Mapping(
                identity,
                group.granularity,
                group.group_id,
                current.issue_number,
                current.url,
                current.state,
                group.task_ids,
            )
            actions.append({"action": "skip", "group": group.group_id, "issue": current.issue_number, "state": current.state})
            continue
        body = render_issue_body(group, repository, tasks_relative, commit, mappings, groups)
        title = f"{group.title}: {group.tasks[0].description}"
        if args.dry_run:
            actions.append({"action": "would-create", "group": group.group_id, "title": title, "identity": identity})
            continue
        if not args.approve:
            raise ReadinessError("GitHub writes require --approve after reviewing the dry-run")
        url = runner(["gh", "issue", "create", "--repo", repository, "--title", title, "--body", body], root)
        number_match = re.search(r"/(\d+)(?:\s*)$", url)
        if not number_match:
            raise RuntimeError(f"cannot determine issue number from gh output: {url}")
        mapping = Mapping(
            identity,
            group.granularity,
            group.group_id,
            int(number_match.group(1)),
            url,
            "OPEN",
            group.task_ids,
        )
        mappings[group.group_id] = mapping
        actions.append({"action": "created", "group": group.group_id, "issue": mapping.issue_number, "url": url})
    if not args.dry_run:
        selected = [mappings[group.group_id] for group in groups if group.group_id in mappings]
        update_ledger(tasks_path, selected)
    return {
        "tasks": tasks_relative,
        "repository": repository,
        "artifact_commit": commit,
        "granularity": groups[0].granularity,
        "groups": len(groups),
        "actions": actions,
        "ledger_updated": not args.dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, help="selected .specify/specs/<feature>/tasks.md")
    parser.add_argument("--repo", help="explicit OWNER/REPO target; defaults to origin")
    parser.add_argument("--artifact-commit", required=True, help="reviewed immutable artifact commit or ref")
    parser.add_argument("--granularity", choices=("auto", "stage", "story", "task"), default="auto")
    parser.add_argument("--analysis-clean", action="store_true", help="confirm official consistency analysis is clean")
    parser.add_argument("--dry-run", action="store_true", help="preview groups without GitHub or ledger writes")
    parser.add_argument("--approve", action="store_true", help="approve GitHub writes after reviewing dry-run")
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
        for action in result["actions"]:
            print(json.dumps(action, sort_keys=True))
        print(f"Ledger updated: {'yes' if result['ledger_updated'] else 'no (dry-run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
