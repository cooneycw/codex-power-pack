"""Layer-specific outcome classification and scorecard tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from lib.skill_eval.cases import load_suite
from lib.skill_eval.evaluate import evaluate_observation, score_results
from lib.skill_eval.models import ContractLayer, Lane, Observation, Outcome

ROOT = Path(__file__).resolve().parents[2]
SUITE = load_suite(ROOT / ".agents" / "skill-evaluation-cases.json")
CASE = next(case for case in SUITE.cases if case.case_id == "CASE-006")


@pytest.mark.parametrize(
    ("observation", "outcome", "layer"),
    [
        (Observation(CASE.case_id, available=False), Outcome.UNAVAILABLE, ContractLayer.UNAVAILABLE),
        (Observation(CASE.case_id, selected_skill=None), Outcome.ACTIVATION_FAILURE, ContractLayer.ROUTING),
        (
            Observation(CASE.case_id, selected_skill="flow-auto", contracts={ContractLayer.ARTIFACT: False}),
            Outcome.PROCEDURE_FAILURE,
            ContractLayer.ARTIFACT,
        ),
        (
            Observation(CASE.case_id, selected_skill="flow-auto", contracts={ContractLayer.PARSER: False}),
            Outcome.PROCEDURE_FAILURE,
            ContractLayer.PARSER,
        ),
        (
            Observation(CASE.case_id, selected_skill="flow-auto", contracts={ContractLayer.GROUPING: False}),
            Outcome.PROCEDURE_FAILURE,
            ContractLayer.GROUPING,
        ),
        (
            Observation(CASE.case_id, selected_skill="flow-auto", contracts={ContractLayer.ISSUE_BODY: False}),
            Outcome.OUTPUT_FAILURE,
            ContractLayer.ISSUE_BODY,
        ),
        (
            Observation(CASE.case_id, selected_skill="flow-auto", contracts={ContractLayer.MAPPING: False}),
            Outcome.PROCEDURE_FAILURE,
            ContractLayer.MAPPING,
        ),
        (
            Observation(CASE.case_id, selected_skill="flow-auto", runtime_error="boom"),
            Outcome.RUNTIME_FAILURE,
            ContractLayer.RUNTIME,
        ),
    ],
)
def test_failures_name_the_exact_contract_layer(
    observation: Observation, outcome: Outcome, layer: ContractLayer
) -> None:
    result = evaluate_observation(CASE, observation, Lane.LIVE)
    assert result.outcome is outcome
    assert result.contract_layer is layer


def test_scorecard_does_not_turn_unchecked_activation_green() -> None:
    observation = Observation(
        CASE.case_id,
        activation_checked=False,
        selected_skill="flow-auto",
        checkpoints=CASE.expectation.required_checkpoints,
        output_fields=CASE.expectation.required_output_fields,
    )
    result = evaluate_observation(CASE, observation, Lane.DETERMINISTIC)
    score = score_results([result], SUITE.thresholds)

    assert score["threshold_state"] == {
        "direct_recall": "not_checked",
        "indirect_recall": "not_checked",
        "negative_precision": "not_checked",
    }


def test_runtime_failure_does_not_turn_activation_green() -> None:
    result = evaluate_observation(
        CASE,
        Observation(CASE.case_id, runtime_error="no constrained result"),
        Lane.LIVE,
    )
    score = score_results([result], SUITE.thresholds)

    metrics = cast(dict[str, Any], score["metrics"])
    threshold_state = cast(dict[str, str], score["threshold_state"])
    assert metrics["direct_recall"] is None
    assert threshold_state["direct_recall"] == "not_checked"


def test_negative_case_forbids_only_the_skill_under_test() -> None:
    negative = next(case for case in SUITE.cases if case.case_id == "CASE-008")

    alternative = evaluate_observation(
        negative,
        Observation(negative.case_id, selected_skill="github-issue-view"),
        Lane.LIVE,
    )
    wrong = evaluate_observation(
        negative,
        Observation(negative.case_id, selected_skill="flow-auto"),
        Lane.LIVE,
    )

    assert alternative.outcome is Outcome.PASS
    assert wrong.outcome is Outcome.ACTIVATION_FAILURE
