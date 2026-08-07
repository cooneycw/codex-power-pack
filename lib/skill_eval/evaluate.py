"""Deterministic contract evaluation and aggregate score calculation."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import (
    Category,
    ContractLayer,
    EvaluationCase,
    EvaluationResult,
    Lane,
    Observation,
    Outcome,
    Thresholds,
)


def _result(
    case: EvaluationCase,
    lane: Lane,
    observation: Observation,
    outcome: Outcome,
    layer: ContractLayer | None,
    *reasons: str,
) -> EvaluationResult:
    return EvaluationResult(
        case_id=case.case_id,
        skill=case.skill,
        category=case.category,
        lane=lane,
        outcome=outcome,
        contract_layer=layer,
        reasons=tuple(reasons),
        activation_checked=observation.activation_checked,
        selected_skill_raw=observation.selected_skill_raw,
        latency_ms=observation.latency_ms,
        total_tokens=observation.total_tokens,
    )


def _outcome_for_layer(layer: ContractLayer) -> Outcome:
    if layer is ContractLayer.ROUTING:
        return Outcome.ACTIVATION_FAILURE
    if layer is ContractLayer.RUNTIME:
        return Outcome.RUNTIME_FAILURE
    if layer in {ContractLayer.OUTPUT, ContractLayer.ISSUE_BODY}:
        return Outcome.OUTPUT_FAILURE
    return Outcome.PROCEDURE_FAILURE


def evaluate_observation(case: EvaluationCase, observation: Observation, lane: Lane) -> EvaluationResult:
    if observation.case_id != case.case_id:
        return _result(
            case,
            lane,
            observation,
            Outcome.RUNTIME_FAILURE,
            ContractLayer.RUNTIME,
            f"observation belongs to {observation.case_id}",
        )
    if not observation.available:
        return _result(
            case,
            lane,
            observation,
            Outcome.UNAVAILABLE,
            ContractLayer.UNAVAILABLE,
            observation.runtime_error or "evaluation runtime is unavailable",
        )
    if observation.timed_out or observation.runtime_error or observation.exit_code != 0:
        detail = observation.runtime_error or (
            "evaluation timed out" if observation.timed_out else f"runtime exited {observation.exit_code}"
        )
        return _result(case, lane, observation, Outcome.RUNTIME_FAILURE, ContractLayer.RUNTIME, detail)
    if observation.activation_checked:
        activation_failed = (
            observation.selected_skill == case.skill
            if case.category is Category.NEGATIVE
            else observation.selected_skill != case.expectation.selected_skill
        )
        if activation_failed:
            expectation = f"anything except {case.skill!r}" if case.category is Category.NEGATIVE else repr(
                case.expectation.selected_skill
            )
            return _result(
                case,
                lane,
                observation,
                Outcome.ACTIVATION_FAILURE,
                ContractLayer.ROUTING,
                (
                    f"expected selected skill {expectation}, got {observation.selected_skill!r} "
                    f"(raw {observation.selected_skill_raw!r})"
                ),
            )
        if case.category is Category.NEGATIVE:
            return _result(case, lane, observation, Outcome.PASS, None, "skill under test was not activated")

    for layer, passed in observation.contracts.items():
        if not passed:
            return _result(
                case,
                lane,
                observation,
                _outcome_for_layer(layer),
                layer,
                f"{layer.value} contract failed",
            )

    missing_checkpoints = sorted(set(case.expectation.required_checkpoints) - set(observation.checkpoints))
    if missing_checkpoints:
        return _result(
            case,
            lane,
            observation,
            Outcome.PROCEDURE_FAILURE,
            ContractLayer.PROCEDURE,
            f"missing checkpoints: {', '.join(missing_checkpoints)}",
        )
    forbidden = sorted(set(case.expectation.forbidden_actions).intersection(observation.actions))
    if forbidden:
        return _result(
            case,
            lane,
            observation,
            Outcome.PROCEDURE_FAILURE,
            ContractLayer.PROCEDURE,
            f"forbidden actions observed: {', '.join(forbidden)}",
        )
    missing_fields = sorted(set(case.expectation.required_output_fields) - set(observation.output_fields))
    if missing_fields:
        return _result(
            case,
            lane,
            observation,
            Outcome.OUTPUT_FAILURE,
            ContractLayer.OUTPUT,
            f"missing output fields: {', '.join(missing_fields)}",
        )
    return _result(case, lane, observation, Outcome.PASS, None, "all checked contracts passed")


def _ratio(results: list[EvaluationResult], category: Category) -> float | None:
    checked = [
        result
        for result in results
        if result.category is category
        and result.activation_checked
        and result.outcome not in {Outcome.UNAVAILABLE, Outcome.RUNTIME_FAILURE}
    ]
    if not checked:
        return None
    return sum(result.outcome is not Outcome.ACTIVATION_FAILURE for result in checked) / len(checked)


def score_results(results: Iterable[EvaluationResult], thresholds: Thresholds) -> dict[str, object]:
    materialized = list(results)
    direct = _ratio(materialized, Category.DIRECT)
    indirect = _ratio(materialized, Category.INDIRECT)
    negative = _ratio(materialized, Category.NEGATIVE)
    metrics = {
        "direct_recall": direct,
        "indirect_recall": indirect,
        "negative_precision": negative,
    }
    required = {
        "direct_recall": thresholds.direct_recall,
        "indirect_recall": thresholds.indirect_recall,
        "negative_precision": thresholds.negative_precision,
    }
    threshold_state = {
        name: "not_checked" if value is None else ("passed" if value >= required[name] else "failed")
        for name, value in metrics.items()
    }
    outcomes = Counter(result.outcome.value for result in materialized)
    return {
        "cases": len(materialized),
        "outcomes": dict(sorted(outcomes.items())),
        "metrics": metrics,
        "thresholds": required,
        "threshold_state": threshold_state,
        "passed": all(result.outcome is Outcome.PASS for result in materialized),
    }
