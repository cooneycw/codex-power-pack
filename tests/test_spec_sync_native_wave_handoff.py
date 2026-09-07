"""Contract-conformance evidence for the spec-sync to native-wave handoff (#199)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from lib.project_next.classify import classify_repository
from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "spec-sync-native-wave-handoff-contract.md"
SCENARIOS_PATH = ROOT / "tests" / "fixtures" / "spec-sync-native-wave-handoff-scenarios.json"
NATIVE_CONTRACT_PATH = ROOT / "docs" / "native-codex-wave-contract.md"
PROJECT_NEXT_CONTRACT_PATH = ROOT / "docs" / "project-next-contract.md"
SPEC_SYNC_PATH = ROOT / ".codex" / "skills" / "spec-sync" / "scripts" / "spec_sync.py"
PACKAGED_SPEC_SYNC_PATH = ROOT / "plugins" / "spec" / "skills" / "spec-sync" / "scripts" / "spec_sync.py"
NATIVE_CONTRACT_SHA256 = "779c2aa4f1470ef66c5eb87b0b3bdb1e22386408a633bf5a31a99ff2c307ded5"

_spec = importlib.util.spec_from_file_location("spec_sync_native_wave_contract", SPEC_SYNC_PATH)
assert _spec is not None and _spec.loader is not None
spec_sync = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = spec_sync
_spec.loader.exec_module(spec_sync)


def load_corpus() -> dict[str, Any]:
    payload = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def scenarios_by_id(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios = corpus["scenarios"]
    result = {scenario["id"]: scenario for scenario in scenarios}
    assert len(result) == len(scenarios), "scenario IDs must be unique"
    return result


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_tasks(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_corpus_binds_existing_contracts_and_one_compiler() -> None:
    corpus = load_corpus()
    sources = corpus["source_contracts"]

    assert corpus["contract_version"] == "1.0"
    assert corpus["schema_id"] == "spec-sync-native-wave-handoff/v1"
    assert corpus["tracking_issue"] == 199
    assert corpus["consumer_issue"] == 201
    assert corpus["evidence_status"] == "contract_conformance_fixture"
    assert corpus["runtime_admission_implemented"] is False
    assert sources["native_wave"]["sha256"] == NATIVE_CONTRACT_SHA256
    assert sources["spec_sync"]["identity_version"] == "spec-sync:v1"
    assert sources["spec_sync"]["compiler_count"] == 1
    assert sources["project_next"] == {
        "path": "docs/project-next-contract.md",
        "contract_version": "1.3",
        "partial_grammar_convergence_issue": 184,
        "relationship": "decided_partial_convergence",
    }
    assert SPEC_SYNC_PATH.read_bytes() == PACKAGED_SPEC_SYNC_PATH.read_bytes()
    assert hashlib.sha256(NATIVE_CONTRACT_PATH.read_bytes()).hexdigest() == NATIVE_CONTRACT_SHA256


def test_corpus_has_reviewable_coverage_without_claiming_runtime_proof() -> None:
    corpus = load_corpus()
    scenarios = scenarios_by_id(corpus)
    assert set(scenarios) == {f"H-{number:03d}" for number in range(1, 20)}

    coverage = {tag for scenario in scenarios.values() for tag in scenario["covers"]}
    required = {
        "stage_identity",
        "story_identity",
        "same_input_digest",
        "inventory_refresh",
        "artifact_mismatch",
        "mapping_missing",
        "mapping_ambiguous",
        "mapping_stale",
        "duplicate_group_claim",
        "duplicate_task_claim",
        "dependency_cycle",
        "inventory_incomplete",
        "inventory_stale",
        "inventory_digest_mismatch",
        "closed_external_blocker",
        "blocker_open",
        "blocker_unknown",
        "qualified_key_collision",
        "project_next_unchanged",
        "external_blocker_suppresses_assignment",
        "old_spec_excluded",
    }
    assert required <= coverage

    for scenario in scenarios.values():
        assert scenario["witness"]
        assert scenario["expected"]["disposition"] in {"eligible", "rejected", "excluded"}
        if scenario["expected"]["disposition"] != "eligible":
            assert scenario["expected"]["assignment_input"] is None


def test_observation_time_does_not_change_same_input_digest() -> None:
    scenarios = scenarios_by_id(load_corpus())

    for scenario_id in ("H-001", "H-002"):
        runs = scenarios[scenario_id]["runs"]
        assert runs[0]["observed_at"] != runs[1]["observed_at"]
        assert canonical_digest(runs[0]["digest_input"]) == canonical_digest(runs[1]["digest_input"])
        assert runs[0]["digest_input"]["mapping_identity"] == runs[1]["digest_input"]["mapping_identity"]

    refresh = scenarios["H-003"]
    first, second = refresh["runs"]
    assert first["digest_input"]["mapping_identity"] == second["digest_input"]["mapping_identity"]
    assert first["digest_input"]["inventory_digest"] != second["digest_input"]["inventory_digest"]
    assert canonical_digest(first["digest_input"]) != canonical_digest(second["digest_input"])


def test_actual_compiler_preserves_stage_story_identity_and_idempotent_ledger(tmp_path: Path) -> None:
    stage_path = write_tasks(
        tmp_path / ".specify" / "specs" / "stage-demo" / "tasks.md",
        """# Tasks

## Stage 1: Foundation

- [ ] **T001** [US1] Implement `src/parser.py`.
- [ ] **T002** [US1] Test `tests/test_parser.py`; depends on T001.

**Checkpoint:** Parser behavior and its focused tests pass independently.
""",
    )
    stage_tasks, stage_checkpoints = spec_sync.parse_tasks(stage_path)
    first_stage_groups = spec_sync.group_tasks(stage_tasks, stage_checkpoints)
    second_stage_groups = spec_sync.group_tasks(stage_tasks, stage_checkpoints)
    spec_sync.validate_groups(stage_tasks, first_stage_groups)

    assert [group.group_id for group in first_stage_groups] == ["stage-1"]
    assert [group.task_ids for group in first_stage_groups] == [group.task_ids for group in second_stage_groups]
    stage_identity = spec_sync.stable_identity(
        "cooneycw/codex-power-pack",
        ".specify/specs/stage-demo/tasks.md",
        first_stage_groups[0].group_id,
    )
    assert stage_identity == (
        "spec-sync:v1:cooneycw/codex-power-pack:.specify/specs/stage-demo/tasks.md:stage-1"
    )

    mapping = spec_sync.Mapping(
        stage_identity,
        "stage",
        "stage-1",
        310,
        "https://github.com/cooneycw/codex-power-pack/issues/310",
        "OPEN",
        ("T001", "T002"),
    )
    spec_sync.update_ledger(stage_path, [mapping])
    first_write = stage_path.read_bytes()
    spec_sync.update_ledger(stage_path, [mapping])
    assert stage_path.read_bytes() == first_write
    assert stage_path.read_text(encoding="utf-8").count(spec_sync.LEDGER_START) == 1

    story_path = write_tasks(
        tmp_path / ".specify" / "specs" / "story-demo" / "tasks.md",
        """# Tasks

- [ ] **T003** [US1] Implement `src/one.py`.
- [ ] **T004** [US2] Implement `src/two.py`.
""",
    )
    story_tasks, _ = spec_sync.parse_tasks(story_path)
    first_story_groups = spec_sync.group_tasks(
        story_tasks,
        {"us-1": "US1 passes independently.", "us-2": "US2 passes independently."},
        "story",
    )
    second_story_groups = spec_sync.group_tasks(
        story_tasks,
        {"us-1": "US1 passes independently.", "us-2": "US2 passes independently."},
        "story",
    )
    spec_sync.validate_groups(story_tasks, first_story_groups)

    assert [group.group_id for group in first_story_groups] == ["us-1", "us-2"]
    assert [group.task_ids for group in first_story_groups] == [group.task_ids for group in second_story_groups]
    assert spec_sync.stable_identity(
        "cooneycw/codex-power-pack", ".specify/specs/story-demo/tasks.md", "us-2"
    ).endswith(":us-2")


def test_actual_compiler_rejects_ambiguous_duplicate_and_cyclic_inputs(tmp_path: Path) -> None:
    ambiguous = write_tasks(
        tmp_path / "ambiguous" / "tasks.md",
        "- [ ] **T001** Implement `src/a.py`.\n",
    )
    tasks, checkpoints = spec_sync.parse_tasks(ambiguous)
    with pytest.raises(spec_sync.ReadinessError, match="automatic grouping is ambiguous"):
        spec_sync.group_tasks(tasks, checkpoints)

    duplicate = write_tasks(
        tmp_path / "duplicate" / "tasks.md",
        "- [ ] **T001** Implement `src/a.py`.\n- [ ] **T001** Test `tests/test_a.py`.\n",
    )
    with pytest.raises(spec_sync.ReadinessError, match="duplicate task identifiers"):
        spec_sync.parse_tasks(duplicate)

    cycle = write_tasks(
        tmp_path / "cycle" / "tasks.md",
        """## Stage 1: Cycle
- [ ] **T001** Implement `src/a.py`; depends on T002.
- [ ] **T002** Implement `src/b.py`; depends on T001.
**Checkpoint:** This invalid cycle cannot become independently runnable.
""",
    )
    cycle_tasks, cycle_checkpoints = spec_sync.parse_tasks(cycle)
    cycle_groups = spec_sync.group_tasks(cycle_tasks, cycle_checkpoints)
    with pytest.raises(spec_sync.ReadinessError, match="cyclic task dependencies"):
        spec_sync.validate_groups(cycle_tasks, cycle_groups)


def test_rejection_cases_contain_structural_witnesses_not_only_expected_labels() -> None:
    scenarios = scenarios_by_id(load_corpus())

    artifact = scenarios["H-004"]["witness"]
    assert any(item["bound_sha256"] != item["actual_sha256"] for item in artifact["files"])

    missing = scenarios["H-005"]["witness"]
    assert set(missing["missing_task_ids"]) == set(missing["selected_task_ids"]) - set(missing["mapped_task_ids"])

    ambiguous = scenarios["H-006"]["witness"]
    assert len(ambiguous["claims"]) > 1
    assert len({claim["stable_identity"] for claim in ambiguous["claims"]}) > 1

    stale = scenarios["H-007"]["witness"]
    assert stale["expected_identity"] != stale["ledger_identity"]

    duplicate_group = scenarios["H-008"]["witness"]
    assert len(set(duplicate_group["issue_keys"])) > 1

    duplicate_task = scenarios["H-009"]["witness"]
    assert len(set(duplicate_task["group_ids"])) > 1

    cycle = scenarios["H-010"]["witness"]
    edges = {tuple(edge) for edge in cycle["directed_edges"]}
    assert any((target, source) in edges for source, target in edges)


def test_inventory_failures_have_operational_evidence() -> None:
    scenarios = scenarios_by_id(load_corpus())

    incomplete = scenarios["H-011"]["witness"]
    proved_repositories = {proof["repository"] for proof in incomplete["repository_proofs"]}
    assert set(incomplete["repository_scope"]) - proved_repositories == set(
        incomplete["missing_repository_proofs"]
    )
    assert all(proof["terminal_page"] for proof in incomplete["repository_proofs"])

    stale = scenarios["H-012"]["witness"]
    assert stale["bound_consumer_revision"] != stale["current_consumer_revision"]
    assert stale["invalidation_signal"] == "base_revision_changed"

    mismatch = scenarios["H-013"]["witness"]
    assert canonical_digest(mismatch["canonical_payload"]) != mismatch["declared_digest"]


def test_qualified_blockers_never_alias_by_issue_number() -> None:
    scenarios = scenarios_by_id(load_corpus())

    closed = scenarios["H-014"]
    assert closed["witness"]["blocker_key"] == closed["witness"]["inventory_record"]["key"]
    assert closed["witness"]["inventory_record"]["state"] == "CLOSED"
    assert closed["expected"]["satisfied_edge"][1] == closed["witness"]["blocker_key"]

    opened = scenarios["H-015"]
    assert opened["witness"]["blocker_key"] == opened["witness"]["inventory_record"]["key"]
    assert opened["witness"]["inventory_record"]["state"] == "OPEN"
    assert opened["expected"]["assignment_input"] is None

    unknown = scenarios["H-016"]
    assert unknown["witness"]["inventory_record"]["state"] == "UNKNOWN"
    assert unknown["witness"]["inventory_record"]["evidence_digest"] is None
    assert unknown["expected"]["assignment_input"] is None

    collision = scenarios["H-017"]
    required = collision["witness"]["required_blocker_key"]
    evidence = {item["key"]: item for item in collision["witness"]["available_evidence"]}
    assert required == "cooneycw/kyle#44"
    assert evidence["cooneycw/codex-power-pack#44"]["state"] == "CLOSED"
    assert evidence[required]["state"] == "UNKNOWN"
    assert required.rsplit("#", 1)[1] == "44"
    assert required != "cooneycw/codex-power-pack#44"
    assert collision["expected"]["assignment_input"] is None


def test_project_next_13_entry_points_remain_unchanged_but_are_not_global_admission() -> None:
    scenario = scenarios_by_id(load_corpus())["H-018"]
    state = RepositoryState.from_dict(scenario["witness"]["project_next_state"])

    classification = classify_repository(state)
    first = recommend(state)
    second = recommend(state)

    assert classification.available == (193,)
    assert classification.blocked == ()
    assert classification.uncertain == ()
    assert first.contract_version == "1.3"
    assert first.next_startable_issue == 193
    assert first.to_dict() == second.to_dict()
    assert scenario["expected"]["project_next_next_startable_issue"] == 193
    assert scenario["witness"]["external_dependencies"][0]["state"] == "UNKNOWN"
    assert scenario["expected"]["assignment_input"] is None


def test_docs_align_reason_codes_consumer_boundary_and_old_spec_exclusion() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    project_next_contract = PROJECT_NEXT_CONTRACT_PATH.read_text(encoding="utf-8")
    corpus = load_corpus()

    for phrase in (
        "`spec-sync-native-wave-handoff/v1`",
        "`project-next` behavioral contract version `1.3`",
        "partial dependency-grammar convergence recorded by #184",
        "Inventory completeness is evidence, not a Boolean assertion",
        "Observational `observed_at`, `collected_at`, `fresh_until`",
        "closed local issue never satisfies a qualified blocker",
        "#201 must implement the normative admission checks",
        "unrelated historical 36-task specification",
    ):
        assert phrase in contract

    rejection_reasons = {
        scenario["expected"]["reason"]
        for scenario in corpus["scenarios"]
        if scenario["expected"]["disposition"] == "rejected"
    }
    assert all(f"`{reason}`" in contract for reason in rejection_reasons)
    assert "decided partial convergence" in project_next_contract

    excluded = scenarios_by_id(corpus)["H-019"]
    assert excluded["witness"]["excluded_artifact"]["task_count"] == 36
    assert excluded["witness"]["excluded_artifact"]["selected"] is False
    assert excluded["witness"]["excluded_artifact"]["synchronized"] is False
    assert corpus["excluded_inputs"] == [excluded["witness"]["excluded_artifact"]]
