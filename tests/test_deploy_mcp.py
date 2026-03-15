"""Unit tests for scripts/deploy_mcp.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy_mcp.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _fake_docker_script() -> str:
    return """#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
    exit 1
fi

printf '%s\\n' "$*" >> "${FAKE_DOCKER_LOG:?}"

case "$1" in
    compose)
        shift
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --profile)
                    shift 2
                    ;;
                version|config|up|ps)
                    exit 0
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        exit 0
        ;;
    inspect)
        service="${4:-}"
        case "$service" in
            codex-second-opinion-secrets)
                printf '%s\\n' "${FAKE_SECOND_OPINION_STATUS:-running}"
                ;;
            codex-woodpecker-secrets)
                printf '%s\\n' "${FAKE_WOODPECKER_STATUS:-running}"
                ;;
            *)
                printf '%s\\n' "running"
                ;;
        esac
        ;;
    logs)
        printf '%s\\n' "${FAKE_DOCKER_LOG_OUTPUT:-CredentialsNotLoaded}"
        ;;
    image)
        exit 0
        ;;
esac
"""


def test_deploy_mcp_fails_when_selected_sidecar_restarts(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_log = tmp_path / "docker.log"

    _write_executable(fake_bin / "docker", _fake_docker_script())

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["PROFILE"] = "core"
    env["SIDECAR_GRACE_SECONDS"] = "0"
    env["FAKE_DOCKER_LOG"] = str(fake_log)
    env["FAKE_SECOND_OPINION_STATUS"] = "restarting"
    env["FAKE_DOCKER_LOG_OUTPUT"] = "CredentialsNotLoaded"

    result = subprocess.run(
        [str(SCRIPT), "--skip-smoke"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3
    assert "not running" in result.stdout
    assert "CredentialsNotLoaded" in result.stdout


def test_deploy_mcp_succeeds_when_selected_sidecars_are_running(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_log = tmp_path / "docker.log"

    _write_executable(fake_bin / "docker", _fake_docker_script())

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["PROFILE"] = "core legacy-cicd"
    env["SIDECAR_GRACE_SECONDS"] = "0"
    env["FAKE_DOCKER_LOG"] = str(fake_log)
    env["FAKE_SECOND_OPINION_STATUS"] = "running"
    env["FAKE_WOODPECKER_STATUS"] = "running"

    result = subprocess.run(
        [str(SCRIPT), "--skip-smoke"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Deploy complete." in result.stdout
