#!/usr/bin/env python3
"""Deterministic semantic compatibility gate for published Codex skills."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_MODULE = REPO_ROOT / "scripts" / "skill_contract_baseline.py"
CONTRACT_PATH = REPO_ROOT / ".agents" / "skill-contracts.json"
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGINS_ROOT = REPO_ROOT / "plugins"
SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"
FIXED_REPOSITORY = re.compile(r"\bcooneycw/(?:claude-power-pack|codex-power-pack)\b", re.IGNORECASE)
EXPLICIT_SKILL = re.compile(r"\$([a-z][a-z0-9_]*(?:-[a-z0-9_]+)+)")
IGNORED_PAYLOAD_PARTS = {"__pycache__"}
IGNORED_PAYLOAD_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True)
class Finding:
    rule: str
    subject: str
    detail: str


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def _baseline_module() -> Any:
    spec = importlib.util.spec_from_file_location("skill_contract_baseline", BASELINE_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASELINE_MODULE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _metadata() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(PLUGINS_ROOT.glob("*/skills/*/agents/openai.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: expected a YAML mapping")
        result[path.parents[1].name] = {"path": path, "payload": payload, "plugin": path.parents[3].name}
    return result


def _payload_drift(skill: dict[str, Any]) -> list[str]:
    package = skill["package"]
    if package["state"] != "packaged":
        return []
    source_root = REPO_ROOT / skill["installed"]["path"]
    package_root = REPO_ROOT / package["path"]

    def is_payload_file(path: Path, root: Path) -> bool:
        relative = path.relative_to(root)
        return (
            path.is_file()
            and "agents" not in relative.parts
            and not (IGNORED_PAYLOAD_PARTS & set(relative.parts))
            and path.suffix not in IGNORED_PAYLOAD_SUFFIXES
        )

    source_files = {
        path.relative_to(source_root).as_posix(): path.read_bytes()
        for path in source_root.rglob("*")
        if is_payload_file(path, source_root)
    }
    package_files = {
        path.relative_to(package_root).as_posix(): path.read_bytes()
        for path in package_root.rglob("*")
        if is_payload_file(path, package_root)
    }
    source_names = set(source_files)
    package_names = set(package_files)
    changed = {name for name in source_names & package_names if source_files[name] != package_files[name]}
    return sorted(source_names ^ package_names | changed)


def lint_contract(today: date | None = None) -> list[Finding]:
    today = today or date.today()
    module = _baseline_module()
    expected = module.build_contract()
    recorded = _load_json(CONTRACT_PATH)
    marketplace = _load_json(MARKETPLACE_PATH)
    metadata = _metadata()
    findings: list[Finding] = []

    if recorded != expected:
        findings.append(Finding("stale-contract", str(CONTRACT_PATH.relative_to(REPO_ROOT)), "run the baseline writer"))

    published_plugins = {entry["name"] for entry in marketplace.get("plugins", ())}
    installed_names = {path.name for path in SKILLS_ROOT.iterdir() if (path / "SKILL.md").is_file()}
    contract_names = {skill["name"] for skill in expected["skills"]}
    if installed_names != contract_names:
        findings.append(
            Finding(
                "installed-inventory",
                ".codex/skills",
                f"missing={sorted(contract_names - installed_names)}, extra={sorted(installed_names - contract_names)}",
            )
        )

    for plugin in expected["marketplace"]["plugins"]:
        if plugin["state"] != "published" or plugin["name"] not in published_plugins:
            findings.append(Finding("marketplace-inventory", plugin["name"], "published plugin path is missing"))

    for skill in expected["skills"]:
        name = skill["name"]
        package = skill["package"]
        exclusion = skill["exclusion"]
        if package["state"] == "packaged":
            if exclusion["state"] != "not_excluded":
                findings.append(Finding("packaging-exclusion", name, "packaged skill cannot also be excluded"))
            if skill["marketplace"]["state"] != "published":
                findings.append(Finding("marketplace-inventory", name, "packaged skill is not published"))
            drift = _payload_drift(skill)
            if drift:
                findings.append(Finding("package-drift", name, ", ".join(drift[:5])))
        else:
            missing = [
                field
                for field in ("owner", "rationale", "replacement", "review_by", "tracking_issue")
                if not exclusion.get(field)
            ]
            if exclusion["state"] != "excluded" or missing:
                findings.append(Finding("invalid-exclusion", name, f"missing={missing}"))
            else:
                try:
                    review_by = date.fromisoformat(str(exclusion["review_by"]))
                except ValueError:
                    findings.append(Finding("invalid-exclusion-date", name, str(exclusion["review_by"])))
                else:
                    if review_by < today:
                        findings.append(Finding("expired-exclusion", name, review_by.isoformat()))

    for reference in expected["references"]:
        if reference["classification"] == "unexplained":
            findings.append(
                Finding(
                    "unresolved-reference",
                    f"{reference['path']}:{reference['line']}",
                    f"{reference['kind']} {reference['token']}",
                )
            )

    for name, item in metadata.items():
        payload = item["payload"]
        interface = payload.get("interface") or {}
        policy = payload.get("policy") or {}
        description = str(interface.get("short_description") or "").strip()
        prompt = str(interface.get("default_prompt") or "").strip()
        rel = item["path"].relative_to(REPO_ROOT).as_posix()
        if len(description) < 12 or len(description) > 160 or description.endswith("..."):
            findings.append(Finding("metadata-description", rel, "description must be 12-160 complete characters"))
        if FIXED_REPOSITORY.search(description) or FIXED_REPOSITORY.search(prompt):
            findings.append(Finding("repository-neutrality", rel, "metadata names a fixed repository"))
        if not prompt:
            findings.append(Finding("starter-prompt", rel, "default_prompt is required"))
        for target in EXPLICIT_SKILL.findall(prompt):
            if target not in installed_names:
                findings.append(Finding("starter-prompt", rel, f"${target} is not installed"))
        implicit = policy.get("allow_implicit_invocation") is True
        if implicit != (name in {"flow-auto", "project-next"}):
            findings.append(Finding("implicit-policy", rel, f"unexpected implicit={implicit}"))

    return findings


def run_check(as_json: bool = False) -> int:
    try:
        findings = lint_contract()
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f"skill-contract-lint: invalid contract: {exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps({"ok": not findings, "findings": [asdict(item) for item in findings]}, indent=2))
    elif findings:
        print("skill-contract-lint: semantic compatibility failures", file=sys.stderr)
        for finding in findings:
            print(f"{finding.rule}: {finding.subject}: {finding.detail}", file=sys.stderr)
    else:
        print("skill-contract-lint: all published skills are semantically compatible")
    return 1 if findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the current repository contract")
    parser.add_argument("--json", action="store_true", help="emit machine-readable findings")
    args = parser.parse_args()
    return run_check(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
