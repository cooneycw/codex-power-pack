#!/usr/bin/env python3
"""Shared MCP utilities for Codex Power Pack operational scripts."""

from __future__ import annotations

import json
import socket
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_PROTOCOL_VERSION = "2024-11-05"


@dataclass(frozen=True)
class ServerSpec:
    """Canonical MCP server metadata."""

    config_name: str
    profile: str
    sse_url: str
    repo_subdir: str

    @property
    def stdio_args(self) -> list[str]:
        return ["run", "--directory", self.repo_subdir, "python", "src/server.py", "--stdio"]


@dataclass
class ProbeResult:
    """Result of probing an MCP SSE endpoint."""

    config_name: str
    sse_url: str
    ok: bool
    stage: str
    endpoint: str | None = None
    protocol_version: str | None = None
    server_name: str | None = None
    server_version: str | None = None
    error: str | None = None


def canonical_servers() -> list[ServerSpec]:
    """Return canonical Codex Power Pack MCP server definitions."""
    return [
        ServerSpec(
            config_name="codex-second-opinion",
            profile="core",
            sse_url="http://127.0.0.1:9100/sse",
            repo_subdir="codex-second-opinion",
        ),
        ServerSpec(
            config_name="codex-nano-banana",
            profile="core",
            sse_url="http://127.0.0.1:9102/sse",
            repo_subdir="codex-nano-banana",
        ),
        ServerSpec(
            config_name="codex-playwright",
            profile="browser",
            sse_url="http://127.0.0.1:9101/sse",
            repo_subdir="codex-playwright",
        ),
        ServerSpec(
            config_name="codex-woodpecker",
            profile="cicd",
            sse_url="http://127.0.0.1:9103/sse",
            repo_subdir="codex-woodpecker",
        ),
    ]


def parse_profiles(raw: str | None) -> set[str]:
    """Parse profile string (`core browser` or `core,browser`) into a set."""
    if not raw:
        return {"core"}
    normalized = raw.replace(",", " ")
    values = {token.strip() for token in normalized.split() if token.strip()}
    return values or {"core"}


def selected_servers(profiles: set[str]) -> list[ServerSpec]:
    """Select canonical servers matching the requested profiles."""
    return [spec for spec in canonical_servers() if spec.profile in profiles]


def _read_sse_event(stream: Any, max_lines: int = 200) -> dict[str, str] | None:
    """Read one SSE event from a streaming response."""
    event_name: str | None = None
    data_lines: list[str] = []
    line_count = 0

    while line_count < max_lines:
        raw = stream.readline()
        if not raw:
            return None

        try:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        except AttributeError:
            line = str(raw).rstrip("\r\n")

        line_count += 1

        if line == "":
            if event_name is not None:
                return {"event": event_name, "data": "\n".join(data_lines)}
            event_name = None
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())

    return None


def probe_sse_server(spec: ServerSpec, timeout_seconds: float = 8.0, check_tools_list: bool = False) -> ProbeResult:
    """Probe an MCP server over SSE and validate JSON-RPC initialize."""
    headers = {"Accept": "text/event-stream"}

    try:
        with urlopen(Request(spec.sse_url, headers=headers, method="GET"), timeout=timeout_seconds) as stream:
            endpoint: str | None = None
            for _ in range(30):
                evt = _read_sse_event(stream)
                if not evt:
                    break
                if evt.get("event") == "endpoint":
                    payload = (evt.get("data") or "").strip()
                    endpoint = payload if payload.startswith("http") else urljoin(spec.sse_url, payload)
                    break

            if not endpoint:
                return ProbeResult(
                    config_name=spec.config_name,
                    sse_url=spec.sse_url,
                    ok=False,
                    stage="handshake",
                    error="No endpoint event received from SSE stream",
                )

            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "codex-power-pack", "version": "1.0"},
                },
            }

            post_data = json.dumps(init_payload).encode("utf-8")
            with urlopen(
                Request(endpoint, data=post_data, headers={"Content-Type": "application/json"}, method="POST"),
                timeout=timeout_seconds,
            ) as _:
                pass

            init_result: dict[str, Any] | None = None
            for _ in range(60):
                evt = _read_sse_event(stream)
                if not evt:
                    break
                data = (evt.get("data") or "").strip()
                if not data:
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if payload.get("id") == 1:
                    init_result = payload
                    break

            if not init_result or "result" not in init_result:
                return ProbeResult(
                    config_name=spec.config_name,
                    sse_url=spec.sse_url,
                    ok=False,
                    stage="handshake",
                    endpoint=endpoint,
                    error="Initialize response was not received",
                )

            if check_tools_list:
                tools_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
                with urlopen(
                    Request(
                        endpoint,
                        data=json.dumps(tools_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=timeout_seconds,
                ) as _:
                    pass

                tools_response: dict[str, Any] | None = None
                for _ in range(80):
                    evt = _read_sse_event(stream)
                    if not evt:
                        break
                    data = (evt.get("data") or "").strip()
                    if not data:
                        continue
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("id") == 2:
                        tools_response = payload
                        break

                if not tools_response or ("result" not in tools_response and "error" in tools_response):
                    return ProbeResult(
                        config_name=spec.config_name,
                        sse_url=spec.sse_url,
                        ok=False,
                        stage="tools",
                        endpoint=endpoint,
                        error="tools/list response was not received",
                    )

            server_info = (init_result.get("result", {}) or {}).get("serverInfo", {})
            return ProbeResult(
                config_name=spec.config_name,
                sse_url=spec.sse_url,
                ok=True,
                stage="ok",
                endpoint=endpoint,
                protocol_version=(init_result.get("result", {}) or {}).get("protocolVersion"),
                server_name=server_info.get("name"),
                server_version=server_info.get("version"),
            )

    except HTTPError as exc:
        return ProbeResult(
            config_name=spec.config_name,
            sse_url=spec.sse_url,
            ok=False,
            stage="endpoint",
            error=f"HTTP {exc.code}",
        )
    except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
        return ProbeResult(
            config_name=spec.config_name,
            sse_url=spec.sse_url,
            ok=False,
            stage="endpoint",
            error=str(exc),
        )
    except Exception as exc:  # pragma: no cover - last-resort guard
        return ProbeResult(
            config_name=spec.config_name,
            sse_url=spec.sse_url,
            ok=False,
            stage="handshake",
            error=str(exc),
        )


def load_mcp_servers_from_toml(config_path: Path) -> dict[str, dict[str, Any]]:
    """Load `[mcp_servers.*]` sections from a Codex config TOML file."""
    if not config_path.exists():
        return {}

    with config_path.open("rb") as handle:
        parsed = tomllib.load(handle)

    servers = parsed.get("mcp_servers", {})
    if isinstance(servers, dict):
        # narrow type for downstream usage
        return {str(key): value for key, value in servers.items() if isinstance(value, dict)}
    return {}


def extract_directory_from_args(args: Any) -> str | None:
    """Extract `--directory` path from a stdio args list."""
    if not isinstance(args, list):
        return None

    for index, value in enumerate(args):
        if value == "--directory" and index + 1 < len(args):
            candidate = args[index + 1]
            if isinstance(candidate, str):
                return candidate
    return None
