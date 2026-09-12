"""Contract-conformance evidence for the spec-sync to native-wave handoff (#199)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from graphlib import CycleError, TopologicalSorter
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
CANONICAL_ISSUE_KEY = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+#[1-9][0-9]*")

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


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def string_values(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return [value for item in payload.values() for value in string_values(item)]
    if isinstance(payload, list):
        return [value for item in payload for value in string_values(item)]
    return [payload] if isinstance(payload, str) else []


def graph_from_witness(witness: dict[str, Any]) -> dict[str, set[str]]:
    nodes = set(witness["nodes"])
    graph = {node: set() for node in nodes}
    for source, target in witness["directed_edges"]:
        assert source in nodes and target in nodes, "every fixture edge endpoint must be declared"
        graph[source].add(target)
    return graph


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
    assert corpus["scenario_semantics"].startswith("Each scenario is a minimal witness delta")
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


def test_digest_contract_has_exact_serialization_not_a_style_label() -> None:
    digest = load_corpus()["digest_contract"]

    assert digest["algorithm"] == "sha256"
    assert digest["value_domain"] == ["null", "boolean", "unicode-nfc-string", "signed-64-bit-integer"]
    assert digest["forbidden_values"] == ["binary-float", "nan", "infinity", "non-nfc-string"]
    assert digest["object_key_order"] == "unicode-code-point"
    assert digest["semantic_array_order"] == "preserved"
    assert digest["set_like_array_order"] == {
        "repository_scope": "repository",
        "mapping_rows": "stable_identity",
        "selected_task_ids": "lexical-string",
        "dependency_edges": ["source", "target"],
        "repository_proofs": ["repository", "mode"],
        "issue_records": "canonical-issue-key",
    }
    assert digest["string_escapes"].endswith("slash-and-other-unicode-direct")
    assert digest["separators"] == [",", ":"]
    assert digest["trailing_newline"] is False
    assert canonical_bytes({"z": None, "a": [True, 7, "é"]}) == '{"a":[true,7,"é"],"z":null}'.encode()


def test_corpus_has_reviewable_coverage_without_claiming_runtime_proof() -> None:
    corpus = load_corpus()
    scenarios = scenarios_by_id(corpus)
    assert set(scenarios) == {f"H-{number:03d}" for number in range(1, 23)}

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
        "duplicate_issue_claim",
        "dependency_cycle",
        "valid_intra_group_dag",
        "ordered_cycle_validation",
        "inventory_incomplete",
        "inventory_stale",
        "inventory_digest_mismatch",
        "closed_external_blocker",
        "blocker_open",
        "blocker_unknown",
        "qualified_key_collision",
        "project_next_unchanged",
        "external_blocker_suppresses_assignment",
        "candidate_mapping_mismatch",
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
    missing_set = set(missing["selected_task_ids"]) - set(missing["mapped_task_ids"])
    assert missing_set
    assert set(missing["missing_task_ids"]) == missing_set
    valid_missing = missing["valid_counterpart"]
    assert set(valid_missing["selected_task_ids"]) - set(valid_missing["mapped_task_ids"]) == set()
    assert valid_missing["missing_task_ids"] == []

    ambiguous = scenarios["H-006"]["witness"]
    assert len(ambiguous["claims"]) > 1
    assert len({claim["stable_identity"] for claim in ambiguous["claims"]}) > 1

    stale = scenarios["H-007"]["witness"]
    assert stale["expected_identity"] != stale["ledger_identity"]

    duplicate_group = scenarios["H-008"]["witness"]
    assert len(set(duplicate_group["issue_keys"])) > 1

    duplicate_task = scenarios["H-009"]["witness"]
    assert len(set(duplicate_task["group_ids"])) > 1

    duplicate_issue = scenarios["H-020"]["witness"]
    assert len({claim["stable_identity"] for claim in duplicate_issue["claims"]}) > 1
    assert len({claim["group_id"] for claim in duplicate_issue["claims"]}) > 1
    assert duplicate_issue["issue_key"] == "cooneycw/codex-power-pack#310"

    cycle = scenarios["H-010"]["witness"]
    with pytest.raises(CycleError):
        tuple(TopologicalSorter(graph_from_witness(cycle)).static_order())
    assert len(set(cycle["group_membership"].values())) == 1
    assert set(cycle["group_membership"]) == set(cycle["nodes"])
    assert cycle["projected_group_edges_if_validation_were_skipped"] == []

    valid_dag = scenarios["H-021"]
    valid_witness = valid_dag["witness"]
    valid_order = tuple(TopologicalSorter(graph_from_witness(valid_witness)).static_order())
    assert set(valid_order) == set(valid_witness["nodes"])
    assert valid_order.index("T001") < valid_order.index("T002")
    assert set(valid_witness["group_membership"]) == set(valid_witness["nodes"])
    assert len(set(valid_witness["group_membership"].values())) == 1
    assert valid_witness["task_graph_acyclic"] is True
    assert valid_witness["projected_group_edges"] == []
    assert valid_dag["expected"]["assignment_input"] is not None


def test_inventory_failures_have_operational_evidence() -> None:
    scenarios = scenarios_by_id(load_corpus())

    incomplete = scenarios["H-011"]["witness"]
    proved_repositories = {proof["repository"] for proof in incomplete["repository_proofs"]}
    missing_proofs = set(incomplete["repository_scope"]) - proved_repositories
    assert missing_proofs
    assert missing_proofs == set(incomplete["missing_repository_proofs"])
    assert all(proof["terminal_page"] for proof in incomplete["repository_proofs"])
    valid_inventory = incomplete["valid_counterpart"]
    valid_proved = {proof["repository"] for proof in valid_inventory["repository_proofs"]}
    assert set(valid_inventory["repository_scope"]) - valid_proved == set()
    assert valid_inventory["missing_repository_proofs"] == []
    assert all(proof["terminal_page"] for proof in valid_inventory["repository_proofs"])

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


def test_all_canonical_issue_keys_use_minimal_positive_decimal_numbers() -> None:
    values = string_values(load_corpus())
    issue_keys = {value for value in values if "#" in value and "/" in value and not value.startswith("http")}

    assert issue_keys
    assert all(CANONICAL_ISSUE_KEY.fullmatch(key) for key in issue_keys)
    assert CANONICAL_ISSUE_KEY.fullmatch("cooneycw/kyle#44")
    assert CANONICAL_ISSUE_KEY.fullmatch("cooneycw/kyle#044") is None
    assert CANONICAL_ISSUE_KEY.fullmatch("cooneycw/kyle#0") is None


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


def test_candidate_key_must_match_the_exact_selected_mapping_row() -> None:
    scenario = scenarios_by_id(load_corpus())["H-022"]
    witness = scenario["witness"]

    assert witness["selected_mapping"]["mapping_identity"].endswith(":stage-1")
    assert witness["selected_mapping"]["issue_key"] == "cooneycw/codex-power-pack#310"
    assert witness["candidate_key"] == "cooneycw/codex-power-pack#999"
    assert witness["candidate_key"] != witness["selected_mapping"]["issue_key"]
    assert scenario["expected"]["reason"] == "candidate_mapping_mismatch"
    assert scenario["expected"]["assignment_input"] is None


def test_docs_align_reason_codes_consumer_boundary_and_old_spec_exclusion() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    project_next_contract = PROJECT_NEXT_CONTRACT_PATH.read_text(encoding="utf-8")
    corpus = load_corpus()

    for phrase in (
        "`spec-sync-native-wave-handoff/v1`",
        "`project-next` behavioral contract version `1.3`",
        "partial dependency-grammar convergence recorded by #184",
        "The handoff digest is lowercase SHA-256 over this exact serialization",
        "Inventory completeness is evidence, not a Boolean assertion",
        "Observational `observed_at`",
        "closed local issue never satisfies a qualified blocker",
        "#201 must implement the normative admission checks",
        "`candidate_key` must equal the canonical issue key",
        "unrelated historical 36-task specification",
    ):
        assert phrase in contract
    assert all(field in contract for field in ("`observed_at`", "`collected_at`", "`fresh_until`"))

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


def test_actual_context_producer_preserves_historical_contracts_and_raw_successor(tmp_path: Path) -> None:
    from tests.test_spec_sync_context import consumer_issue, fixture

    expected = {
        CONTRACT_PATH: "6c62f382975875c27c37bb20953024afaa09f988325a5c5cd2a2084306403560",
        SCENARIOS_PATH: "570ce2a1ae96bd96bfa44fe25003f878abc76eaa3d07cc6bcbd883882d7aa9a1",
        NATIVE_CONTRACT_PATH: NATIVE_CONTRACT_SHA256,
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    tasks, github = fixture(tmp_path)
    reviewed = tasks.read_bytes()
    result = github.run(tasks)
    data = spec_sync.context.unpack(consumer_issue(github)["body"])[0]
    assert data["artifacts"]["tasks"]["sha256"] == hashlib.sha256(reviewed).hexdigest()
    assert result["ledger_evidence"]["writer_before_sha256"] == hashlib.sha256(reviewed).hexdigest()
    assert result["ledger_evidence"]["writer_after_sha256"] == hashlib.sha256(tasks.read_bytes()).hexdigest()
    assert result["ledger_evidence"]["deterministic_successor"] is True
    assert data["schema"] == "spec-sync-context/v1"
    assert "assignment_input" not in data and "approval" not in data
    assert github.run(tasks)["ledger_evidence"]["comparison"] == "verified-ledger-successor"
