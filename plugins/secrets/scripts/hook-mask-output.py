#!/usr/bin/env python3
"""Suppress secret-shaped PostToolUse output without echoing sensitive input."""

from __future__ import annotations

import json
import re
import sys

PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"\b(?:ghp|github_pat|sk|xox[baprs])-[-A-Za-z0-9_]{12,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        candidate = json.dumps(payload.get("tool_response", ""), ensure_ascii=True)
        if any(pattern.search(candidate) for pattern in PATTERNS):
            print(json.dumps({
                "decision": "block",
                "reason": "Sensitive tool output was suppressed by the Secrets plugin.",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        "Do not repeat the original output. "
                        "Use $secrets-run or a masked secrets workflow."
                    ),
                },
            }))
        else:
            print("{}")
    except Exception:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
