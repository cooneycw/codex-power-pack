"""Project-bound pip-audit adapter; never audit the scanner's environment."""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import dependency_audit as core
from ..models import Finding, ScanResult, Severity


def is_available() -> bool:
    return shutil.which("pip-audit") is not None


def scan(project_root: str) -> ScanResult:
    result = ScanResult()
    root = Path(project_root).resolve()
    try:
        sources = core.discover(root)
        excluded = core.excluded_manifests(root, sources)
    except core.Unknown as exc:
        indicators = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "uv.lock")
        nonpython = root.is_dir() and not any((root / name).exists() for name in indicators)
        if nonpython and str(exc).startswith("no supported"):
            result.skipped.append("pip-audit (not a Python project)")
        else:
            result.errors.append(f"pip-audit UNKNOWN: {exc}")
        return result
    for source in excluded:
        result.skipped.append(
            f"pip-audit outside locked/root-requirements scope: {source.relative_to(root)} (not audited)"
        )
    for source in sources:
        relative = str(source.relative_to(root))
        try:
            evidence = core.audit(relative, core.population(source), root)
        except core.Unknown as exc:
            result.errors.append(f"pip-audit UNKNOWN ({relative}): {exc}")
            continue
        for dep, vuln in evidence.findings:
            fixes = vuln.get("fix_versions", [])
            result.findings.append(Finding(
                id="PIP_AUDIT_" + vuln["id"].replace("-", "_"),
                severity=Severity.HIGH,
                title=f"Vulnerable dependency: {dep['name']} {dep['version']} ({vuln['id']})",
                file_path=relative,
                why=vuln.get("description", "Known vulnerability in this package version."),
                fix=f"Upgrade the declared dependency and regenerate its lock: {', '.join(fixes)}"
                    if fixes else "No fix available yet",
                scanner="pip-audit",
            ))
        if not evidence.findings:
            result.passed.append(
                f"pip-audit {relative}: examined {len(evidence.packages)} all-platform registry package versions; "
                + ("no known advisories" if evidence.packages else "explicitly dependency-free")
            )
    return result
