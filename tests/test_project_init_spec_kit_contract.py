"""Executable guardrails for the project-init and Spec Kit contract (#166)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / ".agents" / "project-init-spec-kit-contract.json"
SCHEMA_PATH = ROOT / ".agents" / "project-init-spec-kit-contract.schema.json"
DECISION_PATH = ROOT / "docs" / "project-init-spec-kit-contract.md"
WAVE_ROOT = ROOT / ".specify" / "specs" / "wave-7-skill-influence-fidelity"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def resolve_ref(schema_root: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/")
    node: Any = schema_root
    for component in ref[2:].split("/"):
        node = node[component]
    assert isinstance(node, dict)
    return node


def validate(instance: Any, schema: dict[str, Any], schema_root: dict[str, Any], path: str = "$") -> None:
    """Validate the JSON Schema features used by this versioned contract."""
    if "$ref" in schema:
        validate(instance, resolve_ref(schema_root, schema["$ref"]), schema_root, path)
        return

    if "const" in schema:
        assert instance == schema["const"], f"{path}: expected {schema['const']!r}"
    if "enum" in schema:
        assert instance in schema["enum"], f"{path}: {instance!r} is not in enum"

    expected_type = schema.get("type")
    type_checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
    }
    if expected_type:
        assert type_checks[expected_type](instance), f"{path}: expected {expected_type}"

    if isinstance(instance, dict):
        required = schema.get("required", [])
        assert not (set(required) - set(instance)), f"{path}: missing {set(required) - set(instance)}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert not (set(instance) - set(properties)), f"{path}: unexpected {set(instance) - set(properties)}"
        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], schema_root, f"{path}.{key}")

    if isinstance(instance, list):
        assert len(instance) >= schema.get("minItems", 0), f"{path}: too few items"
        if "maxItems" in schema:
            assert len(instance) <= schema["maxItems"], f"{path}: too many items"
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True) for item in instance]
            assert len(serialized) == len(set(serialized)), f"{path}: duplicate items"
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                validate(value, item_schema, schema_root, f"{path}[{index}]")

    if isinstance(instance, str):
        assert len(instance) >= schema.get("minLength", 0), f"{path}: string is too short"
        if "pattern" in schema:
            assert re.search(schema["pattern"], instance), f"{path}: pattern mismatch"

    if isinstance(instance, int) and not isinstance(instance, bool):
        assert instance >= schema.get("minimum", instance), f"{path}: below minimum"
        assert instance <= schema.get("maximum", instance), f"{path}: above maximum"


def test_contract_instance_validates_against_published_schema() -> None:
    schema = load_json(SCHEMA_PATH)
    contract = load_json(CONTRACT_PATH)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/.agents/project-init-spec-kit-contract.schema.json")
    validate(contract, schema, schema)


def test_project_init_is_local_explicit_and_negatively_routed() -> None:
    contract = load_json(CONTRACT_PATH)
    routing = contract["routing"]
    routes = {route["intent"]: route for route in routing["routes"]}

    assert routing["default"] == "safe-local-scaffold"
    assert routing["project_init_selection"] == "explicit-only"
    assert routes["new-local-python-project"] == {
        "intent": "new-local-python-project",
        "owner": "project-init",
        "selection": "explicit",
        "consent": "target-path",
        "project_init_negative": False,
    }
    assert all(
        route["project_init_negative"]
        for intent, route in routes.items()
        if intent != "new-local-python-project"
    )


def test_spec_kit_boundary_is_immutable_official_and_additive() -> None:
    spec_kit = load_json(CONTRACT_PATH)["spec_kit"]

    assert spec_kit["upstream"] == "https://github.com/github/spec-kit"
    assert spec_kit["release"] == "v0.16.0"
    assert spec_kit["commit"] == "5dce710ce099067c7d3f2ef47a37b9a1c300b327"
    assert spec_kit["install"].endswith("github/spec-kit.git@v0.16.0")
    assert spec_kit["initialization"] == "specify init --here --integration codex"
    assert spec_kit["composition"]["choice"] == "extension"
    assert {item["choice"] for item in spec_kit["composition"]["rejected"]} == {
        "preset",
        "bundle",
        "hand-authored-scaffold",
    }


def test_readiness_and_issue_compilation_contract_is_complete() -> None:
    contract = load_json(CONTRACT_PATH)
    readiness = contract["spec_kit"]["readiness_gate"]
    compilation = contract["issue_compilation"]

    assert readiness["approval_required"] is True
    assert {check["id"] for check in readiness["checks"]} == {
        "spec-exists",
        "plan-exists",
        "tasks-exist",
        "consistency-analysis-clean",
        "no-placeholders",
        "exact-paths",
        "independent-tests",
        "dependencies-explicit",
        "user-approved",
    }
    assert compilation["owner"] == "spec-sync"
    assert compilation["default_granularity"] == "stage-or-story"
    assert compilation["task_granularity"] == "explicit-request-only"
    assert compilation["idempotency_scope"] == "open-and-closed-issues"
    assert len(compilation["required_body_sections"]) == 10
    assert "tasks.md" in compilation["mapping_write_back"]


def test_audit_and_rollout_have_complete_ownership() -> None:
    contract = load_json(CONTRACT_PATH)
    helpers = contract["audit"]["duplicate_helpers"]
    ownership = contract["rollout_ownership"]

    assert len(helpers) == 13
    assert {helper["repository"] for helper in helpers} == {
        "codex-power-pack",
        "claude-power-pack",
    }
    assert all(helper["owner_issue"] == 160 for helper in helpers)
    assert {item["issue"] for item in ownership} == set(range(158, 164))
    assert all(item["responsibilities"] and item["acceptance_evidence"] for item in ownership)


def test_decision_and_wave_artifacts_reference_the_contract() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    spec = (WAVE_ROOT / "spec.md").read_text(encoding="utf-8")
    plan = (WAVE_ROOT / "plan.md").read_text(encoding="utf-8")
    tasks = (WAVE_ROOT / "tasks.md").read_text(encoding="utf-8")

    assert "project-init-spec-kit-contract.json" in decision
    assert "Thirteen helper payloads" in decision
    assert "US7: Safe Project-to-Issue Composition" in spec
    assert ".agents/project-init-spec-kit-contract.json" in plan
    assert "T090-T097" in tasks
    for issue in range(158, 164):
        assert f"#{issue}" in decision
        assert f"#{issue}" in tasks
