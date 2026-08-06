from __future__ import annotations

import json
from typing import Any

from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend
from lib.project_next.render import render_result


def test_all_human_modes_are_versioned_and_separate_both_decisions(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["active_pr_and_safe_issue"]["state"])
    result = recommend(state)

    for mode in ("brief", "compact", "full"):
        rendered = render_result(result, state, mode)
        assert "1.1" in rendered
        assert "Top action" in rendered
        assert "Next safe issue" in rendered
        assert "#1" in rendered
        assert "#2" in rendered


def test_structured_output_is_versioned_and_json_serializable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["active_pr_and_safe_issue"]["state"])
    payload = recommend(state).to_dict()

    assert payload["contract_version"] == "1.1"
    assert payload["top_action"]["issue_number"] == 1
    assert payload["next_startable_issue"] == 2
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
