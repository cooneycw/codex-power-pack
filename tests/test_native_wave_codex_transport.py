"""Pinned experimental response shapes, bounded proxy IO, and conservative reconciliation."""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from lib.native_wave.codex_transport import CodexTransport, ProxyRPC, verify_runtime
from lib.native_wave.delivery_types import DeliveryError, RuntimeBinding
from tests.test_native_wave_events_replay import snapshot

THREAD = str(UUID(int=2))
COMMAND = str(UUID(int=100))
POINTER = "fixed durable event pointer"


def runtime(tmp_path):
    with Path(sys.executable).open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return RuntimeBinding(str(tmp_path / "app.sock"), "test-host", str(UUID(int=3)), 9000, 10, 1, 2,
                          checksum, "0.154.0")


def capability():
    value = snapshot("worker")
    # Recompute immutable capability digest through the constructor's canonical factory.
    from dataclasses import asdict

    from lib.native_wave.types import CapabilitySnapshot
    fields = asdict(value)
    fields.pop("snapshot_id")
    fields["evidence"] = value.evidence
    fields["cli_version"] = "0.154.0"
    return CapabilitySnapshot.create(**fields)


class RPC:
    def __init__(self):
        self.calls = []
        self.thread = {"id": THREAD, "status": {"type": "idle"}, "canAcceptDirectInput": True,
                       "ephemeral": False, "parentThreadId": None, "source": "cli", "model": "worker",
                       "reasoningEffort": "high", "cwd": "/repos", "cliVersion": "old-creation-version"}
        self.turns = [{"id": "turn-1", "status": "completed"}]
        self.queue = []
        self.items = []
        self.cursor = None
        self.added = {"id": "q-1", "clientUserMessageId": COMMAND,
                      "input": [{"type": "text", "text": POINTER}]}

    def __call__(self, *args):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def call(self, method, params, *, before_send=None):
        if before_send is not None:
            before_send()
        self.calls.append((method, params))
        if method == "thread/read":
            return {"thread": self.thread}
        if method == "thread/turns/list":
            return {"data": self.turns, "nextCursor": None}
        if method == "thread/queue/add":
            return {"queuedSubmission": self.added}
        if method == "thread/queue/list":
            return {"data": self.queue, "nextCursor": self.cursor}
        if method == "thread/items/list":
            return {"data": self.items, "nextCursor": "history-incomplete"}
        raise AssertionError(method)


def backend(rpc, *, permissions=lambda *args: True):
    return CodexTransport(Path(sys.executable), rpc_factory=rpc, permissions=permissions)


@pytest.mark.parametrize("state,expected", [("idle", "idle"), ("active", "busy")])
def test_fixture_current_permissions_allow_loaded_thread_only(tmp_path, state, expected):
    rpc = RPC()
    rpc.thread["status"] = {"type": state, "activeFlags": []}
    transport = backend(rpc)
    binding = runtime(tmp_path)
    assert transport.inspect(binding, THREAD, capability()).state == expected
    assert transport.enqueue(binding, THREAD, POINTER, COMMAND, before_send=lambda: None) == "q-1"
    calls = [params for method, params in rpc.calls if method == "thread/queue/add"]
    assert calls == [{"threadId": THREAD, "clientUserMessageId": COMMAND,
                      "input": [{"type": "text", "text": POINTER}]}]
    assert all(method not in {"thread/resume", "thread/queue/start", "turn/start"} for method, _ in rpc.calls)


def test_production_missing_current_permissions_refuses_before_add(tmp_path):
    rpc = RPC()
    transport = backend(rpc, permissions=None)
    assert transport.inspect(runtime(tmp_path), THREAD, capability()).state == "permissions_unverified"
    with pytest.raises(DeliveryError, match="current_inspection"):
        transport.enqueue(runtime(tmp_path), THREAD, POINTER, COMMAND, before_send=lambda: None)
    assert all(method != "thread/queue/add" for method, _ in rpc.calls)


@pytest.mark.parametrize("change,expected", [
    ({"status": {"type": "notLoaded"}}, "unloaded"),
    ({"status": {"type": "active", "activeFlags": ["waitingOnApproval"]}}, "approval_or_input_waiting"),
    ({"status": {"type": "active", "activeFlags": ["waitingOnUserInput"]}}, "approval_or_input_waiting"),
    ({"status": {"type": "active"}}, "unknown"),
    ({"status": {}}, "unknown"),
    ({"status": {"type": "systemError"}}, "unknown"),
    ({"canAcceptDirectInput": None}, "origin_restricted"),
    ({"canAcceptDirectInput": False}, "origin_restricted"),
    ({"source": {"subAgent": "review"}}, "origin_restricted"),
    ({"parentThreadId": str(UUID(int=5))}, "origin_restricted"),
    ({"ephemeral": True}, "origin_restricted"),
    ({"model": "changed"}, "profile_changed_or_unknown"),
    ({"cwd": "/wrong-root"}, "profile_changed_or_unknown"),
])
def test_restrictions_are_named_and_never_probe_by_resume(tmp_path, change, expected):
    rpc = RPC()
    rpc.thread.update(change)
    transport = backend(rpc)
    assert transport.inspect(runtime(tmp_path), THREAD, capability()).state == expected
    assert all(method in {"thread/read", "thread/turns/list"} for method, _ in rpc.calls)


@pytest.mark.parametrize("turns,expected", [([], "history_unavailable"),
    ([{"status": "interrupted"}], "interrupted"), ([{"status": "failed"}], "history_unavailable")])
def test_idle_does_not_override_interrupted_or_missing_history(tmp_path, turns, expected):
    rpc = RPC()
    rpc.turns = turns
    rpc.queue = [rpc.added]  # An existing item does not authorize restarting stopped work.
    transport = backend(rpc)
    assert transport.inspect(runtime(tmp_path), THREAD, capability()).state == expected
    with pytest.raises(DeliveryError):
        transport.enqueue(runtime(tmp_path), THREAD, POINTER, COMMAND, before_send=lambda: None)
    assert not any(method == "thread/queue/start" for method, _ in rpc.calls)


def test_eligibility_is_rechecked_and_consumed(tmp_path):
    rpc = RPC()
    transport = backend(rpc)
    transport.inspect(runtime(tmp_path), THREAD, capability())
    rpc.thread["status"] = {"type": "notLoaded"}
    with pytest.raises(DeliveryError, match="eligibility_changed"):
        transport.enqueue(runtime(tmp_path), THREAD, POINTER, COMMAND, before_send=lambda: None)
    assert all(method != "thread/queue/add" for method, _ in rpc.calls)


@pytest.mark.parametrize("client,text,expected", [(COMMAND, POINTER, "started"),
                                                (None, POINTER, "unknown"),
                                                (COMMAND, "different", "unknown")])
def test_consumed_queue_requires_exact_history_client_id_and_payload(tmp_path, client, text, expected):
    rpc = RPC()
    rpc.items = [{"turnId": "turn-1", "item": {"type": "userMessage", "id": "item-1", "clientId": client,
                                                "content": [{"type": "text", "text": text}]}}]
    assert backend(rpc).reconcile(runtime(tmp_path), THREAD, POINTER, COMMAND).state == expected


def test_unstable_queue_pagination_only_accepts_positive_evidence(tmp_path):
    rpc = RPC()
    rpc.cursor = "50"  # Repeated/shifted offsets never supply negative evidence.
    result = backend(rpc).reconcile(runtime(tmp_path), THREAD, POINTER, COMMAND)
    assert result.state == "unknown"
    assert len([method for method, _ in rpc.calls if method == "thread/queue/list"]) == 3
    rpc.queue = [rpc.added]
    result = backend(rpc).reconcile(runtime(tmp_path), THREAD, POINTER, COMMAND)
    assert result.state == "queued" and result.submission_id == "q-1"


@pytest.mark.parametrize("item", [None, {}, {"id": "q-1", "clientUserMessageId": "wrong"}])
def test_malformed_add_reply_is_unknown_never_a_retry_instruction(tmp_path, item):
    rpc = RPC()
    rpc.added = item
    transport = backend(rpc)
    transport.inspect(runtime(tmp_path), THREAD, capability())
    with pytest.raises(DeliveryError, match="response_unknown"):
        transport.enqueue(runtime(tmp_path), THREAD, POINTER, COMMAND, before_send=lambda: None)
    assert len([method for method, _ in rpc.calls if method == "thread/queue/add"]) == 1


def proxy_fixture(monkeypatch, tmp_path, response, *, timeout=1):
    """Actual bounded pipe IO to a fake proxy process; never invoke native Codex."""
    original = subprocess.Popen
    code = ("import sys,json,time\n"
            "for line in sys.stdin:\n"
            " x=json.loads(line)\n"
            " if x.get('method')=='initialize': print(json.dumps({'id':x['id'],'result':{}}),flush=True)\n"
            " elif 'id' in x:\n" + response + "\n")
    def launch(argv, **kwargs):
        assert argv[1:] == ["app-server", "proxy", "--sock", str(tmp_path / "app.sock")]
        return original([sys.executable, "-u", "-c", code], **kwargs)
    monkeypatch.setattr(subprocess, "Popen", launch)
    return ProxyRPC(runtime(tmp_path), Path(sys.executable), timeout=timeout, verify=lambda _: None)


def test_proxy_distinguishes_notifications_from_correlated_responses(monkeypatch, tmp_path):
    response = "  print(json.dumps({'method':'thread/tokenUsage/updated','params':{}}),flush=True)\n" \
               "  print(json.dumps({'id':x['id'],'result':{'data':[]}}),flush=True)"
    with proxy_fixture(monkeypatch, tmp_path, response) as rpc:
        assert rpc.call("thread/queue/list", {"threadId": THREAD}) == {"data": []}


@pytest.mark.parametrize("response,error", [
    ("  print(json.dumps({'id':x['id'],'method':'item/commandExecution/requestApproval','params':{}}),flush=True)",
     "server_request"),
    ("  print(json.dumps({'id':999,'result':{}}),flush=True)", "uncorrelated"),
    ("  print(json.dumps({'id':x['id'],'error':{'code':-1}}),flush=True)", "rejected_unknown"),
    ("  print(json.dumps({'id':x['id'],'result':[]}),flush=True)", "malformed_RPC_result"),
    ("  print('not-json',flush=True)", "malformed_RPC_message"),
    ("  print('x'*1100000,flush=True)", "output_budget"),
    ("  sys.exit(0)", "EOF_unknown"),
    ("  time.sleep(1)", "timeout_unknown"),
    ("  print(json.dumps({'method':'thread/settings/updated','params':{}}),flush=True)", "runtime_changed"),
])
def test_proxy_failure_never_answers_approval_or_falls_back(monkeypatch, tmp_path, response, error):
    with proxy_fixture(monkeypatch, tmp_path, response, timeout=0.3) as rpc:
        with pytest.raises(DeliveryError, match=error):
            rpc.call("thread/queue/list", {"threadId": THREAD})
    assert rpc.process.poll() is not None


@pytest.mark.parametrize("method", ["thread/resume", "thread/queue/start", "turn/start", "thread/list",
                                    "thread/settings/update", "turn/interrupt", "config/read"])
def test_proxy_method_allowlist(tmp_path, method):
    rpc = ProxyRPC(runtime(tmp_path), Path(sys.executable))
    with pytest.raises(DeliveryError, match="allowlisted"):
        rpc.call(method, {"threadId": THREAD})
    rpc.close()


def test_runtime_missing_socket_and_wrong_binding_fail_closed(tmp_path):
    with pytest.raises(DeliveryError, match="runtime_evidence_unavailable"):
        verify_runtime(runtime(tmp_path))
    with pytest.raises(DeliveryError, match="explicit canonical"):
        replace(runtime(tmp_path), socket_path="relative.sock")


def test_actual_unix_peer_and_process_digest_are_checked(tmp_path, monkeypatch):
    # Container images need not contain a machine-id. Keep that input deterministic
    # while exercising the actual Unix peer, /proc process and executable digest.
    original_read = Path.read_text
    def read_identity(path, *args, **kwargs):
        if path == Path("/etc/machine-id"):
            return "fixture-machine-id\n"
        if path == Path("/proc/sys/kernel/random/boot_id"):
            return str(UUID(int=3)) + "\n"
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read_identity)
    path = tmp_path / "actual.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        listener.listen(8)
        info = path.stat()
        ticks = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
        binding = replace(runtime(tmp_path), socket_path=str(path),
                          host_id=Path("/etc/machine-id").read_text().strip(),
                          boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                          server_pid=os.getpid(), server_start_ticks=ticks,
                          socket_device=info.st_dev, socket_inode=info.st_ino)
        verify_runtime(binding)
        for changed, reason in [(replace(binding, server_pid=os.getpid() + 1), "peer_changed"),
                                (replace(binding, server_start_ticks=ticks + 1), "process_replaced"),
                                (replace(binding, executable_digest="a" * 64), "changed_runtime"),
                                (replace(binding, socket_inode=info.st_ino + 1), "socket_identity_changed")]:
            with pytest.raises(DeliveryError, match=reason):
                verify_runtime(changed)


@pytest.mark.parametrize("missing", ["/etc/machine-id", "/proc/sys/kernel/random/boot_id"])
def test_production_refuses_missing_host_identity_evidence(tmp_path, monkeypatch, missing):
    original_read = Path.read_text
    def read_identity(path, *args, **kwargs):
        if path == Path(missing):
            raise FileNotFoundError(missing)
        if path == Path("/etc/machine-id"):
            return "test-host\n"
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read_identity)
    path = tmp_path / "app.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        info = path.stat()
        binding = replace(runtime(tmp_path), socket_device=info.st_dev, socket_inode=info.st_ino)
        with pytest.raises(DeliveryError, match="runtime_evidence_unavailable"):
            verify_runtime(binding)


def test_final_dispatch_guard_runs_after_transport_inspection(tmp_path):
    rpc = RPC()
    transport = backend(rpc)
    binding = runtime(tmp_path)
    transport.inspect(binding, THREAD, capability())
    def revoked():
        raise DeliveryError("stale_notifier_lease")
    with pytest.raises(DeliveryError, match="stale_notifier_lease"):
        transport.enqueue(binding, THREAD, POINTER, COMMAND, before_send=revoked)
    assert not any(method == "thread/queue/add" for method, _ in rpc.calls)
