"""Population, evidence, invocation and control regressions for issue #278."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lib.security import dependency_audit as core

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dependency-audit.py"
CONTROL = ROOT / "controls" / "dependency-audit"
PINS = [core.Package("iniconfig", "2.3.0")]
CLEAN = {"dependencies": [{"name": "iniconfig", "version": "2.3.0", "vulns": []}]}


def locked(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="example"\nversion="1"\ndependencies=[]\n'
        '[project.optional-dependencies]\ndev=["iniconfig==2.3.0"]\n'
    )
    path = tmp_path / "uv.lock"
    path.write_text('[[package]]\nname="iniconfig"\nversion="2.3.0"\n'
                    'source={registry="https://pypi.org/simple"}\n')
    return path


def result(stdout, rc=0):
    return subprocess.CompletedProcess([], rc, stdout, "private stderr is not copied")


def test_export_selects_all_extras_groups_readonly_and_checks_census(tmp_path, monkeypatch):
    source = locked(tmp_path)
    original = source.read_bytes()

    def export(cmd, cwd, timeout):
        assert cwd == tmp_path
        assert timeout == core.EXPORT_TIMEOUT
        assert {"--locked", "--offline", "--all-extras", "--all-groups", "--no-emit-workspace"} <= set(cmd)
        return result("iniconfig==2.3.0 ; sys_platform == 'win32'\n")

    monkeypatch.setattr(core, "run", export)
    assert core.population(source) == PINS
    assert source.read_bytes() == original


@pytest.mark.parametrize("output", ["# generated file only\n", "", "iniconfig==2.2.0\n", "other==2.3.0\n"])
def test_empty_partial_or_wrong_export_cannot_clear(tmp_path, monkeypatch, output):
    source = locked(tmp_path)
    monkeypatch.setattr(core, "run", lambda *a: result(output))
    with pytest.raises(core.Unknown, match="export incomplete"):
        core.population(source)


def test_real_repository_export_is_nonempty_and_immutable():
    source = ROOT / "uv.lock"
    original = source.read_bytes()
    pins = core.population(source)
    assert {"pytest", "ruff", "mypy", "colorama"} <= {pin.name for pin in pins}
    assert len(pins) >= 20
    assert source.read_bytes() == original


def test_export_failure_and_unexpected_lock_write_are_unknown(tmp_path, monkeypatch):
    source = locked(tmp_path)
    monkeypatch.setattr(core, "run", lambda *a: result("", 1))
    with pytest.raises(core.Unknown, match="export failed"):
        core.population(source)

    def bad_export(*args):
        source.write_text(source.read_text() + "# rewritten\n")
        return result("iniconfig==2.3.0\n")

    monkeypatch.setattr(core, "run", bad_export)
    with pytest.raises(core.Unknown, match="changed the lock"):
        core.population(source)


def test_discovery_walks_nested_owned_locks_and_prunes_declared_copies(tmp_path):
    for directory in (tmp_path, tmp_path / "service", tmp_path / "vendor" / "upstream", tmp_path / "controls"):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "uv.lock").touch()
    (tmp_path / "requirements.txt").write_text("ignored==1\n")
    assert core.discover(tmp_path) == sorted([
        tmp_path / "uv.lock", tmp_path / "service" / "uv.lock", tmp_path / "requirements.txt",
    ])


def test_symlink_lock_is_unknown(tmp_path):
    (tmp_path / "target").touch()
    (tmp_path / "uv.lock").symlink_to(tmp_path / "target")
    with pytest.raises(core.Unknown, match="symlinked"):
        core.discover(tmp_path)


def test_genuinely_empty_project_is_explicit(tmp_path):
    source = tmp_path / "pyproject.toml"
    source.write_text('[project]\nname="empty"\nversion="1"\ndependencies=[]\n')
    assert core.population(source) == []
    proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "explicitly dependency-free" in proc.stdout
    assert "examined=0" in proc.stdout


@pytest.mark.parametrize("declaration", [
    '[project.optional-dependencies]\ndev=["pytest"]',
    '[dependency-groups]\ntest=["pytest"]',
    '[tool.poetry.dependencies]\npytest="*"',
    '[tool.uv]\ndev-dependencies=["pyyaml==5.1"]',
    '[tool.pdm.dev-dependencies]\ntest=["pytest"]',
    '[tool.hatch.envs.test]\ndependencies=["pytest"]',
    '[tool.rye]\ndev-dependencies=["pytest"]',
])
def test_no_lock_with_nonbase_declarations_is_not_empty(tmp_path, declaration):
    source = tmp_path / "pyproject.toml"
    source.write_text('[project]\nname="example"\ndependencies=[]\n' + declaration)
    with pytest.raises(core.Unknown, match="require uv.lock"):
        core.population(source)


@pytest.mark.parametrize("text", [
    "foo>=1", "-r other.txt", "-e .", "foo @ https://example.com/foo.whl", "--index-url URL",
])
def test_unsupported_requirements_fail_closed(text):
    with pytest.raises(core.Unknown):
        core.parse_pins(text)


@pytest.mark.parametrize("data,rc", [
    ({}, 0), ({"dependencies": []}, 0), ({"dependencies": {}}, 0), ([], 0),
    ({"dependencies": [{"name": "iniconfig", "version": "2.2.0", "vulns": []}]}, 0),
    ({"dependencies": [{"name": "iniconfig", "version": "2.3.0", "skip_reason": "unavailable"}]}, 0),
    ({"dependencies": [{"name": "iniconfig", "version": "2.3.0", "vulns": [{}]}]}, 1),
    ({"dependencies": CLEAN["dependencies"] * 2}, 0), (CLEAN, 1), (CLEAN, 2),
])
def test_missing_malformed_mismatched_and_failed_evidence_is_unknown(data, rc):
    with pytest.raises(core.Unknown):
        core.validate("uv.lock", PINS, data, rc)


def test_complete_clean_and_advisory_reports_discriminate():
    assert not core.validate("uv.lock", PINS, CLEAN, 0).findings
    evidence = core.replay(CONTROL / "cases" / "bad-advisory" / "audit.json")
    assert evidence.findings[0][1]["id"] == "PYSEC-2020-96"
    with pytest.raises(core.Unknown, match="contradicts"):
        core.validate(evidence.source, evidence.packages, {"dependencies": evidence.dependencies}, 0)


def test_scanner_uses_private_temp_input_no_resolution_or_ambient_fallback(tmp_path, monkeypatch):
    paths = []

    def scan(cmd, cwd, timeout):
        assert cwd == tmp_path
        assert timeout == core.AUDIT_TIMEOUT
        assert {"--no-deps", "--disable-pip", "--strict", "--requirement"} <= set(cmd)
        path = Path(cmd[cmd.index("--requirement") + 1])
        paths.append(path)
        assert path.read_text() == "iniconfig==2.3.0\n"
        assert path.parent.stat().st_mode & 0o777 == 0o700
        return result(json.dumps(CLEAN))

    monkeypatch.setattr(core, "run", scan)
    for _ in range(2):
        assert not core.audit("requirements.txt", PINS, tmp_path).findings
    assert paths[0] != paths[1]
    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize("failure", [FileNotFoundError(), PermissionError(), subprocess.TimeoutExpired("pip-audit", 1)])
def test_tool_failure_is_unknown_and_does_not_leak_stderr(tmp_path, monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(core.subprocess, "run", fail)
    with pytest.raises(core.Unknown, match="not installed|timed out|could not execute"):
        core.audit("uv.lock", PINS, tmp_path)


@pytest.mark.parametrize("stdout", ["", "{}", "not json", '{"dependencies":null}'])
def test_unreadable_scanner_report_is_unknown(tmp_path, monkeypatch, stdout):
    monkeypatch.setattr(core, "run", lambda *a: result(stdout))
    with pytest.raises(core.Unknown):
        core.audit("uv.lock", PINS, tmp_path)


@pytest.mark.parametrize("blind", [False, True])
def test_selftest_requires_both_nonempty_correct_verdicts(monkeypatch, blind):
    calls = []

    def scan(source, pins, cwd):
        assert pins
        calls.append(source)
        case = "bad-advisory" if source == "bad-known-advisory" and not blind else "good-clean"
        return core.replay(CONTROL / "cases" / case / "audit.json")

    monkeypatch.setattr(core, "audit", scan)
    if blind:
        with pytest.raises(core.Unknown, match="failed to discriminate"):
            core.selftest(ROOT)
    else:
        core.selftest(ROOT)
        assert calls == ["bad-known-advisory", "good-clean"]


@pytest.mark.parametrize("case,code,signal", [
    ("bad-advisory", 1, "DEP-AUDIT-FINDING:"), ("good-clean", 0, "examined=1"),
    ("bad-incomplete", 2, "DEP-AUDIT-UNKNOWN:"),
])
def test_cli_offline_cases(case, code, signal):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--from-capture",
                           str(CONTROL / "cases" / case / "audit.json")], capture_output=True, text=True)
    assert proc.returncode == code, proc.stderr
    assert signal in proc.stdout + proc.stderr


def test_registered_control_is_proven_and_rejects_blind_mutation():
    spec = importlib.util.spec_from_file_location("register", ROOT / "scripts" / "check-negative-controls.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    assert mod.evaluate(CONTROL, SCRIPT, ROOT).verdict == "PASS"
    # Mutations need a repo-relative gate path; the register invokes the actual
    # blind anchor in its normal proof and the wedged mutation in its own suite.
    anchor = CONTROL / "anchors" / "constructed-blind.py"
    # The current and anchor gates both return GOOD on BAD input: the register
    # refuses to establish which side drifted, so its precise verdict is UNRESOLVED.
    assert mod.evaluate(CONTROL, anchor, ROOT).verdict == "UNRESOLVED"


def test_root_requirements_not_hidden_by_nested_lock(tmp_path):
    (tmp_path / "requirements.txt").write_text("iniconfig==2.3.0\n")
    service = tmp_path / "service"
    service.mkdir()
    (service / "uv.lock").touch()
    assert core.discover(tmp_path) == [tmp_path / "requirements.txt", service / "uv.lock"]


def test_alternate_versions_are_batched_without_omission(tmp_path, monkeypatch):
    pins = [core.Package("example", "1"), core.Package("example", "2"), core.Package("other", "1")]
    seen = []

    def scan(cmd, cwd, timeout):
        source = Path(cmd[cmd.index("--requirement") + 1])
        batch = core.parse_pins(source.read_text())
        assert len({pin.name for pin in batch}) == len(batch)
        seen.extend(batch)
        return result(json.dumps({"dependencies": [
            {"name": pin.name, "version": pin.version, "vulns": []} for pin in batch
        ]}))

    monkeypatch.setattr(core, "run", scan)
    evidence = core.audit("uv.lock", pins, tmp_path)
    assert sorted(seen) == sorted(pins)
    assert len(evidence.dependencies) == 3


def test_makefile_retains_bandit_and_orders_live_probe_before_audit():
    makefile = (ROOT / "Makefile").read_text()
    recipe = makefile.split("\ndep-audit:\n", 1)[1].split("\n\n", 1)[0]
    assert recipe.index("--selftest") < recipe.index("dependency-audit.py ||")
    assert "bandit -r lib scripts -ll --quiet --skip B104,B108,B310,B602" in recipe
    assert "/tmp/requirements.txt" not in recipe


@pytest.mark.parametrize("probe,audit,bandit,expected", [(0, 0, 0, 0), (0, 1, 0, 2), (2, 0, 0, 2), (0, 0, 1, 2)])
def test_make_runs_bandit_even_on_advisory_or_unknown(tmp_path, probe, audit, bandit, expected):
    script = '#!/bin/sh\necho "$0 $*" >> "$AUDIT_TEST_LOG"\n'
    python = tmp_path / "python3"
    python.write_text(script + f'case "$*" in *--selftest*) exit {probe};; *) exit {audit};; esac\n')
    scanner = tmp_path / "bandit"
    scanner.write_text(script + f"exit {bandit}\n")
    python.chmod(0o700)
    scanner.chmod(0o700)
    log = tmp_path / "commands.log"
    proc = subprocess.run(["make", "dep-audit"], cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "AUDIT_TEST_LOG": str(log)})
    assert proc.returncode == expected, proc.stdout + proc.stderr
    lines = log.read_text().splitlines()
    assert "--selftest" in lines[0]
    assert "bandit -r lib scripts -ll --quiet --skip B104,B108,B310,B602" in lines[-1]
    assert len(lines) == (2 if probe else 3)


def test_registered_capture_files_are_not_gitignored():
    manifest = json.loads((CONTROL / "control.json").read_text())
    for case in manifest["cases"]:
        path = CONTROL / case["input"]
        proc = subprocess.run(["git", "check-ignore", "--no-index", str(path)], cwd=ROOT, capture_output=True)
        assert proc.returncode == 1, f"capture excluded from fresh checkouts: {path}"


def test_repository_unlocked_libraries_are_explicitly_outside_scope():
    sources = core.discover(ROOT)
    excluded = {str(path.relative_to(ROOT)) for path in core.excluded_manifests(ROOT, sources)}
    assert {"lib/creds/pyproject.toml", "lib/cicd/pyproject.toml", "lib/security/pyproject.toml"} <= excluded


def test_nested_only_project_cannot_be_mistaken_for_nonpython(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    (library / "pyproject.toml").write_text('[project]\ndependencies=["pyyaml"]\n')
    with pytest.raises(core.Unknown, match="nested declarations"):
        core.discover(tmp_path)


@pytest.mark.parametrize("name", ["requirements.txt", "pyproject.toml"])
def test_symlink_fallback_sources_are_unknown(tmp_path, name):
    (tmp_path / "outside").touch()
    (tmp_path / name).symlink_to(tmp_path / "outside")
    with pytest.raises(core.Unknown, match="symlinked dependency source"):
        core.discover(tmp_path)


def test_canonicalized_version_is_unknown_not_assumed_equivalent():
    pins = [core.Package("example", "1.0.0-beta1")]
    data = {"dependencies": [{"name": "example", "version": "1.0.0b1", "vulns": []}]}
    with pytest.raises(core.Unknown, match="audit incomplete"):
        core.validate("uv.lock", pins, data, 0)
