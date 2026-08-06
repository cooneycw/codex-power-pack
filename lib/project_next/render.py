"""Versioned human-readable project-next output modes."""

from __future__ import annotations

from .models import Action, RecommendationResult, RepositoryState


def _action(action: Action | None) -> str:
    if action is None:
        return "None — no actionable repository work was found."
    refs = []
    if action.issue_number is not None:
        refs.append(f"issue #{action.issue_number}")
    if action.pull_request_number is not None:
        refs.append(f"PR #{action.pull_request_number}")
    suffix = f" ({', '.join(refs)})" if refs else ""
    return f"{action.kind}: {action.title}{suffix} — {action.reason}"


def _next_issue(result: RecommendationResult, state: RepositoryState) -> str:
    if result.next_startable_issue is None:
        return "None"
    issue = next(issue for issue in state.issues if issue.number == result.next_startable_issue)
    return f"#{issue.number} {issue.title}"


def render_brief(result: RecommendationResult, state: RepositoryState) -> str:
    confidence = "complete" if result.inventory_complete else "incomplete"
    return "\n".join(
        (
            f"Project Next {result.contract_version} — brief",
            f"Top action: {_action(result.top_action)}",
            f"Next safe issue: {_next_issue(result, state)}",
            f"Inventory: {confidence}",
        )
    )


def render_compact(result: RecommendationResult, state: RepositoryState) -> str:
    issues = {issue.number: issue for issue in state.issues}
    lines = [
        f"## {result.repository} — Project Next {result.contract_version}",
        "",
        f"**Top action:** {_action(result.top_action)}",
        f"**Next safe issue:** {_next_issue(result, state)}",
        (
            f"**State:** {len(state.issues)} open | {len(result.classification.in_flight)} in-flight | "
            f"{len(result.classification.blocked)} blocked | {len(result.classification.uncertain)} uncertain | "
            f"inventory {'complete' if result.inventory_complete else 'incomplete'}"
        ),
    ]
    alternatives = result.ranked_available[1:4]
    if alternatives:
        lines.extend(("", "### Other available issues"))
        lines.extend(f"- #{number} {issues[number].title}" for number in alternatives)
    if result.classification.in_flight:
        lines.extend(("", "### Active work (not startable)"))
        lines.extend(
            f"- #{number} {issues[number].title} — {', '.join(result.classification.in_flight_evidence[number])}"
            for number in result.classification.in_flight
        )
    if result.classification.blocked:
        lines.extend(("", "### Blocked (not startable)"))
        lines.extend(
            f"- #{number} {issues[number].title} — blocked by "
            + ", ".join(f"#{blocker}" for blocker in result.classification.blocked_by[number])
            for number in result.classification.blocked
        )
    if result.classification.uncertain:
        lines.extend(("", "### Uncertain (not startable)"))
        lines.extend(
            f"- #{number} {issues[number].title} — {'; '.join(result.classification.uncertainty[number])}"
            for number in result.classification.uncertain
        )
    if result.warnings:
        lines.extend(("", "### Warnings"))
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines)


def render_full(result: RecommendationResult, state: RepositoryState) -> str:
    issues = {issue.number: issue for issue in state.issues}
    lines = [render_compact(result, state), "", "### Complete classification"]
    for name, numbers in (
        ("In flight", result.classification.in_flight),
        ("Blocked", result.classification.blocked),
        ("Available", result.classification.available),
        ("Uncertain", result.classification.uncertain),
    ):
        rendered = ", ".join(f"#{number} {issues[number].title}" for number in numbers) or "none"
        lines.append(f"- {name}: {rendered}")
    lines.extend(("", "### Pull requests"))
    lines.extend(
        f"- #{pr.number} {pr.title} — head {pr.head_ref}; checks {pr.checks_state}; "
        f"review {pr.review_decision or 'unknown'}; merge {pr.merge_state}"
        for pr in state.pull_requests
    )
    if not state.pull_requests:
        lines.append("- none")
    lines.extend(("", "### Worktrees"))
    lines.extend(
        f"- {worktree.path} — {worktree.branch or '(detached)'}; {'dirty' if worktree.dirty else 'clean'}"
        for worktree in state.worktrees
    )
    if not state.worktrees:
        lines.append("- none")
    lines.extend(("", "### Unsynchronized specification tasks"))
    lines.extend(f"- {task.task_id} {task.title} — {task.source}" for task in result.unsynchronized_spec_tasks)
    if not result.unsynchronized_spec_tasks:
        lines.append("- none")
    return "\n".join(lines)


def render_result(result: RecommendationResult, state: RepositoryState, mode: str = "compact") -> str:
    if mode == "brief":
        return render_brief(result, state)
    if mode == "full":
        return render_full(result, state)
    if mode != "compact":
        raise ValueError(f"unknown project-next output mode: {mode}")
    return render_compact(result, state)
