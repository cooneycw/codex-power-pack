from __future__ import annotations

from typing import Any

import pytest

from lib.project_next.classify import classify_repository
from lib.project_next.models import RepositoryState


@pytest.mark.parametrize(
    "name",
    [
        "active_pr_and_safe_issue",
        "dependency_chain",
        "dependency_cycle",
        "ambiguous_dependency",
        "incomplete_inventory",
    ],
)
def test_fixture_classification_is_exact(project_next_scenarios: dict[str, Any], name: str) -> None:
    scenario = project_next_scenarios[name]
    result = classify_repository(RepositoryState.from_dict(scenario["state"]))
    expected = scenario["expected"]

    assert list(result.in_flight) == expected["in_flight"]
    assert list(result.blocked) == expected["blocked"]
    assert list(result.available) == expected["available"]
    assert list(result.uncertain) == expected["uncertain"]

    all_sets = [set(result.in_flight), set(result.blocked), set(result.available), set(result.uncertain)]
    assert sum(len(values) for values in all_sets) == len(set().union(*all_sets))


def test_dependency_chain_records_transitive_blockers(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["dependency_chain"]["state"])
    result = classify_repository(state)

    assert result.blocked_by[10] == (11, 12)
    assert result.blocked_by[11] == (12,)


def test_cycles_are_blocked_not_startable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["dependency_cycle"]["state"])
    result = classify_repository(state)

    assert result.blocked_by == {20: (21,), 21: (20,)}
    assert result.available == ()
