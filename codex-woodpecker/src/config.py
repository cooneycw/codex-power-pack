"""Configuration for the MCP Woodpecker CI server."""

import logging
import os

from aws_secrets import DEFAULT_SECRET_NAME, resolve_secret
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

_local_env_path = Path(__file__).parent.parent / ".env"
_root_env_path = Path(__file__).parent.parent.parent / ".env"
if _root_env_path.exists():
    load_dotenv(_root_env_path)
if _local_env_path.exists():
    load_dotenv(_local_env_path, override=True)


def _get_int_env(name: str, default: int) -> int:
    """Get an integer environment variable with validation."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_woodpecker_config() -> tuple[str, str]:
    """Resolve Woodpecker URL and API token from environment or AWS Secrets Manager.

    Priority:
    1. Direct environment variables (WOODPECKER_URL / WOODPECKER_API_TOKEN)
    2. AWS Secrets Manager (AWS_SECRET_NAME env var, default: codex-power-pack)
    """
    url = os.getenv("WOODPECKER_URL", "")
    token = os.getenv("WOODPECKER_API_TOKEN", "")

    if url and token:
        return url, token

    # Try AWS Secrets Manager
    secret_name = os.getenv("AWS_SECRET_NAME", DEFAULT_SECRET_NAME)
    region = os.getenv("AWS_REGION", "us-east-1")

    secrets = resolve_secret(secret_name, region)
    if secrets:
        if not url:
            url = secrets.get("WOODPECKER_HOST", "")
        if not token:
            token = secrets.get("WOODPECKER_API_TOKEN", "")

    return url, token


_wp_url, _wp_token = _resolve_woodpecker_config()


class Config:
    """Server configuration."""

    SERVER_NAME: str = "codex-woodpecker"
    SERVER_VERSION: str = "1.0.0"
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = _get_int_env("MCP_SERVER_PORT", 9103)

    WOODPECKER_URL: str = _wp_url
    WOODPECKER_API_TOKEN: str = _wp_token
