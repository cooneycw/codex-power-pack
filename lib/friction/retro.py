"""Turn minimized Codex friction telemetry into safe, actionable proposals."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import FrictionEvent, FrictionEventError

REPEATED_FAILURE_TYPES = {"command_failure", "gate_failure", "tool_error", "red_output"}
BOOTSTRAP_PATTERN = re.compile(r"\b(admin[- ]only|bootstrap|manual (?:iam|permission|apply))\b", re.IGNORECASE)


@dataclass(frozen=True)
class RetroProposal:
    """A non-sensitive, user-confirmed improvement candidate."""

    kind: str
    title: str
    action: str
    evidence_count: int
    blocking: bool = False


def analyze_events(events: Iterable[Mapping[str, Any]], repeat_threshold: int = 2) -> list[RetroProposal]:
    """Produce proposals from allowlisted telemetry without returning raw input."""
    normalized: list[FrictionEvent] = []
    for event in events:
        try:
            normalized.append(FrictionEvent.from_mapping(event).masked())
        except FrictionEventError:
            # Telemetry is intentionally fail-open: a malformed legacy row must
            # not stop analysis of the rest of the queue.
            continue

    proposals: list[RetroProposal] = []
    repeated: dict[str, int] = {}
    for event in normalized:
        if event.event_type in REPEATED_FAILURE_TYPES:
            fingerprint = event.fingerprint or event.compute_fingerprint()
            repeated[fingerprint] = repeated.get(fingerprint, 0) + 1

    for count in repeated.values():
        if count >= repeat_threshold:
            proposals.append(
                RetroProposal(
                    kind="validation-gate",
                    title="Add a preflight validation gate for a repeated failure",
                    action=(
                        "Add a deterministic preflight or canary check to the Makefile and "
                        "make CI run it before the affected workflow."
                    ),
                    evidence_count=count,
                )
            )
            break

    # Exact fingerprints are the strongest same-root-cause signal. Some legacy
    # hooks, however, attach volatile wording to every failure. When a failure
    # class itself repeats, propose a generic preflight/triage gate without
    # pretending the individual summaries are identical or exposing them.
    if not any(proposal.kind == "validation-gate" for proposal in proposals):
        type_counts: dict[str, int] = {}
        for event in normalized:
            if event.event_type in REPEATED_FAILURE_TYPES:
                type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
        for event_type, count in type_counts.items():
            if count >= repeat_threshold:
                proposals.append(
                    RetroProposal(
                        kind="validation-gate",
                        title=f"Add a preflight gate for repeated {event_type.replace('_', ' ')} events",
                        action=(
                            "Add a deterministic preflight or canary check to the Makefile and "
                            "make CI run it before the affected workflow."
                        ),
                        evidence_count=count,
                    )
                )
                break

    bootstrap_count = sum(1 for event in normalized if BOOTSTRAP_PATTERN.search(event.summary))
    if bootstrap_count:
        proposals.append(
            RetroProposal(
                kind="bootstrap-reminder",
                title="Block workflow until the admin-only bootstrap prerequisite is applied",
                action=(
                    "Add a bootstrap-check target or preflight that names the required manual "
                    "admin apply and exits non-zero before merge, deploy, or retry."
                ),
                evidence_count=bootstrap_count,
                blocking=True,
            )
        )
    return proposals


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(_normalize_record(value))
    return records


def _normalize_record(value: dict[str, Any]) -> dict[str, Any]:
    """Map the previous fail-open JSONL shape into the public event schema."""
    if "event_type" in value:
        return value

    legacy_type = str(value.get("class", "other")).strip().lower().replace("-", "_")
    event_type = {
        "permission_prompt": "approval_prompt",
        "gate_failure": "gate_failure",
        "red_output": "red_output",
        "manual_intervention": "manual_intervention",
    }.get(legacy_type, "other")
    return {
        "event_type": event_type,
        "summary": str(value.get("signal", "legacy friction event")),
        "event_source": str(value.get("step", "legacy-jsonl")),
        "severity": "warning",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze minimized Codex friction telemetry")
    parser.add_argument("--path", type=Path, default=Path(".codex/friction.jsonl"))
    parser.add_argument("--repeat-threshold", type=int, default=2)
    args = parser.parse_args(argv)

    proposals = analyze_events(_read_jsonl(args.path), args.repeat_threshold)
    print(json.dumps([asdict(proposal) for proposal in proposals], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
