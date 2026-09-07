"""Contract-corpus guardrails for native Codex wave identity and recovery (#197)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "native-codex-wave-contract.md"
SCENARIOS_PATH = ROOT / "tests" / "fixtures" / "native-codex-wave-contract-scenarios.json"
MAP_PATH = ROOT / "docs" / "wayfinder" / "native-codex-waves" / "map.md"
IDENTITY_TICKET_PATH = (
    ROOT / "docs" / "wayfinder" / "native-codex-waves" / "tickets" / "02-define-session-identity.md"
)


def load_corpus() -> dict[str, Any]:
    payload = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def scenarios_by_id(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios = corpus["scenarios"]
    result = {scenario["id"]: scenario for scenario in scenarios}
    assert len(result) == len(scenarios), "scenario IDs must be unique"
    return result


def test_state_vocabulary_and_transition_authority_are_complete() -> None:
    corpus = load_corpus()

    assert corpus["contract_version"] == "1.0"
    assert corpus["tracking_issue"] == 197
    assert corpus["state_vocabulary"] == [
        "queued",
        "read",
        "accepted",
        "implementing",
        "pr_open",
        "held",
        "completed",
        "cancelled",
    ]
    assert corpus["transition_authority"] == {
        "queued": "current_coordinator_generation",
        "read": "assigned_worker_generation",
        "accepted": "assigned_worker_generation",
        "implementing": "assigned_worker_generation_with_current_gate",
        "pr_open": "assigned_worker_generation",
        "held": "current_coordinator_generation",
        "completed": "current_coordinator_generation",
        "cancelled": "current_coordinator_generation",
    }

    exercised = {
        state
        for scenario in corpus["scenarios"]
        for state in scenario["states_exercised"]
    }
    assert exercised == set(corpus["state_vocabulary"])


def test_scenarios_cover_identity_authority_recovery_and_boundaries() -> None:
    corpus = load_corpus()
    scenarios = scenarios_by_id(corpus)
    assert set(scenarios) == {f"NW-{number:03d}" for number in range(1, 19)}

    coverage = {tag for scenario in scenarios.values() for tag in scenario["covers"]}
    required = {
        "three_worker_identity",
        "worker_first_registration",
        "coordinator_first_registration",
        "live_owner_conflict",
        "unknown_liveness_fails_closed",
        "queue_not_read",
        "read_vs_accept",
        "payload_sender_untrusted",
        "gate_exact_binding",
        "stale_assignment",
        "stale_worker_generation",
        "stale_coordinator_generation",
        "stale_policy",
        "local_action_suppression",
        "event_replay",
        "event_reordering",
        "event_id_payload_conflict",
        "compaction_recovery",
        "owner_restart",
        "cancellation",
        "pr_head_change",
        "merge_crash_reconcile",
        "interrupted_work_reconcile",
        "native_capabilities",
        "driver_capability_separation",
    }
    assert required <= coverage

    for scenario in scenarios.values():
        assert scenario["evidence_status"] in {"contract_fixture", "future_required_unproved"}
        assert scenario["given"]
        assert scenario["expected"]["assertions"]


def test_event_examples_are_correlatable_and_generation_fenced() -> None:
    events = [
        event
        for scenario in load_corpus()["scenarios"]
        for event in scenario["events"]
    ]

    first_seen: set[str] = set()
    event_counts = Counter(event["event_id"] for event in events)
    for event in events:
        assert {
            "event_id",
            "kind",
            "actor_role",
            "actor_generation",
            "disposition",
        } <= set(event)

        if event.get("assignment_id") is not None:
            assert {"assignment_revision", "policy_revision"} <= set(event)
            assert isinstance(event["assignment_revision"], int)
            assert isinstance(event["policy_revision"], int)

        if "replay_of" in event:
            assert event["replay_of"] == event["event_id"]
            assert event["disposition"] == "idempotent"
        elif "conflict_with" in event:
            assert event["conflict_with"] == event["event_id"]
            assert event["disposition"] == "rejected"
            assert event["reason"] == "event_id_payload_conflict"
        else:
            assert event["event_id"] not in first_seen
            first_seen.add(event["event_id"])

    assert {event_id: count for event_id, count in event_counts.items() if count > 1} == {
        "evt-nw-010-01": 2,
        "evt-nw-018-01": 2,
    }

    duplicate_events = [event for event in events if event["event_id"] == "evt-nw-010-01"]
    assert {event["payload_digest"] for event in duplicate_events} == {"sha256:event-payload-010"}
    conflict_events = [event for event in events if event["event_id"] == "evt-nw-018-01"]
    assert len({event["payload_digest"] for event in conflict_events}) == 2

    for gate in (event for event in events if event["kind"] == "gate.approved"):
        assert {
            "worker_generation",
            "plan_digest",
            "provenance",
        } <= set(gate)
        assert gate["actor_role"] == "coordinator"
        assert gate["actor_generation"].startswith("coord-g")

    for event in events:
        if event["kind"] in {"assignment.held", "assignment.cancelled", "assignment.completed"}:
            assert event["actor_role"] == "coordinator"
            assert event["actor_generation"].startswith("coord-g")
        if event["kind"] == "assignment.held":
            assert event["resume_state"] in {"queued", "read", "accepted", "implementing", "pr_open"}
            assert event["reason"]
        if event["kind"] == "assignment.pr_open":
            assert event["pr_base"] and event["pr_head"]
        if event["kind"] == "assignment.completed":
            assert event["pr_head"]


def test_local_stop_is_separate_from_coordinator_hold_and_release() -> None:
    corpus = load_corpus()
    local = corpus["local_action_suppression"]

    assert local["changes_authoritative_assignment_state"] is False
    assert set(local["authorities"]) == {
        "assigned_worker_generation",
        "current_coordinator_generation",
    }
    assert set(local["reasons"]) == {
        "gate_mismatch",
        "ownership_unknown",
        "prerequisite_failed",
        "coordinator_unavailable",
    }
    assert local["durable_hold_authority"] == "current_coordinator_generation"
    assert local["durable_release_authority"] == "current_coordinator_generation"


def test_provenance_does_not_promote_payload_or_queue_acceptance() -> None:
    provenance = load_corpus()["provenance"]

    assert provenance["levels"] == [
        "transport_observed",
        "registry_bound_local",
        "payload_only",
    ]
    assert provenance["payload_only_may_transition"] is False
    assert provenance["queue_acceptance_proves"] == "enqueued_only"
    assert provenance["same_user_mailbox_is_cryptographic_authentication"] is False


def test_external_effect_recovery_requires_reconciliation() -> None:
    scenarios = scenarios_by_id(load_corpus())
    merge_crash = scenarios["NW-015"]
    interrupted = scenarios["NW-016"]

    assert merge_crash["expected"]["final_state"] == "completed"
    assert any(event["disposition"] == "reconciled" for event in merge_crash["events"])
    assert "merge is not invoked a second time" in merge_crash["expected"]["assertions"]

    assert interrupted["expected"]["final_state"] == "held"
    assert interrupted["events"][0]["kind"] == "worker.action_suppressed"
    assert interrupted["events"][1]["kind"] == "assignment.held"


def test_three_worker_fixture_is_explicitly_not_live_acceptance_evidence() -> None:
    scenario = scenarios_by_id(load_corpus())["NW-001"]

    assert scenario["evidence_status"] == "future_required_unproved"
    assert scenario["events"] == []
    assert any("issue 203" in assertion for assertion in scenario["expected"]["assertions"])


def test_docs_preserve_contract_and_existing_compiler_boundaries() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    map_text = MAP_PATH.read_text(encoding="utf-8")
    ticket = IDENTITY_TICKET_PATH.read_text(encoding="utf-8")

    for phrase in (
        "`thread_id`",
        "`owner_generation_id`",
        "`coordinator_generation_id`",
        "Local action suppression is not a durable hold",
        "external side effects",
        "project-next` 1.3",
        "issue compiler beside `spec-sync`",
        "future_required_unproved",
    ):
        assert phrase in contract

    assert "status: active" in map_text
    assert "destination_status: agreed" in map_text
    assert "docs/native-codex-wave-contract.md" in map_text
    assert "interaction: agent" in ticket
    assert "status: closed" in ticket
    assert "not attributed to a separate human selection" in ticket
