"""Deterministic repository-state classification."""

from __future__ import annotations

import re
from collections import defaultdict

from .models import Classification, Issue, PullRequest, RepositoryState

ISSUE_BRANCH = re.compile(r"(?:^|/)issue-(?P<number>\d+)(?:-|$)", re.IGNORECASE)
DEPENDENCY = re.compile(
    r"\b(?:depends\s+on|blocked\s+by|requires|after)\s+#(?P<number>\d+)\b",
    re.IGNORECASE,
)
DEPENDENCY_WORDS = re.compile(r"\b(?:depends\s+on|blocked\s+by|requires|after)\b", re.IGNORECASE)
CHECKLIST_ISSUE = re.compile(r"^-\s*\[\s\]\s+.*?#(?P<number>\d+)\b", re.IGNORECASE)
EXPLICIT_PR_ISSUE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|issue)\s*:?[\s#]+(?P<number>\d+)\b",
    re.IGNORECASE,
)


def issue_number_from_branch(branch: str) -> int | None:
    match = ISSUE_BRANCH.search(branch)
    return int(match.group("number")) if match else None


def pull_request_issue_numbers(pr: PullRequest) -> tuple[int, ...]:
    numbers = set(pr.closing_issue_numbers)
    branch_issue = issue_number_from_branch(pr.head_ref)
    if branch_issue is not None:
        numbers.add(branch_issue)
    numbers.update(int(match.group("number")) for match in EXPLICIT_PR_ISSUE.finditer(f"{pr.title}\n{pr.body}"))
    return tuple(sorted(numbers))


def _dependencies(issue: Issue) -> tuple[set[int], list[str]]:
    dependencies = {int(match.group("number")) for match in DEPENDENCY.finditer(issue.body)}
    for line in issue.body.splitlines():
        match = CHECKLIST_ISSUE.search(line.strip())
        if match and re.search(r"\b(?:wave|phase|epic|parent)\b", issue.title, re.IGNORECASE):
            dependencies.add(int(match.group("number")))

    uncertainty: list[str] = []
    for line in issue.body.splitlines():
        if DEPENDENCY_WORDS.search(line) and not DEPENDENCY.search(line):
            uncertainty.append(f"ambiguous dependency wording: {line.strip()}")
    dependencies.discard(issue.number)
    return dependencies, uncertainty


def _cycle_members(graph: dict[int, set[int]]) -> set[int]:
    index = 0
    indices: dict[int, int] = {}
    lowlinks: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    cycles: set[int] = set()

    def strong_connect(node: int) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for dependency in sorted(graph.get(node, set())):
            if dependency not in graph:
                continue
            if dependency not in indices:
                strong_connect(dependency)
                lowlinks[node] = min(lowlinks[node], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[dependency])

        if lowlinks[node] != indices[node]:
            return
        component: list[int] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        if len(component) > 1:
            cycles.update(component)

    for node in sorted(graph):
        if node not in indices:
            strong_connect(node)
    return cycles


def classify_repository(state: RepositoryState) -> Classification:
    issue_numbers = {issue.number for issue in state.issues}
    evidence: dict[int, set[str]] = defaultdict(set)
    unmapped_worktrees: list[str] = []

    for worktree in state.worktrees:
        number = issue_number_from_branch(worktree.branch)
        if number in issue_numbers:
            evidence[number].add(f"worktree:{worktree.path}{':dirty' if worktree.dirty else ':clean'}")
        elif worktree.branch and worktree.branch != state.default_branch:
            unmapped_worktrees.append(f"{worktree.path} ({worktree.branch})")

    for branch in state.branches:
        number = issue_number_from_branch(branch.name)
        if number in issue_numbers:
            kind = "remote-branch" if branch.remote else "local-branch"
            evidence[number].add(f"{kind}:{branch.name}")

    for pr in state.pull_requests:
        for number in pull_request_issue_numbers(pr):
            if number in issue_numbers:
                evidence[number].add(f"pr:#{pr.number}")

    dependency_map: dict[int, set[int]] = {}
    uncertainty: dict[int, list[str]] = defaultdict(list)
    for issue in state.issues:
        dependencies, reasons = _dependencies(issue)
        dependency_map[issue.number] = dependencies
        uncertainty[issue.number].extend(reasons)
        if not state.inventory_complete:
            unknown = sorted(dependencies - issue_numbers)
            if unknown:
                uncertainty[issue.number].append(
                    "dependency state unavailable for " + ", ".join(f"#{number}" for number in unknown)
                )

    cycles = _cycle_members(dependency_map)
    blocked_by: dict[int, set[int]] = defaultdict(set)
    for number in cycles:
        blocked_by[number].update(dependency_map[number] & cycles)

    changed = True
    while changed:
        changed = False
        for issue_number, dependencies in dependency_map.items():
            before = set(blocked_by[issue_number])
            for dependency in dependencies:
                if dependency in issue_numbers:
                    blocked_by[issue_number].add(dependency)
                    blocked_by[issue_number].update(blocked_by.get(dependency, set()))
            blocked_by[issue_number].discard(issue_number)
            if blocked_by[issue_number] != before:
                changed = True

    in_flight = set(evidence)
    uncertain = {number for number, reasons in uncertainty.items() if reasons} - in_flight
    blocked = {number for number, blockers in blocked_by.items() if blockers} - in_flight - uncertain
    available = issue_numbers - in_flight - blocked - uncertain

    partitions = (in_flight, blocked, available, uncertain)
    if set().union(*partitions) != issue_numbers or sum(len(group) for group in partitions) != len(issue_numbers):
        raise AssertionError("project-next classifications are not disjoint and exhaustive")

    return Classification(
        in_flight=tuple(sorted(in_flight)),
        blocked=tuple(sorted(blocked)),
        available=tuple(sorted(available)),
        uncertain=tuple(sorted(uncertain)),
        dependency_map={number: tuple(sorted(values)) for number, values in sorted(dependency_map.items())},
        blocked_by={number: tuple(sorted(values)) for number, values in sorted(blocked_by.items()) if values},
        in_flight_evidence={number: tuple(sorted(values)) for number, values in sorted(evidence.items())},
        uncertainty={number: tuple(values) for number, values in sorted(uncertainty.items()) if values},
        unmapped_worktrees=tuple(sorted(unmapped_worktrees)),
    )
