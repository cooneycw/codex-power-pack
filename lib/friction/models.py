"""Allowed event model for Codex friction telemetry."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from lib.creds.masking import OutputMasker

HARNESS = "codex"

ALLOWED_EVENT_FIELDS = {
    "harness",
    "repo",
    "branch",
    "issue",
    "event_type",
    "event_source",
    "severity",
    "summary",
    "fingerprint",
    "created_at",
}

FORBIDDEN_EVENT_FIELDS = {
    "prompt",
    "raw_prompt",
    "tool_input",
    "raw_tool_input",
    "tool_output",
    "raw_tool_output",
    "environment",
    "env",
    "config",
    "raw_config",
    "session_history",
    "session_history_path",
    "session_log",
    "stack_trace",
    "traceback",
}

EVENT_TYPES = {
    "approval_prompt",
    "command_failure",
    "tool_error",
    "secret_mask_hit",
    "ledger_write_failure",
    "gate_failure",
    "manual_intervention",
    "red_output",
    "other",
}

SEVERITIES = {"info", "warning", "error", "critical"}

FIELD_LIMITS = {
    "repo": 160,
    "branch": 160,
    "event_source": 160,
    "summary": 512,
    "fingerprint": 64,
}


class FrictionEventError(ValueError):
    """Raised when a friction event violates the allowlisted schema."""


def utc_now() -> str:
    """Return an RFC3339-ish UTC timestamp with second precision."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def collapse_ws(value: str) -> str:
    """Keep JSONL and ledger fields compact and single-line."""

    return re.sub(r"\s+", " ", value).strip()


def truncate(value: str, limit: int) -> str:
    """Truncate a string without hiding that truncation occurred."""

    if len(value) <= limit:
        return value
    if limit <= 3:
        return "." * max(0, limit)
    return value[: limit - 3] + "..."


def _optional_str(value: object, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    raise FrictionEventError(f"{field} must be a scalar string-like value")


def _issue(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise FrictionEventError("issue must be an integer") from exc
    if parsed < 0:
        raise FrictionEventError("issue must be non-negative")
    return parsed


@dataclass(frozen=True)
class FrictionEvent:
    """A minimized, masked-ready friction event.

    `harness` is fixed to `codex`; caller-provided values are ignored so every
    ledger sighting can be attributed reliably.
    """

    event_type: str
    summary: str
    event_source: str | None = None
    repo: str | None = None
    branch: str | None = None
    issue: int | None = None
    severity: str = "warning"
    created_at: str | None = None
    fingerprint: str | None = None
    harness: str = HARNESS

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FrictionEvent":
        """Build an event from an allowlisted mapping.

        Raw hook payloads must be reduced by an adapter first; this constructor
        rejects raw prompt/tool/config fields even if they appear alongside
        allowed fields.
        """

        keys = set(data)
        forbidden = keys & FORBIDDEN_EVENT_FIELDS
        if forbidden:
            joined = ", ".join(sorted(forbidden))
            raise FrictionEventError(f"forbidden event field(s): {joined}")

        unknown = keys - ALLOWED_EVENT_FIELDS
        if unknown:
            joined = ", ".join(sorted(unknown))
            raise FrictionEventError(f"unknown event field(s): {joined}")

        event_type = _optional_str(data.get("event_type"), "event_type")
        if not event_type:
            raise FrictionEventError("event_type is required")
        event_type = event_type.strip().lower().replace("-", "_")
        if event_type not in EVENT_TYPES:
            raise FrictionEventError(f"unknown event_type: {event_type!r}")

        summary = _optional_str(data.get("summary"), "summary")
        if not summary or not summary.strip():
            raise FrictionEventError("summary is required")

        severity = (_optional_str(data.get("severity"), "severity") or "warning").strip().lower()
        if severity not in SEVERITIES:
            raise FrictionEventError(f"unknown severity: {severity!r}")

        return cls(
            event_type=event_type,
            summary=summary,
            event_source=_optional_str(data.get("event_source"), "event_source"),
            repo=_optional_str(data.get("repo"), "repo"),
            branch=_optional_str(data.get("branch"), "branch"),
            issue=_issue(data.get("issue")),
            severity=severity,
            created_at=_optional_str(data.get("created_at"), "created_at") or utc_now(),
            fingerprint=_optional_str(data.get("fingerprint"), "fingerprint"),
            harness=HARNESS,
        )

    def masked(self, masker: OutputMasker | None = None) -> "FrictionEvent":
        """Return the event after exact-value/pattern masking and truncation."""

        masker = masker or OutputMasker()

        def clean(field: str, value: str | None) -> str | None:
            if value is None:
                return None
            masked = collapse_ws(masker.mask(value))
            return truncate(masked, FIELD_LIMITS.get(field, 512))

        masked_event = replace(
            self,
            event_source=clean("event_source", self.event_source),
            repo=clean("repo", self.repo),
            branch=clean("branch", self.branch),
            summary=clean("summary", self.summary) or "",
            created_at=clean("created_at", self.created_at) or utc_now(),
            fingerprint=None,
            harness=HARNESS,
        )
        return replace(masked_event, fingerprint=masked_event.compute_fingerprint())

    def fingerprint_material(self) -> dict[str, object]:
        """Fields used for deduplication, after masking.

        `created_at` is deliberately excluded so repeated sightings of the same
        friction event converge.
        """

        return {
            "harness": HARNESS,
            "repo": self.repo or "",
            "branch": self.branch or "",
            "issue": self.issue,
            "event_type": self.event_type,
            "event_source": self.event_source or "",
            "severity": self.severity,
            "summary": self.summary,
        }

    def compute_fingerprint(self) -> str:
        encoded = json.dumps(
            self.fingerprint_material(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def public_dict(self) -> dict[str, object]:
        """Serialize only allowed, already-masked event fields."""

        return {
            "harness": HARNESS,
            "repo": self.repo,
            "branch": self.branch,
            "issue": self.issue,
            "event_type": self.event_type,
            "event_source": self.event_source,
            "severity": self.severity,
            "summary": self.summary,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
        }

    def ledger_title(self) -> str:
        """Stable title passed to cpp-memory for its own dedup model."""

        source = f" [{self.event_source}]" if self.event_source else ""
        return truncate(f"Codex {self.event_type}{source}: {self.summary}", 180)

    def ledger_body(self) -> str:
        """Body passed to cpp-memory, intentionally restricted to allowed fields."""

        fields = self.public_dict()
        lines = [
            "Codex friction telemetry event.",
            "",
            f"- event_type: {fields['event_type']}",
            f"- event_source: {fields['event_source'] or ''}",
            f"- severity: {fields['severity']}",
            f"- repo: {fields['repo'] or ''}",
            f"- branch: {fields['branch'] or ''}",
            f"- issue: {fields['issue'] or ''}",
            f"- harness: {HARNESS}",
            f"- fingerprint: {fields['fingerprint']}",
            "",
            fields["summary"] or "",
        ]
        return "\n".join(str(line) for line in lines)
