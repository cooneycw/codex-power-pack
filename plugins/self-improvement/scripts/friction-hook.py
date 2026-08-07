#!/usr/bin/env python3
"""Capture only reviewed, minimized friction metadata when explicitly enabled."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SECRET = re.compile(
    r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]{8,}|"
    r"\b(?:ghp|github_pat|sk|xox[baprs])-[-A-Za-z0-9_]{12,}\b|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)


def event(payload: dict[str, object], hook_event: str) -> dict[str, str] | None:
    encoded = json.dumps(payload, ensure_ascii=True)
    tool = str(payload.get("tool_name") or "unknown")[:80]
    if SECRET.search(encoded):
        kind, severity, summary = "secret_mask_hit", "high", f"Secret-shaped data suppressed during {hook_event}"
    elif hook_event == "PermissionRequest":
        kind, severity, summary = "permission_prompt", "low", f"Permission requested by {tool}"
    elif hook_event == "PostToolUse" and any(
        key in encoded.lower() for key in ('"iserror": true', '"exit_code": 1', '"status": "failed"')
    ):
        kind, severity, summary = "command_failure", "medium", f"Tool failure reported by {tool}"
    else:
        return None
    fingerprint = hashlib.sha256(f"{hook_event}:{kind}:{tool}".encode()).hexdigest()
    return {
        "harness": "codex",
        "event_type": kind,
        "source": hook_event,
        "severity": severity,
        "summary": summary,
        "fingerprint": fingerprint,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=("PermissionRequest", "PostToolUse", "UserPromptSubmit"))
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        record = event(payload, args.event)
        queue_value = os.environ.get("CXPP_FRICTION_QUEUE", "")
        if record is not None and queue_value:
            queue = Path(queue_value).expanduser()
            queue.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(queue, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        pass
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
