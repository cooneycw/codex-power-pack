"""Unit tests for scripts/deploy_doctor.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from deploy_doctor import (  # type: ignore[import-not-found]  # noqa: E402
    build_parser,
    inspect_unit,
    inspect_wrapper,
)


def test_build_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.repo_root == "."
    assert args.json is False


def test_inspect_unit_accepts_provisioning_only_bootstrap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    unit_path = tmp_path / "woodpecker-bootstrap.service"
    unit_path.write_text(
        "[Service]\n"
        f"ExecStart=/usr/bin/python3 {repo_root}/woodpecker/bootstrap-secrets.py\n",
        encoding="utf-8",
    )

    result = inspect_unit(unit_path, repo_root)
    assert result.status == "ok"
    assert "Provisioning-only" in result.detail


def test_inspect_unit_flags_runtime_command_in_provisioning_unit(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    unit_path = tmp_path / "woodpecker-bootstrap.service"
    unit_path.write_text(
        "[Service]\nExecStart=/usr/local/bin/deploy-mcp --profile core\n",
        encoding="utf-8",
    )

    result = inspect_unit(unit_path, repo_root)
    assert result.status == "drift"
    assert "Provisioning-only unit runs runtime command" in result.detail


def test_inspect_unit_accepts_repo_owned_runtime_command(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    unit_path = tmp_path / "deploy-mcp.service"
    unit_path.write_text(
        "[Service]\n"
        f"ExecStart={repo_root}/scripts/deploy_mcp.sh --profiles \"core browser\"\n",
        encoding="utf-8",
    )

    result = inspect_unit(unit_path, repo_root)
    assert result.status == "ok"
    assert "repo-owned entrypoint" in result.detail


def test_inspect_wrapper_flags_stale_runtime_logic(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    canonical = repo_root / "scripts" / "deploy_mcp.sh"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("#!/bin/sh\n", encoding="utf-8")

    wrapper = tmp_path / "cpp-deploy-mcp"
    wrapper.write_text("#!/bin/sh\ndocker compose up -d --build --wait\n", encoding="utf-8")

    result = inspect_wrapper(wrapper, repo_root, canonical)
    assert result.status == "drift"
    assert "outside the repo checkout" in result.detail
