"""Secret contract coverage for dockerized MCP services."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Literal

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
ROOT_COMPOSE = ROOT / "docker-compose.yml"
SECOND_OPINION_COMPOSE = ROOT / "codex-second-opinion" / "deploy" / "docker-compose.yml"


def _compose_env(service: dict) -> dict[str, str]:
    raw = service.get("environment", [])
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}

    env: dict[str, str] = {}
    for entry in raw:
        key, value = str(entry).split("=", 1)
        env[key] = value
    return env


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _service_volumes(service: dict) -> list[str]:
    raw = service.get("volumes", [])
    return [str(entry) for entry in raw]


class _FakeResponse:
    def __init__(self, payload: str) -> None:
        self._payload = payload.encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False

    def read(self) -> bytes:
        return self._payload


def test_root_compose_uses_agent_sidecars_for_secret_consumers() -> None:
    compose = yaml.safe_load(ROOT_COMPOSE.read_text())
    services = compose["services"]

    assert "codex-second-opinion-secrets" in services
    assert "codex-woodpecker-secrets" in services

    second_env = _compose_env(services["codex-second-opinion"])
    woodpecker_env = _compose_env(services["codex-woodpecker"])

    assert second_env["AWS_SECRET_SOURCE"] == "aws-secretsmanager-agent"
    assert second_env["AWS_SECRETSMANAGER_AGENT_ENDPOINT"] == "http://127.0.0.1:2773"
    assert second_env["AWS_SECRETSMANAGER_AGENT_ATTEMPTS"] == "${AWS_SECRETSMANAGER_AGENT_ATTEMPTS:-30}"
    assert second_env["AWS_SECRETSMANAGER_AGENT_RETRY_DELAY"] == "${AWS_SECRETSMANAGER_AGENT_RETRY_DELAY:-1}"
    assert second_env["AWS_API_KEYS_SECRET_NAME"] == "${AWS_API_KEYS_SECRET_NAME:-codex_llm_apikeys}"
    assert "AWS_ACCESS_KEY_ID" not in second_env
    assert "AWS_SECRET_ACCESS_KEY" not in second_env
    assert "AWS_SESSION_TOKEN" not in second_env

    assert woodpecker_env["AWS_SECRET_SOURCE"] == "aws-secretsmanager-agent"
    assert woodpecker_env["AWS_SECRETSMANAGER_AGENT_ENDPOINT"] == "http://127.0.0.1:2773"
    assert woodpecker_env["AWS_SECRETSMANAGER_AGENT_ATTEMPTS"] == "${AWS_SECRETSMANAGER_AGENT_ATTEMPTS:-30}"
    assert woodpecker_env["AWS_SECRETSMANAGER_AGENT_RETRY_DELAY"] == "${AWS_SECRETSMANAGER_AGENT_RETRY_DELAY:-1}"
    assert "AWS_ACCESS_KEY_ID" not in woodpecker_env
    assert "AWS_SECRET_ACCESS_KEY" not in woodpecker_env
    assert "AWS_SESSION_TOKEN" not in woodpecker_env

    second_sidecar = services["codex-second-opinion-secrets"]
    woodpecker_sidecar = services["codex-woodpecker-secrets"]
    assert second_sidecar["network_mode"] == "service:codex-second-opinion"
    assert woodpecker_sidecar["network_mode"] == "service:codex-woodpecker"
    second_sidecar_env = _compose_env(second_sidecar)
    woodpecker_sidecar_env = _compose_env(woodpecker_sidecar)
    assert second_sidecar_env["AWS_TOKEN"].startswith("${AWS_SECRETSMANAGER_TOKEN:")
    assert second_sidecar_env["HOME"] == "/root"
    assert second_sidecar_env["AWS_PROFILE"] == "${AWS_PROFILE:-default}"
    assert second_sidecar_env["AWS_SDK_LOAD_CONFIG"] == "1"
    assert second_sidecar_env["AWS_SHARED_CREDENTIALS_FILE"] == "/root/.aws/credentials"
    assert second_sidecar_env["AWS_CONFIG_FILE"] == "/root/.aws/config"
    assert "${HOME}/.aws:/root/.aws:ro" in _service_volumes(second_sidecar)
    assert woodpecker_sidecar_env["AWS_TOKEN"].startswith("${AWS_SECRETSMANAGER_TOKEN:")
    assert woodpecker_sidecar_env["HOME"] == "/root"
    assert woodpecker_sidecar_env["AWS_PROFILE"] == "${AWS_PROFILE:-default}"
    assert woodpecker_sidecar_env["AWS_SDK_LOAD_CONFIG"] == "1"
    assert woodpecker_sidecar_env["AWS_SHARED_CREDENTIALS_FILE"] == "/root/.aws/credentials"
    assert woodpecker_sidecar_env["AWS_CONFIG_FILE"] == "/root/.aws/config"
    assert "${HOME}/.aws:/root/.aws:ro" in _service_volumes(woodpecker_sidecar)


def test_second_opinion_service_compose_uses_agent_sidecar() -> None:
    compose = yaml.safe_load(SECOND_OPINION_COMPOSE.read_text())
    services = compose["services"]

    app_env = _compose_env(services["second-opinion-mcp"])
    sidecar_env = _compose_env(services["second-opinion-secrets"])

    assert app_env["AWS_SECRET_SOURCE"] == "aws-secretsmanager-agent"
    assert app_env["AWS_SECRETSMANAGER_AGENT_ENDPOINT"] == "http://127.0.0.1:2773"
    assert app_env["AWS_SECRETSMANAGER_AGENT_ATTEMPTS"] == "${AWS_SECRETSMANAGER_AGENT_ATTEMPTS:-30}"
    assert app_env["AWS_SECRETSMANAGER_AGENT_RETRY_DELAY"] == "${AWS_SECRETSMANAGER_AGENT_RETRY_DELAY:-1}"
    assert services["second-opinion-secrets"]["network_mode"] == "service:second-opinion-mcp"
    assert sidecar_env["AWS_TOKEN"].startswith("${AWS_SECRETSMANAGER_TOKEN:")
    assert sidecar_env["HOME"] == "/root"
    assert sidecar_env["AWS_PROFILE"] == "${AWS_PROFILE:-default}"
    assert sidecar_env["AWS_SDK_LOAD_CONFIG"] == "1"
    assert sidecar_env["AWS_SHARED_CREDENTIALS_FILE"] == "/root/.aws/credentials"
    assert sidecar_env["AWS_CONFIG_FILE"] == "/root/.aws/config"
    assert "${HOME}/.aws:/root/.aws:ro" in _service_volumes(services["second-opinion-secrets"])


@pytest.mark.parametrize(
    ("module_path", "default_secret_name", "contract_keys"),
    [
        (
            ROOT / "codex-second-opinion" / "src" / "aws_secrets.py",
            "codex_llm_apikeys",
            ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
        ),
        (
            ROOT / "codex-woodpecker" / "src" / "aws_secrets.py",
            "codex-power-pack",
            ("WOODPECKER_HOST", "WOODPECKER_API_TOKEN"),
        ),
    ],
)
def test_agent_loader_and_contract_constants(
    monkeypatch: pytest.MonkeyPatch,
    module_path: Path,
    default_secret_name: str,
    contract_keys: tuple[str, ...],
) -> None:
    module = _load_module(module_path.stem, module_path)

    monkeypatch.setenv("AWS_SECRET_SOURCE", "aws-secretsmanager-agent")
    monkeypatch.setenv("AWS_SECRETSMANAGER_AGENT_ENDPOINT", "http://127.0.0.1:2773")
    monkeypatch.setenv("AWS_SECRETSMANAGER_TOKEN", "dev-token")

    expected_payload = {
        key: f"value-{index}"
        for index, key in enumerate(contract_keys, start=1)
    }

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith("http://127.0.0.1:2773/secretsmanager/get?secretId=")
        assert request.get_header("X-aws-parameters-secrets-token") == "dev-token"
        assert timeout == module.DEFAULT_AGENT_TIMEOUT
        payload = json.dumps({"SecretString": json.dumps(expected_payload)})
        return _FakeResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    resolved = module.resolve_secret(default_secret_name, "us-east-1")
    assert module.DEFAULT_SECRET_NAME == default_secret_name
    assert module.SECRET_CONTRACT_KEYS == contract_keys
    assert resolved == expected_payload
