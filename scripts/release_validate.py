#!/usr/bin/env python3
"""Validate CxPP marketplace profiles, upgrades, and rollbacks in isolation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

MARKETPLACE = "codex-power-pack"
DEFAULT_SOURCE = "cooneycw/codex-power-pack"
FULL = (
    "project",
    "spec",
    "flow",
    "github",
    "cicd",
    "secrets",
    "woodpecker",
    "security",
    "agents-md",
    "documentation",
    "qa",
    "evaluate",
    "second-opinion",
    "self-improvement",
    "cxpp",
    "claude",
)
RECOMMENDED = tuple(
    family for family in FULL if family not in {"woodpecker", "evaluate", "second-opinion"}
)
PROFILES = {"minimal": ("cxpp",), "recommended": RECOMMENDED, "full": FULL}
SCENARIOS = ("minimal", "recommended", "full", "upgrade", "rollback")


class ValidationError(RuntimeError):
    """Raised when an isolated release scenario fails."""


def marketplace_command(source: str, ref: str, families: Sequence[str]) -> list[str]:
    command = [
        "codex",
        "plugin",
        "marketplace",
        "add",
        source,
        "--ref",
        ref,
        "--sparse",
        ".agents",
    ]
    for family in families:
        command.extend(["--sparse", f"plugins/{family}"])
    command.append("--json")
    return command


def _run_json(command: Sequence[str], home: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(home)
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1:] or completed.stdout.strip().splitlines()[-1:]
        raise ValidationError(f"{' '.join(command[:4])} failed: {' '.join(detail)[:300]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{' '.join(command[:4])} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{' '.join(command[:4])} returned a non-object")
    return payload


def _resolved_sha(installed_root: object) -> str:
    if not isinstance(installed_root, str) or not installed_root:
        raise ValidationError("marketplace add did not report installedRoot")
    completed = subprocess.run(
        ["git", "-C", installed_root, "rev-parse", "HEAD"],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    sha = completed.stdout.strip()
    if completed.returncode != 0 or len(sha) != 40:
        raise ValidationError("could not resolve the installed marketplace commit")
    return sha


def _install(home: Path, source: str, ref: str, families: Sequence[str]) -> dict[str, Any]:
    marketplace = _run_json(marketplace_command(source, ref, families), home)
    installed = []
    for family in families:
        installed.append(
            _run_json(
                ["codex", "plugin", "add", f"{family}@{MARKETPLACE}", "--json"],
                home,
            )
        )
    listing = _run_json(["codex", "plugin", "list", "--json"], home)
    actual = {
        item.get("name"): item
        for item in listing.get("installed", [])
        if isinstance(item, dict) and item.get("marketplaceName") == MARKETPLACE
    }
    missing = sorted(set(families) - set(actual))
    disabled = sorted(name for name in families if not actual.get(name, {}).get("enabled"))
    if missing or disabled:
        raise ValidationError(f"missing={missing!r}, disabled={disabled!r}")
    versions = sorted({str(actual[name].get("version")) for name in families})
    return {
        "requested_ref": ref,
        "resolved_sha": _resolved_sha(marketplace.get("installedRoot")),
        "families": list(families),
        "installed_count": len(actual),
        "versions": versions,
        "passed": True,
    }


def _fresh_profile(source: str, ref: str, profile: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cxpp-release-validate-") as name:
        result = _install(Path(name), source, ref, PROFILES[profile])
    return {"scenario": profile, **result}


def _transition(source: str, first_ref: str, second_ref: str, scenario: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cxpp-release-validate-") as name:
        home = Path(name)
        before = _install(home, source, first_ref, RECOMMENDED)
        _run_json(
            ["codex", "plugin", "marketplace", "remove", MARKETPLACE, "--json"],
            home,
        )
        after = _install(home, source, second_ref, RECOMMENDED)
    return {
        "scenario": scenario,
        "from": before,
        "to": after,
        "passed": before["resolved_sha"] != after["resolved_sha"] and bool(after["passed"]),
    }


def validate(
    source: str,
    candidate_ref: str,
    rollback_ref: str,
    scenarios: Sequence[str] = SCENARIOS,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        if scenario in PROFILES:
            results.append(_fresh_profile(source, candidate_ref, scenario))
        elif scenario == "upgrade":
            results.append(_transition(source, rollback_ref, candidate_ref, scenario))
        elif scenario == "rollback":
            results.append(_transition(source, candidate_ref, rollback_ref, scenario))
        else:
            raise ValidationError(f"unsupported scenario: {scenario}")
    return {
        "schema_version": "1.0",
        "source": source,
        "candidate_ref": candidate_ref,
        "rollback_ref": rollback_ref,
        "results": results,
        "passed": all(result["passed"] for result in results),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate isolated CxPP install profiles, upgrade, and rollback"
    )
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--rollback-ref", required=True)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = validate(
            args.source,
            args.candidate_ref,
            args.rollback_ref,
            tuple(args.scenario or SCENARIOS),
        )
    except (OSError, subprocess.SubprocessError, ValidationError) as exc:
        print(f"release-validate: {exc}", file=os.sys.stderr)
        return 1
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
