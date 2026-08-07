"""Repository-backed deterministic evaluation adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.project_next.config import ProjectNextConfig
from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend

from .cases import CaseError
from .models import ContractLayer, EvaluationCase, Observation


def _strings(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CaseError(f"{where} must be an array of strings")
    return tuple(value)


def _safe_path(root: Path, relative: object, where: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise CaseError(f"{where} must be a repository-relative path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CaseError(f"{where} escapes the repository") from exc
    return path


def _layer(value: object, default: ContractLayer = ContractLayer.PROCEDURE) -> ContractLayer:
    try:
        return ContractLayer(value) if value is not None else default
    except ValueError as exc:
        raise CaseError(f"unsupported contract layer: {value}") from exc


def _skill_text(case: EvaluationCase, config: dict[str, Any], root: Path) -> Observation:
    paths = config.get("paths")
    if not isinstance(paths, list) or not paths:
        raise CaseError(f"{case.case_id}: skill_text paths must be non-empty")
    content = "\n".join(
        _safe_path(root, relative, f"{case.case_id}.paths").read_text(encoding="utf-8")
        for relative in paths
    )
    required = _strings(config.get("required_text", []), f"{case.case_id}.required_text")
    forbidden = _strings(config.get("forbidden_text", []), f"{case.case_id}.forbidden_text")
    passed = all(needle in content for needle in required) and not any(needle in content for needle in forbidden)
    layer = _layer(config.get("contract_layer"))
    return Observation(
        case_id=case.case_id,
        activation_checked=False,
        selected_skill=case.expectation.selected_skill,
        checkpoints=case.expectation.required_checkpoints if passed else (),
        output_fields=case.expectation.required_output_fields if passed else (),
        contracts={layer: passed},
        summary=(
            f"checked {len(paths)} skill artifact(s), {len(required)} required "
            f"and {len(forbidden)} forbidden markers"
        ),
    )


def _project_next(case: EvaluationCase, config: dict[str, Any], root: Path) -> Observation:
    fixture = _safe_path(root, config.get("fixture"), f"{case.case_id}.fixture")
    scenario_name = config.get("scenario")
    if not isinstance(scenario_name, str) or not scenario_name:
        raise CaseError(f"{case.case_id}.scenario must be non-empty")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if scenario_name not in payload:
        raise CaseError(f"{case.case_id}: scenario {scenario_name!r} is missing")
    scenario = payload[scenario_name]
    state = RepositoryState.from_dict(scenario["state"])
    actual = recommend(state, ProjectNextConfig()).to_dict()
    expected = scenario["expected"]
    comparisons = {
        "top_action": actual["top_action"]["kind"] if actual.get("top_action") else None,
        "top_issue": actual["top_action"]["issue_number"] if actual.get("top_action") else None,
        "next_startable": actual["next_startable_issue"],
        "in_flight": actual["classification"]["in_flight"],
        "blocked": actual["classification"]["blocked"],
        "available": actual["classification"]["available"],
        "uncertain": actual["classification"]["uncertain"],
    }
    passed = comparisons == expected
    return Observation(
        case_id=case.case_id,
        activation_checked=False,
        selected_skill=case.expectation.selected_skill,
        checkpoints=case.expectation.required_checkpoints if passed else (),
        output_fields=tuple(actual),
        contracts={ContractLayer.PROCEDURE: passed},
        summary=f"project-next fixture {scenario_name}: {'matched' if passed else 'mismatched'}",
    )


def _observation(case: EvaluationCase, config: dict[str, Any], root: Path) -> Observation:
    fixture = _safe_path(root, config.get("fixture"), f"{case.case_id}.fixture")
    key = config.get("key")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(key, str) or key not in payload:
        raise CaseError(f"{case.case_id}: observation key is missing")
    data = payload[key]
    contracts = {
        _layer(layer): bool(passed)
        for layer, passed in data.get("contracts", {}).items()
    }
    return Observation(
        case_id=case.case_id,
        available=bool(data.get("available", True)),
        activation_checked=bool(data.get("activation_checked", False)),
        selected_skill=data.get("selected_skill"),
        checkpoints=tuple(data.get("checkpoints", [])),
        output_fields=tuple(data.get("output_fields", [])),
        actions=tuple(data.get("actions", [])),
        contracts=contracts,
        exit_code=int(data.get("exit_code", 0)),
        timed_out=bool(data.get("timed_out", False)),
        runtime_error=data.get("runtime_error"),
        summary=str(data.get("summary", "fixture observation")),
    )


def observe(case: EvaluationCase, root: Path) -> Observation:
    config = case.deterministic
    if config is None:
        raise CaseError(f"{case.case_id}: deterministic configuration is missing")
    adapter = config.get("adapter")
    if adapter == "skill_text":
        return _skill_text(case, config, root)
    if adapter == "project_next":
        return _project_next(case, config, root)
    if adapter == "observation":
        return _observation(case, config, root)
    raise CaseError(f"{case.case_id}: unsupported deterministic adapter {adapter!r}")
