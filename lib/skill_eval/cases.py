"""Evaluation suite parsing, validation, and filtering."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .models import Category, EvaluationCase, EvaluationSuite, Expectation, Lane, LiveControls, Thresholds

CASE_ID = re.compile(r"^CASE-[0-9]{3}$")


class CaseError(ValueError):
    """Raised when an evaluation suite violates the executable contract."""


def _mapping(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CaseError(f"{where} must be an object")
    return value


def _only(payload: dict[str, Any], allowed: set[str], where: str) -> None:
    extra = set(payload) - allowed
    if extra:
        raise CaseError(f"{where} has unsupported fields: {', '.join(sorted(extra))}")


def _strings(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise CaseError(f"{where} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise CaseError(f"{where} must not contain duplicates")
    return tuple(value)


def _positive_int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CaseError(f"{where} must be a positive integer")
    return value


def _ratio(value: object, where: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
        raise CaseError(f"{where} must be between 0 and 1")
    return float(value)


def _case(payload: object, index: int) -> EvaluationCase:
    data = _mapping(payload, f"suite.cases[{index}]")
    _only(data, {"id", "skill", "category", "prompt", "lanes", "tags", "expected", "deterministic"}, f"case {index}")
    required = {"id", "skill", "category", "prompt", "lanes", "tags", "expected"}
    missing = required - set(data)
    if missing:
        raise CaseError(f"case {index} is missing: {', '.join(sorted(missing))}")

    case_id = data["id"]
    if not isinstance(case_id, str) or CASE_ID.fullmatch(case_id) is None:
        raise CaseError(f"case {index} has invalid id")
    if data["skill"] is not None and (not isinstance(data["skill"], str) or not data["skill"]):
        raise CaseError(f"{case_id}.skill must be a non-empty string or null")
    if not isinstance(data["prompt"], str) or not data["prompt"].strip():
        raise CaseError(f"{case_id}.prompt must be non-empty")

    try:
        category = Category(data["category"])
        lanes = tuple(Lane(value) for value in _strings(data["lanes"], f"{case_id}.lanes"))
    except ValueError as exc:
        raise CaseError(f"{case_id} contains an unsupported enum value: {exc}") from exc
    if not lanes:
        raise CaseError(f"{case_id}.lanes must not be empty")

    expected = _mapping(data["expected"], f"{case_id}.expected")
    _only(
        expected,
        {"selected_skill", "required_checkpoints", "required_output_fields", "forbidden_actions"},
        f"{case_id}.expected",
    )
    expected_required = {"selected_skill", "required_checkpoints", "required_output_fields", "forbidden_actions"}
    if expected_required - set(expected):
        raise CaseError(f"{case_id}.expected is incomplete")
    selected = expected["selected_skill"]
    if selected is not None and (not isinstance(selected, str) or not selected):
        raise CaseError(f"{case_id}.expected.selected_skill must be a string or null")
    if category is Category.NEGATIVE and selected is not None:
        raise CaseError(f"{case_id}: negative cases must expect no selected skill")
    if category is not Category.NEGATIVE and data["skill"] != selected:
        raise CaseError(f"{case_id}: skill and expected selected_skill must match")

    deterministic = data.get("deterministic")
    if Lane.DETERMINISTIC in lanes:
        deterministic = _mapping(deterministic, f"{case_id}.deterministic")
        if deterministic.get("adapter") not in {"skill_text", "project_next", "observation"}:
            raise CaseError(f"{case_id}.deterministic has an unsupported adapter")
    elif deterministic is not None:
        raise CaseError(f"{case_id}: deterministic config requires the deterministic lane")

    return EvaluationCase(
        case_id=case_id,
        skill=data["skill"],
        category=category,
        prompt=data["prompt"],
        lanes=lanes,
        tags=_strings(data["tags"], f"{case_id}.tags"),
        expectation=Expectation(
            selected_skill=selected,
            required_checkpoints=_strings(expected["required_checkpoints"], f"{case_id}.required_checkpoints"),
            required_output_fields=_strings(expected["required_output_fields"], f"{case_id}.required_output_fields"),
            forbidden_actions=_strings(expected["forbidden_actions"], f"{case_id}.forbidden_actions"),
        ),
        deterministic=deterministic,
    )


def load_suite(path: Path) -> EvaluationSuite:
    try:
        root = _mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseError(f"cannot read evaluation suite {path}: {exc}") from exc
    suite = _mapping(root.get("suite"), "suite")
    _only(suite, {"id", "tracking_issue", "thresholds", "live_defaults", "cases"}, "suite")
    required = {"id", "tracking_issue", "thresholds", "live_defaults", "cases"}
    if required - set(suite):
        raise CaseError("suite is incomplete")
    if not isinstance(suite["id"], str) or not suite["id"]:
        raise CaseError("suite.id must be non-empty")

    thresholds = _mapping(suite["thresholds"], "suite.thresholds")
    threshold_keys = {"direct_recall", "indirect_recall", "negative_precision"}
    _only(thresholds, threshold_keys, "suite.thresholds")
    if set(thresholds) != threshold_keys:
        raise CaseError("suite.thresholds is incomplete")

    controls = _mapping(suite["live_defaults"], "suite.live_defaults")
    control_keys = {
        "timeout_seconds",
        "max_cases",
        "max_total_tokens",
        "max_output_bytes",
        "retention_days",
        "model",
    }
    _only(controls, control_keys, "suite.live_defaults")
    if set(controls) != control_keys:
        raise CaseError("suite.live_defaults is incomplete")
    model = controls["model"]
    if model is not None and (not isinstance(model, str) or not model):
        raise CaseError("suite.live_defaults.model must be a string or null")

    raw_cases = suite["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CaseError("suite.cases must be a non-empty array")
    cases = tuple(_case(item, index) for index, item in enumerate(raw_cases))
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise CaseError("suite case ids must be unique")
    for required_category in Category:
        if not any(case.category is required_category for case in cases):
            raise CaseError(f"suite is missing {required_category.value} cases")

    return EvaluationSuite(
        suite_id=suite["id"],
        tracking_issue=_positive_int(suite["tracking_issue"], "suite.tracking_issue"),
        thresholds=Thresholds(**{key: _ratio(thresholds[key], f"thresholds.{key}") for key in threshold_keys}),
        live_controls=LiveControls(
            timeout_seconds=_positive_int(controls["timeout_seconds"], "live_defaults.timeout_seconds"),
            max_cases=_positive_int(controls["max_cases"], "live_defaults.max_cases"),
            max_total_tokens=_positive_int(controls["max_total_tokens"], "live_defaults.max_total_tokens"),
            max_output_bytes=_positive_int(controls["max_output_bytes"], "live_defaults.max_output_bytes"),
            retention_days=_positive_int(controls["retention_days"], "live_defaults.retention_days"),
            model=model,
        ),
        cases=cases,
    )


def filter_cases(
    cases: Iterable[EvaluationCase],
    *,
    lane: Lane | None = None,
    case_ids: set[str] | None = None,
    skills: set[str] | None = None,
    categories: set[Category] | None = None,
    tags: set[str] | None = None,
) -> tuple[EvaluationCase, ...]:
    selected = []
    for case in cases:
        if lane is not None and lane not in case.lanes:
            continue
        if case_ids and case.case_id not in case_ids:
            continue
        if skills and case.skill not in skills:
            continue
        if categories and case.category not in categories:
            continue
        if tags and not tags.intersection(case.tags):
            continue
        selected.append(case)
    return tuple(selected)
