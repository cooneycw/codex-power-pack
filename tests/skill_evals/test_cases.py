"""Evaluation-case schema, parsing, filtering, and deterministic lane tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.skill_eval.cases import CaseError, filter_cases, load_suite
from lib.skill_eval.deterministic import observe
from lib.skill_eval.evaluate import evaluate_observation
from lib.skill_eval.models import Category, Lane, Outcome

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / ".agents" / "skill-evaluation-cases.json"


def test_suite_is_versioned_complete_and_filterable() -> None:
    suite = load_suite(CASES)

    assert suite.tracking_issue == 161
    assert len(suite.cases) >= 26
    assert "26/26 pass" in (ROOT / "docs" / "skill-evaluation-scorecard.md").read_text(encoding="utf-8")
    assert {case.category for case in suite.cases} == set(Category)
    assert {case.case_id for case in filter_cases(suite.cases, skills={"flow-auto"})} >= {
        "CASE-004",
        "CASE-005",
        "CASE-006",
        "CASE-007",
        "CASE-008",
    }


def test_every_implicit_entrypoint_has_all_activation_categories() -> None:
    suite = load_suite(CASES)
    policy = json.loads((ROOT / ".agents" / "skill-invocation-policy.json").read_text(encoding="utf-8"))

    for entry in policy["implicit_entrypoints"]:
        categories = {
            case.category
            for case in suite.cases
            if case.skill == entry["name"] and Lane.LIVE in case.lanes
        }
        assert categories == set(Category), entry["name"]


def test_all_deterministic_repository_contracts_pass() -> None:
    suite = load_suite(CASES)
    cases = filter_cases(suite.cases, lane=Lane.DETERMINISTIC)

    results = [evaluate_observation(case, observe(case, ROOT), Lane.DETERMINISTIC) for case in cases]

    assert results
    assert {result.outcome for result in results} == {Outcome.PASS}
    assert all(not result.activation_checked for result in results)


def test_parser_rejects_unknown_fields_and_duplicate_ids(tmp_path: Path) -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    payload["suite"]["cases"][0]["surprise"] = True
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CaseError, match="unsupported fields"):
        load_suite(bad)

    payload = json.loads(CASES.read_text(encoding="utf-8"))
    payload["suite"]["cases"][1]["id"] = payload["suite"]["cases"][0]["id"]
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CaseError, match="unique"):
        load_suite(bad)
