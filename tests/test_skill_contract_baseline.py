"""Wave 7 Stage 0 skill-contract inventory and evaluation baseline tests."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "skill_contract_baseline.py"
CONTRACT_PATH = REPO_ROOT / ".agents" / "skill-contracts.json"
CONTRACT_SCHEMA_PATH = REPO_ROOT / ".agents" / "skill-contracts.schema.json"
EVALUATION_PATH = REPO_ROOT / ".agents" / "skill-evaluation-cases.json"
EVALUATION_SCHEMA_PATH = REPO_ROOT / ".agents" / "skill-evaluation-cases.schema.json"

_spec = importlib.util.spec_from_file_location("skill_contract_baseline", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_versioned_json_schemas_are_published() -> None:
    contract_schema = load_json(CONTRACT_SCHEMA_PATH)
    evaluation_schema = load_json(EVALUATION_SCHEMA_PATH)

    for schema in (contract_schema, evaluation_schema):
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://github.com/cooneycw/codex-power-pack/")
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False

    assert contract_schema["properties"]["schema_version"]["const"] == "1.0"
    assert evaluation_schema["properties"]["schema_version"]["const"] == "1.0"


def test_committed_contract_matches_current_source_and_package_surfaces() -> None:
    committed = load_json(CONTRACT_PATH)
    assert committed == baseline.build_contract()
    assert baseline.run_check() == 0


def test_inventory_reconciles_the_stage_zero_baseline() -> None:
    contract = load_json(CONTRACT_PATH)
    summary = contract["summary"]

    assert summary["source_skills"] == 83
    assert summary["packaged_skills"] == 73
    assert summary["unpackaged_skills"] == 10
    assert summary["marketplace_plugins"] == 16
    assert summary["implicit_skills"] == 73

    skills = contract["skills"]
    names = [skill["name"] for skill in skills]
    assert names == sorted(names)
    assert len(names) == len(set(names)) == summary["source_skills"]

    packaged = [skill for skill in skills if skill["package"]["state"] == "packaged"]
    unpackaged = [skill for skill in skills if skill["package"]["state"] == "unpackaged"]
    assert len(packaged) == summary["packaged_skills"]
    assert len(unpackaged) == summary["unpackaged_skills"]
    assert all(skill["marketplace"]["state"] == "published" for skill in packaged)
    assert all(skill["implicit"]["state"] == "enabled" for skill in packaged)


def test_every_unpublished_source_skill_has_a_time_bounded_owner() -> None:
    contract = load_json(CONTRACT_PATH)
    unpackaged = [skill for skill in contract["skills"] if skill["package"]["state"] == "unpackaged"]
    gaps = {
        gap["subject"]: gap
        for gap in contract["gaps"]
        if gap["type"] == "unpackaged_skill"
    }

    assert set(gaps) == {skill["name"] for skill in unpackaged}
    for skill in unpackaged:
        exclusion = skill["exclusion"]
        gap = gaps[skill["name"]]
        assert exclusion["state"] == "gap"
        assert exclusion["owner"]
        assert exclusion["replacement"]
        assert exclusion["review_by"] == "2026-09-30"
        assert exclusion["tracking_issue"] == 160
        assert gap["owner"]
        assert gap["disposition"]
        assert gap["review_by"] == "2026-09-30"
        assert gap["status"] == "scheduled"
        assert gap["evidence"]


def test_cross_skill_and_host_references_are_classified_and_owned() -> None:
    contract = load_json(CONTRACT_PATH)
    references = contract["references"]
    reference_ids = [reference["id"] for reference in references]

    assert reference_ids == [f"REF-{index:04d}" for index in range(1, len(references) + 1)]
    assert Counter(reference["classification"] for reference in references).keys() == {
        "resolvable",
        "native",
        "adapted",
        "unexplained",
    }

    unexplained_groups = {
        (reference["kind"], reference["token"])
        for reference in references
        if reference["classification"] == "unexplained"
    }
    gap_tokens = {
        gap["subject"]
        for gap in contract["gaps"]
        if gap["type"] == "unexplained_reference"
    }
    assert {token for _, token in unexplained_groups} == gap_tokens

    for gap in contract["gaps"]:
        if gap["type"] != "unexplained_reference":
            continue
        assert gap["owner"]
        assert gap["disposition"]
        assert gap["tracking_issue"] in {159, 160}
        assert gap["review_by"] == "2026-09-30"
        assert gap["evidence"] == sorted(set(gap["evidence"]))


def test_alias_and_dependency_state_is_explicit() -> None:
    contract = load_json(CONTRACT_PATH)

    for skill in contract["skills"]:
        assert skill["dependencies"] == sorted(set(skill["dependencies"]))
        if skill["package"]["state"] == "packaged":
            aliases = {(alias["value"], alias["state"]) for alias in skill["aliases"]}
            assert (f"${skill['name']}", "supported") in aliases
            assert (f"/{skill['name']}", "legacy_unsupported") in aliases
        else:
            assert skill["aliases"] == []


def test_evaluation_capture_is_versioned_and_honest_about_unmeasured_activation() -> None:
    evaluation = load_json(EVALUATION_PATH)
    assert evaluation["schema_version"] == "1.0"
    capture = evaluation["captures"][0]
    inventory = capture["inventory"]

    assert inventory == {
        "source_skills": 83,
        "packaged_skills": 73,
        "unpackaged_skills": 10,
        "marketplace_plugins": 16,
        "implicit_skills": 73,
        "system_entries": 5,
        "cxpp_entries": 73,
        "total_entries": 78,
        "entry_metadata_bytes": 20640,
        "skills_section_bytes": 21127,
        "method": inventory["method"],
    }
    assert capture["activation"] == {
        "prompt_presence": "passed",
        "direct_recall": None,
        "indirect_recall": None,
        "negative_precision": None,
        "reason": capture["activation"]["reason"],
    }
    assert {case["category"] for case in capture["cases"]} == {
        "direct",
        "indirect",
        "negative",
        "incomplete",
        "edge",
    }
    assert all(case["baseline"]["status"] == "not_run" for case in capture["cases"])
    assert {failure["tracking_issue"] for failure in capture["known_failures"]} == {159, 160, 161}
