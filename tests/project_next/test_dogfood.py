from __future__ import annotations

from typing import Any

import pytest

from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend


@pytest.mark.parametrize("name", ["codex_power_pack_dogfood", "claude_power_pack_dogfood"])
def test_power_pack_dogfood_fixtures_select_expected_actions(project_next_scenarios: dict[str, Any], name: str) -> None:
    scenario = project_next_scenarios[name]
    result = recommend(RepositoryState.from_dict(scenario["state"]))
    expected = scenario["expected"]

    assert result.top_action is not None
    assert result.top_action.kind == expected["top_action"]
    assert result.top_action.issue_number == expected["top_issue"]
    assert result.next_startable_issue == expected["next_startable"]
    assert list(result.classification.in_flight) == expected["in_flight"]
    assert list(result.classification.blocked) == expected["blocked"]
    assert list(result.classification.available) == expected["available"]


def test_no_non_available_issue_leaks_into_startable_selection(project_next_scenarios: dict[str, Any]) -> None:
    for scenario in project_next_scenarios.values():
        result = recommend(RepositoryState.from_dict(scenario["state"]))
        if result.next_startable_issue is not None:
            assert result.next_startable_issue in result.classification.available
        if result.top_action is not None and result.top_action.kind == "start_issue":
            assert result.top_action.issue_number in result.classification.available
