"""Project-bound, fail-closed advisory auditing shared by the CLI and adapter.

Markers are removed deliberately: query advisories for ALL locked platform
variants without resolving, installing, building, or executing audited packages.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRUNE = {".git", ".venv", "venv", "node_modules", "__pycache__", "vendor", "controls",
         ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ci-bin"}
EXPORT_TIMEOUT = 120
AUDIT_TIMEOUT = 180
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)")


class Unknown(Exception):
    """Missing or incomplete evidence; never interchangeable with clean."""


@dataclass(frozen=True, order=True)
class Package:
    name: str
    version: str


@dataclass
class Evidence:
    source: str
    packages: list[Package]
    dependencies: list[dict[str, Any]]

    @property
    def findings(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        return [(dep, vuln) for dep in self.dependencies for vuln in dep["vulns"]]


def package(name: Any, version: Any) -> Package:
    if not isinstance(name, str) or not isinstance(version, str) or not PIN.fullmatch(f"{name}=={version}"):
        raise Unknown("invalid package name/version evidence")
    return Package(re.sub(r"[-_.]+", "-", name).lower(), version)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise Unknown(f"cannot read {path.name}") from exc


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(read_text(path))
    except tomllib.TOMLDecodeError as exc:
        raise Unknown(f"malformed {path.name}") from exc


def run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise Unknown(f"{command[0]} not installed or executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise Unknown(f"{command[0]} timed out after {timeout}s") from exc
    except OSError as exc:
        # Tool stderr can contain private index credentials; do not echo it.
        raise Unknown(f"{command[0]} could not execute") from exc


def parse_pins(text: str) -> list[Package]:
    pins = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # No includes, index flags, URLs, editable paths or ranges. Unsupported
        # input is UNKNOWN, not a smaller population that happens to be clean.
        pin = line.split(";", 1)[0].strip()
        match = PIN.fullmatch(pin)
        if not match:
            raise Unknown(f"unsupported requirement at line {number}; need exact registry pins")
        pins.add(package(*match.groups()))
    return sorted(pins)


def discover(root: Path) -> list[Path]:
    """Walk owned locks and include explicit root requirements if present."""
    if not root.is_dir():
        raise Unknown("project root is not a readable directory")
    locks = []

    def onerror(error: OSError) -> None:
        raise Unknown("cannot enumerate project locks") from error

    for parent, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = sorted(d for d in dirs if d not in PRUNE and not (Path(parent) / d).is_symlink())
        if "uv.lock" in files:
            lock = Path(parent) / "uv.lock"
            if lock.is_symlink():
                raise Unknown("symlinked uv.lock is outside the owned-lock contract")
            locks.append(lock)
    if locks:
        if (root / "requirements.txt").exists():
            locks.append(root / "requirements.txt")
        elif not (root / "uv.lock").exists() and (root / "pyproject.toml").exists():
            locks.append(root / "pyproject.toml")
        return _owned_sources(sorted(locks))
    for name in ("requirements.txt", "pyproject.toml"):
        if (root / name).exists():
            return _owned_sources([root / name])
    if excluded_manifests(root, []):
        raise Unknown("nested declarations exist without a supported locked/root requirements population")
    raise Unknown("no supported lock or requirements population found")


def _owned_sources(sources: list[Path]) -> list[Path]:
    if any(source.is_symlink() for source in sources):
        raise Unknown("symlinked dependency source is outside the owned-file contract")
    return sources


def excluded_manifests(root: Path, sources: list[Path]) -> list[Path]:
    """Disclose independent declarations outside the locked/root-pins scope.

    A scoped clean result is not a claim about these unlocked populations.
    Creating locks or installing their optional dependencies is a separate task.
    """
    excluded = []

    def onerror(error: OSError) -> None:
        raise Unknown("cannot enumerate independent dependency declarations") from error

    for parent, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = sorted(d for d in dirs if d not in PRUNE and not (Path(parent) / d).is_symlink())
        for name in ("pyproject.toml", "requirements.txt"):
            source = Path(parent) / name
            if name not in files or source in sources:
                continue
            if name == "pyproject.toml" and source.with_name("uv.lock") in sources:
                continue
            excluded.append(source)
    return sorted(excluded)


def declared_empty(path: Path) -> bool:
    data = read_toml(path)
    project = data.get("project")
    if not isinstance(project, dict) or project.get("dependencies") != []:
        return False
    tool = data.get("tool", {})
    extras = project.get("optional-dependencies", {})
    groups = data.get("dependency-groups", {})
    if not all(isinstance(value, dict) for value in (tool, extras, groups)):
        raise Unknown("malformed dependency declaration")
    # Empty is an affirmative claim. Unknown tool tables may contain their own
    # dependency declarations (uv legacy dev-dependencies, pdm, hatch, rye...).
    if project.get("dynamic") or set(tool) - {"pytest", "ruff", "mypy", "coverage", "black", "isort"}:
        return False
    return not any(extras.values()) and not any(groups.values())


def population(source: Path) -> list[Package]:
    if source.name == "requirements.txt":
        pins = parse_pins(read_text(source))
        if not pins:
            raise Unknown("empty requirements file does not establish a dependency-free project")
        return pins
    if source.name == "pyproject.toml":
        if declared_empty(source):
            return []
        raise Unknown("declared dependencies require uv.lock or fully pinned requirements.txt")

    original = read_text(source)
    lock = read_toml(source)
    entries = lock.get("package")
    if not isinstance(entries, list) or not entries:
        raise Unknown("lock has no package census")
    expected = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
            raise Unknown("malformed lock package")
        origin = entry["source"]
        if origin == {"registry": "https://pypi.org/simple"}:
            expected.add(package(entry.get("name"), entry.get("version")))
        elif set(origin) not in ({"virtual"}, {"editable"}):
            raise Unknown("non-public-registry lock dependency needs explicit audit support")
    proc = run([
        "uv", "export", "--locked", "--offline", "--all-extras", "--all-groups",
        "--no-emit-workspace", "--format", "requirements-txt", "--no-hashes",
    ], source.parent, EXPORT_TIMEOUT)
    if read_text(source) != original:
        raise Unknown("export changed the lock unexpectedly")
    if proc.returncode:
        raise Unknown("uv export failed (lock may be stale or unsupported); no audit performed")
    exported = parse_pins(proc.stdout)
    if set(exported) != expected:
        missing = ",".join(f"{pin.name}=={pin.version}" for pin in sorted(expected - set(exported)))
        extra = ",".join(f"{pin.name}=={pin.version}" for pin in sorted(set(exported) - expected))
        raise Unknown(
            f"export incomplete: lock={len(expected)}, export={len(exported)}; missing=[{missing}] extra=[{extra}]"
        )
    if not exported and not declared_empty(source.parent / "pyproject.toml"):
        raise Unknown("empty export is not an explicitly dependency-free project")
    return exported


def validate(source: str, pins: list[Package], data: Any, returncode: int) -> Evidence:
    if not isinstance(data, dict) or not isinstance(data.get("dependencies"), list):
        raise Unknown("audit report lacks a dependencies array")
    observed = set()
    for dep in data["dependencies"]:
        if not isinstance(dep, dict) or "skip_reason" in dep or not isinstance(dep.get("vulns"), list):
            raise Unknown("audit contains unexamined or malformed dependency evidence")
        pin = package(dep.get("name"), dep.get("version"))
        if pin in observed:
            raise Unknown("duplicate package/version audit evidence")
        observed.add(pin)
        for vuln in dep["vulns"]:
            if not isinstance(vuln, dict) or not isinstance(vuln.get("id"), str) or not vuln["id"].strip():
                raise Unknown("malformed advisory evidence")
            fixes = vuln.get("fix_versions", [])
            if not isinstance(fixes, list) or any(not isinstance(v, str) for v in fixes):
                raise Unknown("malformed advisory fix versions")
            if "description" in vuln and not isinstance(vuln["description"], str):
                raise Unknown("malformed advisory description")
    if observed != set(pins):
        raise Unknown(f"audit incomplete: declared={len(pins)}, examined={len(observed)} package versions")
    evidence = Evidence(source, pins, data["dependencies"])
    if returncode != (1 if evidence.findings else 0):
        raise Unknown("scanner exit status contradicts audit evidence")
    return evidence


def audit(source: str, pins: list[Package], cwd: Path) -> Evidence:
    if not pins:
        return Evidence(source, [], [])
    # pip-audit rejects two versions of one name in a requirements file. Split
    # alternate-platform resolutions into batches, then validate the union.
    batches: list[dict[str, Package]] = []
    for pin in pins:
        batch = next((candidate for candidate in batches if pin.name not in candidate), None)
        if batch is None:
            batch = {}
            batches.append(batch)
        batch[pin.name] = pin
    dependencies = []
    for batch in batches:
        dependencies.extend(_audit_batch(source, list(batch.values()), cwd).dependencies)
    data = {"dependencies": dependencies}
    return validate(source, pins, data, int(any(dep["vulns"] for dep in dependencies)))


def _audit_batch(source: str, pins: list[Package], cwd: Path) -> Evidence:
    with tempfile.TemporaryDirectory(prefix="cxpp-dep-audit-") as directory:
        requirements = Path(directory) / "requirements.txt"
        requirements.write_text("".join(f"{pin.name}=={pin.version}\n" for pin in pins), encoding="utf-8")
        proc = run([
            "pip-audit", "--requirement", str(requirements), "--format", "json",
            "--progress-spinner", "off", "--no-deps", "--disable-pip", "--strict",
        ], cwd, AUDIT_TIMEOUT)
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise Unknown("scanner did not emit a readable JSON report") from exc
    return validate(source, pins, data, proc.returncode)


def replay(path: Path) -> Evidence:
    """Offline evidence does not establish live discovery/export completeness."""
    try:
        capture = json.loads(read_text(path))
        if capture["schema"] != 1 or not isinstance(capture["source"], str):
            raise Unknown("unsupported capture schema/source")
        pins = parse_pins(capture["requirements"])
        if not pins:
            raise Unknown("capture has no declared package population")
        return validate(capture["source"], pins, capture["report"], capture["returncode"])
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise Unknown("malformed capture") from exc


def selftest(root: Path) -> None:
    for name, expect_finding in (("bad-known-advisory", True), ("good-clean", False)):
        source = root / "controls" / "dependency-audit" / "live" / name / "requirements.txt"
        evidence = audit(name, population(source), root)
        if bool(evidence.findings) != expect_finding:
            raise Unknown(f"live self-test {name} failed to discriminate")
