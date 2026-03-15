"""AWS Secrets Manager resolution helpers for docker sidecars and native runs."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict

DEFAULT_SECRET_NAME = "codex-power-pack"
SECRET_CONTRACT_KEYS = ("WOODPECKER_HOST", "WOODPECKER_API_TOKEN")
DEFAULT_SECRET_SOURCE = "auto"
AGENT_SECRET_SOURCE = "aws-secretsmanager-agent"
DEFAULT_AGENT_ENDPOINT = "http://127.0.0.1:2773"
DEFAULT_AGENT_TIMEOUT = 5.0
DEFAULT_AGENT_ATTEMPTS = 10
DEFAULT_AGENT_RETRY_DELAY = 0.5

logger = logging.getLogger(__name__)

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[assignment]


def _agent_enabled(source: str, token: str) -> bool:
    if source in {AGENT_SECRET_SOURCE, "agent"}:
        return True
    return source == DEFAULT_SECRET_SOURCE and bool(token)


def _agent_endpoint() -> str:
    return os.getenv("AWS_SECRETSMANAGER_AGENT_ENDPOINT", DEFAULT_AGENT_ENDPOINT).rstrip("/")


def _agent_token() -> str:
    return os.getenv("AWS_SECRETSMANAGER_TOKEN", os.getenv("AWS_TOKEN", ""))


def _agent_attempts() -> int:
    raw = os.getenv("AWS_SECRETSMANAGER_AGENT_ATTEMPTS", str(DEFAULT_AGENT_ATTEMPTS))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_AGENT_ATTEMPTS


def _agent_retry_delay() -> float:
    raw = os.getenv("AWS_SECRETSMANAGER_AGENT_RETRY_DELAY", str(DEFAULT_AGENT_RETRY_DELAY))
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_AGENT_RETRY_DELAY


def _agent_timeout() -> float:
    raw = os.getenv("AWS_SECRETSMANAGER_AGENT_TIMEOUT", str(DEFAULT_AGENT_TIMEOUT))
    try:
        return max(0.1, float(raw))
    except ValueError:
        return DEFAULT_AGENT_TIMEOUT


def _resolve_via_agent(secret_name: str) -> Dict[str, str]:
    token = _agent_token()
    if not token:
        return {}

    endpoint = _agent_endpoint()
    secret_id = urllib.parse.quote(secret_name, safe="")
    url = f"{endpoint}/secretsmanager/get?secretId={secret_id}"
    request = urllib.request.Request(
        url,
        headers={"X-Aws-Parameters-Secrets-Token": token},
    )

    attempts = _agent_attempts()
    retry_delay = _agent_retry_delay()
    timeout = _agent_timeout()

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            secret_string = payload.get("SecretString", "{}")
            data = json.loads(secret_string)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if v is not None}
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            if attempt == attempts:
                logger.warning(
                    "Could not fetch AWS secret '%s' from sidecar agent at %s: %s",
                    secret_name,
                    endpoint,
                    exc,
                )
                break
            time.sleep(retry_delay)

    return {}


def _resolve_via_boto3(secret_name: str, region: str) -> Dict[str, str]:
    if not secret_name or boto3 is None:
        return {}

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        payload = response.get("SecretString", "{}")
        data = json.loads(payload)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if v is not None}
    except Exception as exc:
        logger.warning("Could not fetch AWS secret '%s': %s", secret_name, exc)

    return {}


def resolve_secret(secret_name: str, region: str) -> Dict[str, str]:
    """Resolve a JSON secret through the agent sidecar or boto3."""
    if not secret_name:
        return {}

    source = os.getenv("AWS_SECRET_SOURCE", DEFAULT_SECRET_SOURCE).strip().lower()
    token = _agent_token()
    if _agent_enabled(source, token):
        values = _resolve_via_agent(secret_name)
        if values or source in {AGENT_SECRET_SOURCE, "agent"}:
            return values

    return _resolve_via_boto3(secret_name, region)
