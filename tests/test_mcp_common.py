"""Unit tests for scripts/mcp_common.py helpers."""

from __future__ import annotations

import sys
from pathlib import Path

# Import from scripts/ to test operational helpers without packaging changes.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_common import (  # type: ignore[import-not-found]  # noqa: E402
    extract_directory_from_args,
    load_mcp_servers_from_toml,
    parse_profiles,
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
