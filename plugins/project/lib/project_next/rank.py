"""Stable ranking and top-action selection."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .classify import classify_repository, pull_request_issue_numbers
from .config import ProjectNextConfig
from .models import Action, Classification, Issue, RecommendationResult, RepositoryState

CONTRACT_VERSION = "1.1"
PHASE = re.compile(r"\b(?:wave|phase)[-\s:]*(?P<number>\d+)\b", re.IGNORECASE)


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _priority(issue: Issue, config: ProjectNextConfig) -> int:
    labels = issue.normalized_labels
    if labels & set(config.high_priority_labels):
        return 0
    if labels & set(config.medium_priority_labels):
        return 1
    return 2


def _phase(issue: Issue) -> int:
    for label in issue.normalized_labels:
        match = PHASE.search(label)
        if match:
            return int(match.group("number"))
    match = PHASE.search(issue.title)
    return int(match.group("number")) if match else 10_000


def _type_rank(issue: Issue, config: ProjectNextConfig) -> int:
    labels = issue.normalized_labels
    title = issue.title.casefold()
    if labels & set(config.planning_labels) or re.search(r"\b(?:epic|tracking|planning)\b", title):
        return 3
    if "bug" in labels or "task" in labels or re.search(r"\b(?:fix|restore|implement)\b", title):
        return 0
    if labels & set(config.quick_win_labels):
        return 1
    return 2


def _staleness(issue: Issue, state: RepositoryState, config: ProjectNextConfig) -> int:
    collected = _parse_time(state.collected_at) or datetime.now(timezone.utc)
    updated = _parse_time(issue.updated_at) or _parse_time(issue.created_at)
    if updated is None:
        return 1
    age = max(0, (collected - updated).days)
    return 0 if age >= config.stale_after_days else 1


def rank_key(issue: Issue, state: RepositoryState, config: ProjectNextConfig) -> tuple[int, ...]:
    labels = issue.normalized_labels
    critical = 0 if (labels & set(config.critical_labels) or ("bug" in labels and _priority(issue, config) == 0)) else 1
    quick_win = 0 if labels & set(config.quick_win_labels) else 1
    return (
        critical,
        _priority(issue, config),
        _phase(issue),
        _type_rank(issue, config),
        quick_win,
        _staleness(issue, state, config),
        issue.number,
    )


def _issue_rank(
    number: int, issues: dict[int, Issue], state: RepositoryState, config: ProjectNextConfig
) -> tuple[int, ...]:
    return rank_key(issues[number], state, config) if number in issues else (9, 9, 99_999, 9, 9, 9, number)


def _top_action(
    state: RepositoryState,
    classification: Classification,
    ranked: tuple[int, ...],
    config: ProjectNextConfig,
) -> Action | None:
    issues = {issue.number: issue for issue in state.issues}
    if not state.inventory_complete or state.collector_errors:
        detail = tuple(state.collector_errors or state.collector_warnings)
        return Action(
            kind="resolve_inventory",
            title="Restore complete repository inventory",
            reason="The issue inventory is incomplete, so a globally correct recommendation cannot be claimed.",
            evidence=detail,
        )

    pr_candidates: list[tuple[int, tuple[int, ...], int, Action]] = []
    action_priority = {"fix_gate": 0, "address_review": 1, "merge_pr": 2, "continue_pr": 3}
    for pr in state.pull_requests:
        mapped = [number for number in pull_request_issue_numbers(pr) if number in issues]
        issue_number = min(mapped, key=lambda number: _issue_rank(number, issues, state, config)) if mapped else None
        if pr.checks_state == "failure":
            kind = "fix_gate"
            reason = f"PR #{pr.number} has failing checks."
        elif pr.review_decision.upper() == "CHANGES_REQUESTED":
            kind = "address_review"
            reason = f"PR #{pr.number} has requested changes."
        elif (
            not pr.draft
            and pr.checks_state == "success"
            and pr.review_decision.upper() in {"APPROVED", ""}
            and pr.merge_state.upper() in {"CLEAN", "HAS_HOOKS", "UNSTABLE"}
        ):
            kind = "merge_pr"
            reason = f"PR #{pr.number} is ready to merge."
        else:
            kind = "continue_pr"
            reason = f"PR #{pr.number} is active and should be completed before broad new work."
        rank = _issue_rank(issue_number, issues, state, config) if issue_number else (9, 9, 99_999, 9, 9, 9, pr.number)
        pr_candidates.append(
            (
                action_priority[kind],
                rank,
                pr.number,
                Action(
                    kind=kind,
                    title=pr.title,
                    reason=reason,
                    issue_number=issue_number,
                    pull_request_number=pr.number,
                    evidence=(
                        f"head:{pr.head_ref}",
                        f"checks:{pr.checks_state}",
                        f"review:{pr.review_decision or 'unknown'}",
                    ),
                ),
            )
        )
    if pr_candidates:
        return min(pr_candidates, key=lambda item: item[:3])[3]

    dirty_worktrees = []
    for worktree in state.worktrees:
        if not worktree.dirty:
            continue
        match = re.search(r"(?:^|/)issue-(\d+)(?:-|$)", worktree.branch, re.IGNORECASE)
        issue_number = int(match.group(1)) if match else None
        dirty_worktrees.append((issue_number, worktree))
    if dirty_worktrees:
        issue_number, worktree = min(
            dirty_worktrees,
            key=lambda item: (
                _issue_rank(item[0], issues, state, config) if item[0] else (9, 9, 99_999, 9, 9, 9, 99_999)
            ),
        )
        return Action(
            kind="continue_work",
            title=issues[issue_number].title if issue_number in issues else f"Continue {worktree.branch}",
            reason="An active worktree has uncommitted changes.",
            issue_number=issue_number,
            evidence=(f"worktree:{worktree.path}", "dirty:true"),
        )

    if classification.in_flight:
        issue_number = min(classification.in_flight, key=lambda number: _issue_rank(number, issues, state, config))
        return Action(
            kind="continue_work",
            title=issues[issue_number].title,
            reason="The issue already has a branch or worktree in flight.",
            issue_number=issue_number,
            evidence=classification.in_flight_evidence.get(issue_number, ()),
        )

    if state.gate_status == "failing":
        return Action(
            kind="fix_gate",
            title="Repair the repository quality gate",
            reason="Known failing gates outrank starting broad feature work.",
            evidence=("gate:failing",),
        )

    if ranked:
        issue_number = ranked[0]
        return Action(
            kind="start_issue",
            title=issues[issue_number].title,
            reason="This is the highest-ranked issue that passed the availability gate.",
            issue_number=issue_number,
        )

    invalid_mappings = tuple(task for task in state.spec_tasks if task.mapping_status in {"stale", "ambiguous"})
    if invalid_mappings:
        task = invalid_mappings[0]
        return Action(
            kind="resolve_spec_mapping",
            title=f"Repair {task.mapping_status} Spec Kit mapping for {task.task_id}",
            reason="Stale or ambiguous ledger state cannot safely represent synchronized work.",
            evidence=(task.source, task.stable_identity or "identity:missing"),
        )

    pending = tuple(task for task in state.spec_tasks if not task.synchronized)
    if pending:
        group = pending[0].group_id or pending[0].task_id
        return Action(
            kind="sync_spec",
            title=f"Sync specification group {group}",
            reason="The approved specification contains a group with no stable GitHub issue mapping.",
            evidence=(pending[0].source,),
        )
    return None


def recommend(state: RepositoryState, config: ProjectNextConfig | None = None) -> RecommendationResult:
    config = config or ProjectNextConfig()
    classification = classify_repository(state)
    issues = {issue.number: issue for issue in state.issues}
    ranked = tuple(
        issue.number
        for issue in sorted(
            (issues[number] for number in classification.available),
            key=lambda issue: rank_key(issue, state, config),
        )
    )
    next_startable = ranked[0] if ranked and state.inventory_complete and not state.collector_errors else None
    pending = tuple(task for task in state.spec_tasks if not task.synchronized)
    warnings = tuple(state.collector_warnings) + tuple(state.collector_errors)
    if classification.unmapped_worktrees:
        warnings += tuple(f"unmapped worktree: {item}" for item in classification.unmapped_worktrees)
    return RecommendationResult(
        contract_version=CONTRACT_VERSION,
        repository=state.repository,
        inventory_complete=state.inventory_complete and not state.collector_errors,
        classification=classification,
        ranked_available=ranked,
        top_action=_top_action(state, classification, ranked, config),
        next_startable_issue=next_startable,
        unsynchronized_spec_tasks=pending,
        warnings=warnings,
    )
