from __future__ import annotations

from typing import Any

from lib.project_next.models import Issue, RepositoryState
from lib.project_next.rank import recommend


def test_ranking_uses_critical_priority_phase_type_staleness_and_number() -> None:
    state = RepositoryState(
        repository="example/ranking",
        default_branch="main",
        collected_at="2026-08-06T00:00:00Z",
        issues=(
            Issue(9, "Wave 2 docs", labels=("p1", "documentation"), updated_at="2026-08-05T00:00:00Z"),
            Issue(8, "Wave 1 feature", labels=("p1",), updated_at="2026-08-05T00:00:00Z"),
            Issue(7, "Wave 9 security", labels=("security",), updated_at="2026-08-05T00:00:00Z"),
            Issue(6, "Wave 1 old task", labels=("p1", "task"), updated_at="2025-01-01T00:00:00Z"),
            Issue(5, "Wave 1 old task", labels=("p1", "task"), updated_at="2025-01-01T00:00:00Z"),
        ),
    )

    assert recommend(state).ranked_available == (7, 5, 6, 8, 9)


def test_repeated_ranking_is_byte_stable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["dependency_chain"]["state"])

    assert recommend(state).to_dict() == recommend(state).to_dict()


def test_incomplete_inventory_never_selects_next_startable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["incomplete_inventory"]["state"])
    result = recommend(state)

    assert result.top_action is not None and result.top_action.kind == "resolve_inventory"
    assert result.next_startable_issue is None
