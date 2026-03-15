"""Unit tests for scripts/mcp_common.py helpers."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

# Import from scripts/ to test operational helpers without packaging changes.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_common import (  # type: ignore[import-not-found]  # noqa: E402
    ServerSpec,
    extract_directory_from_args,
    load_mcp_servers_from_toml,
    parse_profiles,
    probe_stdio_server,
    selected_servers,
)


def test_parse_profiles_supports_space_and_comma_delimiters() -> None:
    assert parse_profiles("core browser") == {"core", "browser"}
    assert parse_profiles("core,browser,cicd") == {"core", "browser", "cicd"}


def test_parse_profiles_defaults_to_core() -> None:
    assert parse_profiles(None) == {"core"}
    assert parse_profiles("") == {"core"}


def test_selected_servers_filters_by_profile() -> None:
    core_servers = {spec.config_name for spec in selected_servers({"core"})}
    assert core_servers == {"codex-second-opinion", "codex-nano-banana"}


def test_selected_servers_default_to_loopback_urls() -> None:
    urls = {spec.config_name: spec.sse_url for spec in selected_servers({"core", "browser", "cicd"})}
    assert urls["codex-second-opinion"] == "http://127.0.0.1:9100/sse"
    assert urls["codex-playwright"] == "http://127.0.0.1:9101/sse"
    assert urls["codex-nano-banana"] == "http://127.0.0.1:9102/sse"
    assert urls["codex-woodpecker"] == "http://127.0.0.1:9103/sse"


def test_selected_servers_support_service_dns_urls(monkeypatch) -> None:
    monkeypatch.setenv("MCP_SSE_HOST_MODE", "service")
    urls = {spec.config_name: spec.sse_url for spec in selected_servers({"core", "browser", "cicd"})}
    assert urls["codex-second-opinion"] == "http://codex-second-opinion:9100/sse"
    assert urls["codex-playwright"] == "http://codex-playwright:9101/sse"
    assert urls["codex-nano-banana"] == "http://codex-nano-banana:9102/sse"
    assert urls["codex-woodpecker"] == "http://codex-woodpecker:9103/sse"


def test_extract_directory_from_args() -> None:
    args = ["run", "--directory", "/tmp/example", "python", "src/server.py", "--stdio"]
    assert extract_directory_from_args(args) == "/tmp/example"
    assert extract_directory_from_args(["run", "python", "src/server.py"]) is None


def test_load_mcp_servers_from_toml(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
[mcp_servers.codex-second-opinion]
command = "uv"
args = ["run", "--directory", "/tmp/a", "python", "src/server.py", "--stdio"]

[mcp_servers.codex-second-opinion.env]
PYTHONUNBUFFERED = "1"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    servers = load_mcp_servers_from_toml(config)
    assert "codex-second-opinion" in servers
    assert servers["codex-second-opinion"]["command"] == "uv"


def test_probe_stdio_server_success(monkeypatch) -> None:
    class _FakeProcess:
        def __init__(self) -> None:
            self.stderr = StringIO("")
            self.terminated = False

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: float | None = None) -> int:
            assert self.terminated is True
            return 0

    fake_process = _FakeProcess()

    def _fake_popen(*args, **kwargs):  # type: ignore[no-untyped-def]
        return fake_process

    monkeypatch.setattr("mcp_common.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("mcp_common.time.sleep", lambda _: None)

    result = probe_stdio_server(
        ServerSpec(
            config_name="codex-woodpecker",
            profile="cicd",
            sse_url="http://127.0.0.1:9103/sse",
            repo_subdir="codex-woodpecker",
        )
    )

    assert result.ok is True
    assert result.stage == "ok"
    assert result.endpoint is not None
    assert "--stdio" in result.endpoint


def test_probe_stdio_server_early_exit(monkeypatch) -> None:
    class _FakeProcess:
        def __init__(self) -> None:
            self.stderr = StringIO("boom")

        def poll(self) -> int:
            return 1

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 1

    def _fake_popen(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeProcess()

    monkeypatch.setattr("mcp_common.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("mcp_common.time.sleep", lambda _: None)

    result = probe_stdio_server(
        ServerSpec(
            config_name="codex-woodpecker",
            profile="cicd",
            sse_url="http://127.0.0.1:9103/sse",
            repo_subdir="codex-woodpecker",
        )
    )

    assert result.ok is False
    assert result.stage == "startup"
    assert result.error is not None
    assert "exited early" in result.error
