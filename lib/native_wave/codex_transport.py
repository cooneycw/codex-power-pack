"""Bounded 0.154.0 local proxy operations; unavailable evidence never enables work."""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import socket
import stat
import struct
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from .delivery_types import DeliveryError, QueueEvidence, RuntimeBinding, RuntimeObservation, encode
from .types import CapabilitySnapshot

MAX_BYTES = 1_048_576
METHODS = frozenset({"thread/read", "thread/turns/list", "thread/items/list",
                     "thread/queue/add", "thread/queue/list"})


def verify_runtime(binding: RuntimeBinding) -> None:
    """Check the local endpoint's actual Unix peer, not its filename or userAgent."""
    try:
        path = Path(binding.socket_path)
        info = path.lstat()
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid()
                or (info.st_dev, info.st_ino) != (binding.socket_device, binding.socket_inode)):
            raise DeliveryError("socket_identity_changed")
        if Path("/etc/machine-id").read_text().strip() != binding.host_id:
            raise DeliveryError("wrong_host")
        if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != binding.boot_id:
            raise DeliveryError("wrong_boot")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(1)
            peer.connect(binding.socket_path)
            pid, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if pid != binding.server_pid or uid != os.getuid():
            raise DeliveryError("socket_peer_changed")
        process = Path(f"/proc/{pid}")
        # comm may contain spaces and parentheses; starttime is field 22.
        ticks = int((process / "stat").read_text().rsplit(")", 1)[1].split()[19])
        if ticks != binding.server_start_ticks:
            raise DeliveryError("server_process_replaced")
        with (process / "exe").open("rb") as executable:
            checksum = hashlib.file_digest(executable, "sha256").hexdigest()
        if checksum != binding.executable_digest or binding.cli_version != "0.154.0":
            raise DeliveryError("unsupported_or_changed_runtime")
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise DeliveryError("socket_replaced_during_validation")
    except (OSError, ValueError) as exc:
        raise DeliveryError("runtime_evidence_unavailable") from exc


class ProxyRPC:
    """One explicit proxy, one deadline and total byte budget including notifications."""

    def __init__(self, runtime: RuntimeBinding, executable: Path, *, timeout: float = 10,
                 verify: Callable[[RuntimeBinding], None] = verify_runtime) -> None:
        if not 0 < timeout <= 10:
            raise DeliveryError("RPC deadline must be at most ten seconds")
        self.runtime, self.executable, self.verify = runtime, executable, verify
        self.deadline = time.monotonic() + timeout
        self.buffer = b""
        self.total = 0
        self.serial = 0
        self.process: subprocess.Popen[bytes] | None = None
        self.selector = selectors.DefaultSelector()

    def __enter__(self) -> ProxyRPC:
        self.verify(self.runtime)
        try:
            if not self.executable.is_absolute():
                raise DeliveryError("proxy executable must be explicit")
            with self.executable.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != self.runtime.executable_digest:
                    raise DeliveryError("proxy executable differs from pinned server")
            self.process = subprocess.Popen(
                [str(self.executable), "app-server", "proxy", "--sock", self.runtime.socket_path],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            assert self.process.stdout is not None
            assert self.process.stdin is not None
            os.set_blocking(self.process.stdin.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self._request("initialize", {"clientInfo": {"name": "cxpp_delivery", "version": "1"},
                                         "capabilities": {"experimentalApi": True}})
            self._send({"method": "initialized"})
            return self
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        self.selector.close()
        if self.process is not None:
            # Only the proxy child belongs to us. Never signal the server or recipient.
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    stream.close()

    def __exit__(self, *args: object) -> None:
        self.close()

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process is not None and self.process.stdin is not None
        data = (encode(message) + "\n").encode()
        if len(data) > 8192 or time.monotonic() >= self.deadline:
            raise DeliveryError("RPC input or deadline budget exceeded")
        try:
            with selectors.DefaultSelector() as writer:
                writer.register(self.process.stdin, selectors.EVENT_WRITE)
                while data:
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0 or not writer.select(remaining):
                        raise DeliveryError("RPC_write_timeout_unknown")
                    try:
                        data = data[os.write(self.process.stdin.fileno(), data):]
                    except BlockingIOError:
                        continue
        except OSError as exc:
            raise DeliveryError("proxy_write_unknown") from exc

    def _line(self) -> dict[str, Any]:
        assert self.process is not None and self.process.stdout is not None
        while b"\n" not in self.buffer:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise DeliveryError("RPC_timeout_unknown")
            block = os.read(self.process.stdout.fileno(), 65536)
            if not block:
                raise DeliveryError("proxy_EOF_unknown")
            self.total += len(block)
            if self.total > MAX_BYTES:
                raise DeliveryError("RPC_output_budget_exceeded")
            self.buffer += block
        raw, self.buffer = self.buffer.split(b"\n", 1)
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("not an object")
            return value
        except (ValueError, UnicodeError) as exc:
            raise DeliveryError("malformed_RPC_message") from exc

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.serial += 1
        self._send({"id": self.serial, "method": method, "params": params})
        for _ in range(128):
            message = self._line()
            if "method" in message:
                if "id" in message:
                    # This is a server request (possibly approval), never an RPC response.
                    raise DeliveryError("server_request_requires_independent_agent_action")
                if message["method"] in {"thread/settings/updated", "thread/status/changed"}:
                    raise DeliveryError("runtime_changed_during_RPC")
                continue
            if type(message.get("id")) is not int or message["id"] != self.serial:
                raise DeliveryError("uncorrelated_RPC_response")
            if "error" in message:
                raise DeliveryError("RPC_rejected_unknown_delivery")
            if not isinstance(message.get("result"), dict):
                raise DeliveryError("malformed_RPC_result")
            return dict(message["result"])
        raise DeliveryError("RPC_notification_budget_exceeded")

    def call(self, method: str, params: dict[str, Any],
             *, before_send: Callable[[], None] | None = None) -> dict[str, Any]:
        if method not in METHODS:
            raise DeliveryError("method_not_allowlisted")
        thread = params.get("threadId")
        if not isinstance(thread, str) or str(UUID(thread)) != thread:
            raise DeliveryError("exact_thread_UUID_required")
        self.verify(self.runtime)
        if before_send is not None:
            before_send()
        result = self._request(method, params)
        self.verify(self.runtime)
        return result


class CodexTransport:
    """Native inspection currently refuses dispatch without a current permission oracle.

    0.154.0 thread/read has no resolved permissions. A historical capability or a
    profile name does not fill that gap. No resume/settings mutation is used to
    obtain evidence. The injected oracle is a port for deterministic fixtures and
    a future reviewed native source; the CLI provides no override to bypass it.
    """

    def __init__(self, executable: Path, *, rpc_factory: Callable[..., Any] = ProxyRPC,
                 permissions: Callable[[RuntimeBinding, str, CapabilitySnapshot], bool] | None = None) -> None:
        self.executable, self.rpc_factory, self.permissions = executable, rpc_factory, permissions
        self.eligible: tuple[RuntimeBinding, str, CapabilitySnapshot] | None = None

    def inspect(self, runtime: RuntimeBinding, thread: str, capability: CapabilitySnapshot) -> RuntimeObservation:
        self.eligible = None
        with self.rpc_factory(runtime, self.executable) as rpc:
            record = rpc.call("thread/read", {"threadId": thread, "includeTurns": False}).get("thread", {})
            if record.get("id") != thread:
                raise DeliveryError("thread_response_mismatch")
            status = record.get("status", {})
            state = status.get("type")
            if state == "notLoaded":
                return RuntimeObservation("unloaded", "resume may execute before permission inspection")
            if state not in {"idle", "active"}:
                return RuntimeObservation("unknown", "no supported current thread status")
            flags = status.get("activeFlags")
            if state == "active" and flags != []:
                return RuntimeObservation("approval_or_input_waiting" if flags else "unknown")
            if (record.get("canAcceptDirectInput") is not True or record.get("ephemeral") is not False
                    or record.get("parentThreadId") is not None
                    or record.get("source") not in ("cli", "exec", "appServer")):
                return RuntimeObservation("origin_restricted")
            if (record.get("model") != capability.model or record.get("reasoningEffort") != capability.reasoning_effort
                    or record.get("cwd") not in capability.workspace_roots
                    or runtime.cli_version != capability.cli_version):
                return RuntimeObservation("profile_changed_or_unknown")
            turns = rpc.call("thread/turns/list", {"threadId": thread, "limit": 1, "sortDirection": "desc"})
            latest = turns.get("data")
            if not isinstance(latest, list) or not latest:
                return RuntimeObservation("history_unavailable")
            turn_state = latest[0].get("status")
            if turn_state == "interrupted":
                return RuntimeObservation("interrupted", "idle is not permission to restart interrupted work")
            if turn_state not in {"completed", "inProgress"}:
                return RuntimeObservation("history_unavailable")
            if self.permissions is None or not self.permissions(runtime, thread, capability):
                return RuntimeObservation("permissions_unverified")
            self.eligible = runtime, thread, capability
            return RuntimeObservation("idle" if state == "idle" else "busy")

    @staticmethod
    def _matches(item: dict[str, Any], pointer: str, command_id: str) -> bool:
        if not isinstance(item, dict):
            return False
        content = item.get("input", item.get("content"))
        return (item.get("clientUserMessageId", item.get("clientId")) == command_id and isinstance(content, list)
                and len(content) == 1 and isinstance(content[0], dict)
                and content[0].get("type") == "text" and content[0].get("text") == pointer)

    def enqueue(self, runtime: RuntimeBinding, thread: str, pointer: str, command_id: str,
                *, before_send: Callable[[], None]) -> str:
        if self.eligible is None or self.eligible[:2] != (runtime, thread):
            raise DeliveryError("dispatch_requires_current_inspection")
        capability = self.eligible[2]
        # A new inspection invalidates the previous authorization on any failure.
        if self.inspect(runtime, thread, capability).state not in {"idle", "busy"}:
            raise DeliveryError("dispatch_eligibility_changed")
        self.eligible = None
        with self.rpc_factory(runtime, self.executable) as rpc:
            item = rpc.call("thread/queue/add", {"threadId": thread, "clientUserMessageId": command_id,
                                                "input": [{"type": "text", "text": pointer}]},
                            before_send=before_send).get("queuedSubmission")
            if not isinstance(item, dict) or not self._matches(item, pointer, command_id) or not item.get("id"):
                raise DeliveryError("queue_acceptance_response_unknown")
            return str(item["id"])

    def reconcile(self, runtime: RuntimeBinding, thread: str, pointer: str, command_id: str) -> QueueEvidence:
        with self.rpc_factory(runtime, self.executable) as rpc:
            cursor = None
            for _ in range(3):
                params: dict[str, Any] = {"threadId": thread, "limit": 50}
                if cursor is not None:
                    params["cursor"] = cursor
                page = rpc.call("thread/queue/list", params)
                entries = page.get("data")
                if not isinstance(entries, list) or len(entries) > 50:
                    raise DeliveryError("invalid_queue_page")
                for item in entries:
                    if self._matches(item, pointer, command_id) and isinstance(item.get("id"), str):
                        return QueueEvidence("queued", item["id"])
                cursor = page.get("nextCursor")
                if cursor is None:
                    break
            # Only positive, fully correlated history is evidence of a start.
            page = rpc.call("thread/items/list", {"threadId": thread, "limit": 50, "sortDirection": "desc"})
            items = page.get("data")
            if not isinstance(items, list) or len(items) > 50:
                raise DeliveryError("invalid_history_page")
            if any(isinstance(entry, dict) and isinstance(entry.get("item"), dict)
                   and entry["item"].get("type") == "userMessage"
                   and self._matches(entry["item"], pointer, command_id) for entry in items):
                return QueueEvidence("started")
            # Offset pagination, removed items and missing client ids cannot prove absence.
            return QueueEvidence("unknown")
