"""Thin Codex hook adapters for friction telemetry."""

from __future__ import annotations

import json
from typing import Any, Mapping

from lib.creds.masking import OutputMasker

from .models import FrictionEvent, truncate


def load_payload(raw: str) -> dict[str, Any]:
    """Parse hook JSON defensively."""

    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def event_from_hook_payload(
    hook_event: str,
    payload: Mapping[str, Any],
    *,
    masker: OutputMasker | None = None,
) -> FrictionEvent | None:
    """Extract an allowlisted event from a raw Codex hook payload.

    Raw prompts, inputs, and outputs are never copied into the event. At most the
    adapter stores derived metadata such as tool name, exit code, and whether the
    masking layer detected a secret-shaped value.
    """

    event = hook_event.strip()
    tool_name = _tool_name(payload)
    repo = _optional_str(payload.get("repo") or payload.get("repository"))
    branch = _optional_str(payload.get("branch"))
    issue = payload.get("issue")

    if event == "PermissionRequest":
        return FrictionEvent.from_mapping({
            "event_type": "approval_prompt",
            "event_source": _source(event, tool_name),
            "severity": "info",
            "repo": repo,
            "branch": branch,
            "issue": issue,
            "summary": f"Permission requested for {tool_name or 'unknown tool'}",
        })

    if event == "PostToolUse":
        output = _tool_output(payload)
        warnings = (masker or OutputMasker()).scan(output)
        if warnings:
            return FrictionEvent.from_mapping({
                "event_type": "secret_mask_hit",
                "event_source": _source(event, tool_name),
                "severity": "warning",
                "repo": repo,
                "branch": branch,
                "issue": issue,
                "summary": f"Secret-shaped output detected from {tool_name or 'unknown tool'}",
            })

        if _tool_failed(payload):
            return FrictionEvent.from_mapping({
                "event_type": "command_failure",
                "event_source": _source(event, tool_name),
                "severity": "warning",
                "repo": repo,
                "branch": branch,
                "issue": issue,
                "summary": _failure_summary(payload, tool_name),
            })

    if event == "UserPromptSubmit":
        prompt_text = _prompt_text(payload)
        if (masker or OutputMasker()).scan(prompt_text):
            return FrictionEvent.from_mapping({
                "event_type": "secret_mask_hit",
                "event_source": _source(event, None),
                "severity": "warning",
                "repo": repo,
                "branch": branch,
                "issue": issue,
                "summary": "Secret-shaped user prompt content detected locally",
            })

    return None


def _tool_name(payload: Mapping[str, Any]) -> str | None:
    candidates = (
        payload.get("tool_name"),
        payload.get("toolName"),
        payload.get("tool"),
        payload.get("name"),
    )
    for candidate in candidates:
        value = _optional_str(candidate)
        if value:
            return truncate(value, 80)
    return None


def _source(event: str, tool_name: str | None) -> str:
    return f"hook:{event}:{tool_name}" if tool_name else f"hook:{event}"


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        return text or None
    return None


def _tool_output(payload: Mapping[str, Any]) -> str:
    for key in ("tool_output", "output", "stdout", "stderr", "error"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    result = payload.get("result")
    if isinstance(result, dict):
        parts = [result.get("stdout"), result.get("stderr"), result.get("error")]
        return "\n".join(part for part in parts if isinstance(part, str))
    return ""


def _prompt_text(payload: Mapping[str, Any]) -> str:
    for key in ("prompt", "user_prompt", "message", "text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _tool_failed(payload: Mapping[str, Any]) -> bool:
    for key in ("exit_code", "exitCode", "returncode", "return_code"):
        value = payload.get(key)
        if value not in (None, "", 0, "0"):
            return True

    status = str(payload.get("status") or payload.get("state") or "").lower()
    if status in {"failed", "failure", "error"}:
        return True

    success = payload.get("success")
    if success is False:
        return True

    result = payload.get("result")
    if isinstance(result, dict):
        return _tool_failed(result)

    return bool(payload.get("tool_error") or payload.get("error"))


def _failure_summary(payload: Mapping[str, Any], tool_name: str | None) -> str:
    exit_code = None
    for key in ("exit_code", "exitCode", "returncode", "return_code"):
        if payload.get(key) not in (None, ""):
            exit_code = payload.get(key)
            break
    if exit_code is not None:
        return f"{tool_name or 'Tool'} failed with exit code {exit_code}"
    return f"{tool_name or 'Tool'} reported an error"
