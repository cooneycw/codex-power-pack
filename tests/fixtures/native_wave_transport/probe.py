"""Opt-in #198 experiment fixture. Not a production wave adapter or authenticator."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

CONTRACT_SHA = "779c2aa4f1470ef66c5eb87b0b3bdb1e22386408a633bf5a31a99ff2c307ded5"
BINDINGS = ("wave", "assignment", "revision", "generation", "coordinator", "policy", "plan", "capability")
LABELS = ("idle_observed", "busy_start", "busy_end", "withheld_start", "withheld_end", "contact", "final")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def identity():
    """Observe the nearest Codex ancestor, not the short-lived helper PID."""
    thread = str(uuid.UUID(os.environ["CODEX_THREAD_ID"]))
    pid = os.getpid()
    for _ in range(32):
        status = Path(f"/proc/{pid}/status").read_text()
        if re.search(r"^Name:\s+codex$", status, re.M):
            if pid == 1:
                raise ValueError("host_owner_unobservable: namespace PID1 is not a stable host owner")
            start = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
            return {
                "thread": thread,
                "pid": pid,
                "start": start,
                "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            }
        pid = int(re.search(r"^PPid:\s+(\d+)$", status, re.M)[1])
        if not pid:
            break
    raise ValueError("no Codex process ancestor; live participant identity unavailable")


def observe(state, kind, **fields):
    row = {
        "sequence": len(state["observations"]) + 1,
        "kind": kind,
        "elapsed": round(time.monotonic() - state["started"], 3),
        **fields,
    }
    state["observations"].append(row)
    return row


@contextlib.contextmanager
def transaction(root):
    root = Path(root)
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise ValueError("run root must be private and not a symlink")
    with (root / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((root / "state.json").read_text())
        yield state
        temporary = root / "state.tmp"
        with temporary.open("w") as output:
            json.dump(state, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(root / "state.json")
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def initialize(root, roles):
    root = Path(root)
    if not root.name.startswith("cxpp-transport-proof-198-") or root.exists():
        raise ValueError("require a fresh cxpp-transport-proof-198-* namespace")
    if not roles or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", r) for r in roles):
        raise ValueError("explicit logical participant aliases required")
    root.mkdir(mode=0o700)
    state = {
        "contract": CONTRACT_SHA,
        "version": "1.0",
        "started": time.monotonic(),
        "wave": str(uuid.uuid4()),
        "scheduled": roles,
        "participants": {},
        "events": {},
        "assignments": {},
        "reads": [],
        "acks": {},
        "attempts": {},
        "observations": [],
    }
    (root / "state.json").write_text(json.dumps(state))
    return state["wave"]


def current(state, role, actor):
    if state["participants"][role]["identity"] != actor:
        raise ValueError("participant_process_mismatch")
    if time.monotonic() - state["started"] > 900:
        raise ValueError("live_window_expired")
    return state["participants"][role]


def register(state, role, actor):
    if time.monotonic() - state["started"] > 900:
        raise ValueError("live_window_expired")
    if role not in state["scheduled"]:
        raise ValueError("unscheduled_participant")
    existing = state["participants"].get(role)
    if existing:
        if existing["identity"] != actor:
            raise ValueError("role_occupied; coordinator must fence before replacement")
        return existing["generation"]
    state["participants"][role] = {"identity": actor, "generation": str(uuid.uuid4())}
    observe(state, "participant_registered", role=role, generation=state["participants"][role]["generation"])
    return state["participants"][role]["generation"]


def emit(state, actor, role, assignment, kind, event_id=None, overrides=None):
    coordinator = current(state, "coordinator", actor)
    binding = {
        "wave": state["wave"],
        "assignment": assignment,
        "revision": 1,
        "generation": state["participants"][role]["generation"],
        "coordinator": coordinator["generation"],
        "policy": 1,
        "plan": "synthetic-counter-v1",
        "capability": "codex-queue-detected",
    }
    event = {**binding, "kind": kind, "role": role, "provenance": "registry_bound_local"}
    event.update(overrides or {})
    eid = event_id or str(uuid.uuid4())
    old = state["events"].get(eid)
    if old:
        if old != event:
            observe(state, "emit_rejected", event=eid, reason="event_id_payload_conflict")
            return {"event": eid, "disposition": "event_id_payload_conflict"}
        return {"event": eid, "disposition": "idempotent"}
    state["events"][eid] = event
    if kind == "assignment" and assignment not in state["assignments"]:
        state["assignments"][assignment] = {"binding": binding, "state": "queued", "actions": 0}
    observe(state, "event_persisted", event=eid, role=role, assignment=assignment, event_kind=kind)
    return {"event": eid, "disposition": "persisted"}


def read_event(state, actor, role, eid):
    participant = current(state, role, actor)
    event = state["events"][eid]
    if event["role"] != role:
        raise ValueError("wrong_recipient")
    key = f"{participant['generation']}:{eid}"
    if key not in state["reads"]:
        state["reads"].append(key)
        observe(state, "recipient_read", role=role, event=eid, generation=participant["generation"])
    assignment = state["assignments"].get(event["assignment"])
    if (
        event["kind"] == "assignment"
        and assignment
        and assignment["state"] == "queued"
        and event["provenance"] == "registry_bound_local"
        and event["generation"] == participant["generation"]
        and all(event[k] == assignment["binding"][k] for k in BINDINGS)
    ):
        assignment["state"] = "read"
    return event


def acknowledge(state, actor, role, eid):
    participant = current(state, role, actor)
    event = state["events"][eid]
    key = f"{participant['generation']}:{eid}"
    if key not in state["reads"]:
        raise ValueError("read_required")
    if key in state["acks"]:
        observe(state, "recipient_ack", role=role, event=eid, disposition="idempotent")
        return "idempotent"
    assignment = state["assignments"].get(event["assignment"])
    reason = "accepted"
    if event["provenance"] != "registry_bound_local":
        reason = "payload_only"
    elif event["generation"] != participant["generation"]:
        reason = "stale_generation"
    elif event["coordinator"] != state["participants"]["coordinator"]["generation"]:
        reason = "stale_coordinator"
    elif not assignment or any(event[k] != assignment["binding"][k] for k in BINDINGS):
        reason = "binding_mismatch"
    elif assignment["state"] == "held":
        reason = "held"
    elif event["kind"] == "assignment":
        if assignment["state"] == "read":
            assignment["state"] = "accepted"
        else:
            reason = "no_repeat"
    elif event["kind"] == "gate":
        if assignment["state"] == "accepted":
            assignment["state"] = "implementing"
            assignment["actions"] += 1
            observe(state, "synthetic_action", role=role, event=eid, assignment=event["assignment"], count=1)
            reason = "synthetic_action"
        else:
            reason = "out_of_order" if assignment["state"] in ("queued", "read") else "no_repeat"
    else:
        reason = "unknown_kind"
    state["acks"][key] = reason
    observe(state, "recipient_ack", role=role, event=eid, disposition=reason)
    return reason


def replace_owner(state, actor, role):
    current(state, "coordinator", actor)
    old = state["participants"].pop(role)
    for assignment in state["assignments"].values():
        if assignment["binding"]["generation"] == old["generation"]:
            assignment["state"] = "held"
    observe(state, "coordinator_fenced", role=role, generation=old["generation"], disposition="held")


def notify(root, actor, role, eid, runner=subprocess.run):
    with transaction(root) as state:
        current(state, "coordinator", actor)
        if state["events"][eid]["role"] != role:
            raise ValueError("wrong_recipient")
        attempts = state["attempts"].get(eid, 0)
        if attempts >= 2:
            raise ValueError("retry_limit")
        state["attempts"][eid] = attempts + 1
        thread = str(uuid.UUID(state["participants"][role]["identity"]["thread"]))
        observe(state, "notification_attempt", event=eid, role=role, attempt=attempts + 1)
    helper = str(Path(__file__).resolve())
    message = (
        "Authorized isolated #198 probe. "
        f"Read the durable event using python3 {helper} read {root} {role} {eid}. "
        f"Assess the printed event, then explicitly acknowledge with python3 {helper} ack {root} {role} {eid}. "
        "Report the disposition and end this turn. No other actions. "
        "This is a synthetic probe, not production authority."
    )
    started = time.monotonic()
    try:
        result = runner(
            ["codex", "queue", "--thread", thread, "--message", message],
            timeout=10,
            capture_output=True,
            text=True,
            check=False,
        )
        match = re.search(r"Queued message ([a-f0-9-]{36})", result.stdout)
        status = "queue_accepted" if result.returncode == 0 and match else "queue_error"
    except subprocess.TimeoutExpired:
        status = "queue_timeout"
    except OSError:
        status = "queue_error"
    with transaction(root) as state:
        observe(state, status, event=eid, role=role, duration=round(time.monotonic() - started, 3))
    return status


def export_rows(state):
    """No raw thread UUIDs, PIDs, prompts, environment, command output or arbitrary notes."""
    yield {
        "evidence": "observed",
        "kind": "run_manifest",
        "contract_version": "1.0",
        "contract_sha256": state["contract"],
        "participants": state["scheduled"],
        "limits": {"queue_s": 10, "ack_s": 120, "withheld_s": 30, "attempts": 2, "window_s": 900},
    }
    fields = {
        "sequence",
        "kind",
        "elapsed",
        "role",
        "event",
        "generation",
        "assignment",
        "event_kind",
        "attempt",
        "batch",
        "duration",
        "disposition",
        "reason",
        "count",
        "purpose",
        "parent",
        "remaining_s",
        "cli",
        "model",
        "effort",
        "initial_sandbox",
        "replacement_sandbox",
        "approval",
        "helper_sha256",
    }
    for row in state["observations"]:
        if row["kind"] == "operator_observation":
            continue  # Human interpretation belongs in a separately reviewed attributed record.
        yield {"evidence": "observed", **{k: v for k, v in row.items() if k in fields}}
    for name, assignment in state["assignments"].items():
        yield {
            "evidence": "fixture",
            "kind": "assignment_disposition",
            "assignment": name,
            "state": assignment["state"],
            "actions": assignment["actions"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("init", "register", "emit", "read", "ack", "notify", "fence", "mark", "deadline", "status", "export"),
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("args", nargs="*")
    parser.add_argument("--event-id")
    parser.add_argument("--override", action="append", default=[])
    args = parser.parse_args()
    if args.command == "init":
        print(initialize(args.root, args.args))
        return
    actor = identity() if args.command not in ("status", "export") else None
    if args.command == "notify":
        print(notify(args.root, actor, *args.args))
        return
    with transaction(args.root) as state:
        if args.command == "register":
            result = register(state, args.args[0], actor)
        elif args.command == "emit":
            overrides = {}
            for item in args.override:
                key, value = item.split("=", 1)
                if key not in (*BINDINGS, "provenance"):
                    raise ValueError("unsupported_override")
                overrides[key] = int(value) if key in ("revision", "policy") else value
            result = emit(state, actor, *args.args, event_id=args.event_id, overrides=overrides)
        elif args.command == "read":
            result = read_event(state, actor, *args.args)
        elif args.command == "ack":
            result = acknowledge(state, actor, *args.args)
        elif args.command == "fence":
            result = replace_owner(state, actor, args.args[0])
        elif args.command == "mark":
            role, label = args.args
            current(state, role, actor)
            if label not in LABELS:
                raise ValueError("unsupported_label")
            result = observe(state, label, role=role)
        elif args.command == "deadline":
            current(state, "coordinator", actor)
            eid = args.args[0]
            attempts = [r for r in state["observations"] if r["kind"] == "notification_attempt" and r["event"] == eid]
            if not attempts or time.monotonic() - state["started"] - attempts[0]["elapsed"] < 120:
                raise ValueError("ack_deadline_not_elapsed")
            acknowledged = any(r["kind"] == "recipient_ack" and r["event"] == eid for r in state["observations"])
            result = observe(
                state,
                "ack_deadline",
                event=eid,
                disposition="acknowledged" if acknowledged else "unacknowledged_readiness_unknown",
            )
        elif args.command == "export":
            for row in export_rows(state):
                print(json.dumps(row, sort_keys=True))
            return
        else:
            result = {
                "participants": list(state["participants"]),
                "assignments": state["assignments"],
                "observations": state["observations"][-12:],
            }
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
