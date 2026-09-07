"""Offline tests; no Codex process is ever started by these tests."""

import importlib.util
import json
import subprocess
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/native_wave_transport"
spec = importlib.util.spec_from_file_location("transport_probe", FIXTURES / "probe.py")
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
CASES = json.loads((FIXTURES / "cases.json").read_text())
C = {"thread": str(uuid.uuid4()), "pid": 1, "start": "1", "boot": "fixture"}
W = {"thread": str(uuid.uuid4()), "pid": 2, "start": "2", "boot": "fixture"}


@pytest.fixture
def run(tmp_path):
    root = tmp_path / "cxpp-transport-proof-198-test"
    probe.initialize(root, ["coordinator", "worker"])
    with probe.transaction(root) as state:
        probe.register(state, "coordinator", C)
        probe.register(state, "worker", W)
    return root


def apply(state, eid, actor=W):
    probe.read_event(state, actor, "worker", eid)
    return probe.acknowledge(state, actor, "worker", eid)


def test_contract_pin_and_case_coverage():
    import hashlib

    assert hashlib.sha256((ROOT / "docs/native-codex-wave-contract.md").read_bytes()).hexdigest() == probe.CONTRACT_SHA
    assert CASES["contract_sha256"] == probe.CONTRACT_SHA
    assert {c["id"] for c in CASES["cases"]} == {
        "contact",
        "idle",
        "busy",
        "replay",
        "replacement",
        "timeout",
        "provenance",
    }
    assert all(c["live_required"] for c in CASES["cases"])


def test_read_accept_action_and_replayed_notifications(run):
    with probe.transaction(run) as state:
        assignment = probe.emit(state, C, "worker", "a", "assignment")["event"]
        gate = probe.emit(state, C, "worker", "a", "gate")["event"]
        assert state["assignments"]["a"]["state"] == "queued"
        with pytest.raises(ValueError, match="read_required"):
            probe.acknowledge(state, W, "worker", assignment)
        probe.read_event(state, W, "worker", assignment)
        assert state["assignments"]["a"]["state"] == "read"
        assert probe.acknowledge(state, W, "worker", assignment) == "accepted"
        assert apply(state, gate) == "synthetic_action"
        assert apply(state, gate) == "idempotent"
        assert apply(state, assignment) == "idempotent"
        another_gate = probe.emit(state, C, "worker", "a", "gate")["event"]
        assert apply(state, another_gate) == "no_repeat"
        assert state["assignments"]["a"]["actions"] == 1


def test_early_gate_does_not_become_authorized_on_retry(run):
    with probe.transaction(run) as state:
        assignment = probe.emit(state, C, "worker", "a", "assignment")["event"]
        gate = probe.emit(state, C, "worker", "a", "gate")["event"]
        assert apply(state, gate) == "out_of_order"
        assert apply(state, assignment) == "accepted"
        assert apply(state, gate) == "idempotent"
        assert state["assignments"]["a"]["actions"] == 0
        fresh = probe.emit(state, C, "worker", "a", "gate")["event"]
        assert apply(state, fresh) == "synthetic_action"


@pytest.mark.parametrize("override", CASES["stale_controls"])
def test_stale_controls_never_authorize(run, override):
    with probe.transaction(run) as state:
        assignment = probe.emit(state, C, "worker", "a", "assignment")["event"]
        apply(state, assignment)
        gate = probe.emit(state, C, "worker", "a", "gate", overrides=override)["event"]
        assert apply(state, gate) not in ("accepted", "synthetic_action")
        assert state["assignments"]["a"]["actions"] == 0


def test_event_content_conflict_preserves_first_event(run):
    with probe.transaction(run) as state:
        eid = probe.emit(state, C, "worker", "a", "assignment")["event"]
        original = dict(state["events"][eid])
        assert probe.emit(state, C, "worker", "a", "assignment", eid)["disposition"] == "idempotent"
        assert probe.emit(state, C, "worker", "a", "gate", eid)["disposition"] == "event_id_payload_conflict"
        assert state["events"][eid] == original


def test_replacement_fences_process_and_holds_old_assignment(run):
    newer = {**W, "pid": 3, "start": "3", "thread": str(uuid.uuid4())}
    with probe.transaction(run) as state:
        assignment = probe.emit(state, C, "worker", "a", "assignment")["event"]
        apply(state, assignment)
        gate = probe.emit(state, C, "worker", "a", "gate")["event"]
        probe.replace_owner(state, C, "worker")
        probe.register(state, "worker", newer)
        with pytest.raises(ValueError, match="participant_process_mismatch"):
            apply(state, gate)
        assert apply(state, gate, newer) == "stale_generation"
        assert state["assignments"]["a"]["state"] == "held"
        assert state["assignments"]["a"]["actions"] == 0


def test_queue_timeout_retry_limit_and_no_ack_inference(run):
    with probe.transaction(run) as state:
        eid = probe.emit(state, C, "worker", "a", "assignment")["event"]
    calls = []

    def timeout(argv, **kwargs):
        calls.append(argv)
        assert kwargs["timeout"] == 10
        raise subprocess.TimeoutExpired(argv, 10)

    assert probe.notify(run, C, "worker", eid, timeout) == "queue_timeout"
    assert probe.notify(run, C, "worker", eid, timeout) == "queue_timeout"
    with pytest.raises(ValueError, match="retry_limit"):
        probe.notify(run, C, "worker", eid, timeout)
    assert len(calls) == 2
    with probe.transaction(run) as state:
        assert not state["acks"]
        assert state["assignments"]["a"]["state"] == "queued"
        assert len(state["events"]) == 1


def test_process_and_namespace_boundaries(run):
    with probe.transaction(run) as state:
        with pytest.raises(ValueError, match="unscheduled"):
            probe.register(state, "outsider", W)
        with pytest.raises(ValueError, match="role_occupied"):
            probe.register(state, "worker", C)
        with pytest.raises(ValueError, match="participant_process_mismatch"):
            probe.emit(state, W, "worker", "a", "assignment")
        state["started"] -= 901
        with pytest.raises(ValueError, match="live_window_expired"):
            probe.current(state, "worker", W)
        with pytest.raises(ValueError, match="live_window_expired"):
            probe.register(state, "worker", W)
    run.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        with probe.transaction(run):
            pass


def test_export_does_not_include_raw_process_identity(run):
    with probe.transaction(run) as state:
        probe.observe(state, "recipient_read", role="worker", thread=W["thread"], prompt="private text")
        probe.observe(state, "operator_observation", fact="private note")
        exported = json.dumps(list(probe.export_rows(state)))
        for actor in (C, W):
            assert actor["thread"] not in exported
        assert '"pid"' not in exported
        assert '"boot"' not in exported
        assert '"start"' not in exported
        assert "private" not in exported


def test_namespace_pid1_cannot_register_as_host_owner(monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", W["thread"])
    monkeypatch.setattr(probe.os, "getpid", lambda: 1)
    monkeypatch.setattr(Path, "read_text", lambda self: "Name:\tcodex\nPPid:\t0\n")
    with pytest.raises(ValueError, match="host_owner_unobservable"):
        probe.identity()


@pytest.mark.parametrize("available", [True, False])
def test_queue_result_never_infers_recipient_read(run, available):
    with probe.transaction(run) as state:
        eid = probe.emit(state, C, "worker", "a", "assignment")["event"]

    def runner(argv, **kwargs):
        if not available:
            raise FileNotFoundError("codex")
        return subprocess.CompletedProcess(argv, 0, f"Queued message {uuid.uuid4()}")

    assert probe.notify(run, C, "worker", eid, runner) == ("queue_accepted" if available else "queue_error")
    with probe.transaction(run) as state:
        assert not state["reads"] and not state["acks"]
        assert state["assignments"]["a"]["state"] == "queued"


def test_published_evidence_has_bounded_correlated_reads_and_real_replacement():
    rows = [
        json.loads(line)
        for line in (ROOT / "docs/evidence/native-wave-transport/issue-198.jsonl").read_text().splitlines()
    ]
    assert all(row.get("elapsed", 0) <= 900 for row in rows)
    attempts = [r for r in rows if r["kind"] == "notification_attempt"]
    assert max(r["attempt"] for r in attempts) == 2
    for ack in (r for r in rows if r["kind"] == "recipient_ack"):
        assert any(
            r["kind"] == "recipient_read"
            and r["run_alias"] == ack["run_alias"]
            and r["event"] == ack["event"]
            and r["elapsed"] < ack["elapsed"]
            for r in rows
        )
    owners = {r["owner_alias"]: r for r in rows if r["kind"] == "generation_capability"}
    old, new = owners["worker-second-g2"], owners["worker-second-g3"]
    assert old["generation"] != new["generation"]
    assert old["sandbox"] == new["sandbox"] == "danger-full-access"
    assert any(r["kind"] == "recipient_read" and r["generation"] == new["generation"] for r in rows)
