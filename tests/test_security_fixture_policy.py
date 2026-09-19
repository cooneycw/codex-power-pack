"""Exact fixture exceptions must never turn into whole-file exclusions."""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from lib.security.fixture_policy import FixturePolicy, InvalidFixturePolicy, load_fixture_policy
from lib.security.modules import secrets
from lib.security.orchestrator import check_gate

ROOT = Path(__file__).resolve().parents[1]
IDS = {p[1] for p in secrets.SECRET_PATTERNS + secrets.ASSIGNMENT_PATTERNS}


def token(tail: str = "A") -> str:
    return "AK" + "IA" + tail * 16


def record(value: str, relative: str = "settings.py", **changes: object) -> dict:
    return {
        "path": relative,
        "finding_id": "AWS_ACCESS_KEY",
        "sha256": hashlib.sha256(value.encode()).hexdigest(),
        "reason": "Synthetic unit-test sentinel, not a live credential.",
        **changes,
    }


def write_policy(root: Path, records: list[dict]) -> Path:
    destination = root / ".codex/security-fixtures.toml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = "version = 1\nfixtures = []\n" if not records else "version = 1\n"
    for item in records:
        text += "\n[[fixtures]]\n" + "".join(f"{key} = {json.dumps(value)}\n" for key, value in item.items())
    destination.write_text(text)
    return destination


def write_source(root: Path, *values: str, relative: str = "settings.py") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f'VALUE_{index} = "{value}"' for index, value in enumerate(values)))
    return path


def test_absent_policy_preserves_prior_scanner_behavior(tmp_path: Path) -> None:
    write_source(tmp_path, token())
    result = secrets.scan(str(tmp_path))
    assert [f.id for f in result.findings] == ["AWS_ACCESS_KEY"]
    assert "0 reviewed fixture match(es) excepted" in result.passed[0]


def test_relative_scan_root_does_not_inherit_ancestor_skip_names(tmp_path: Path, monkeypatch) -> None:
    # The scanner's existing relative-root population must not shrink merely
    # because the caller's checkout happens to sit in an ancestor named build.
    subject = tmp_path / "build" / "project"
    write_source(subject, token())
    monkeypatch.chdir(subject)
    assert secrets.scan(".").has_blockers


def test_exact_match_is_visible_and_not_a_claim_about_history(tmp_path: Path) -> None:
    write_source(tmp_path, token())
    write_policy(tmp_path, [record(token())])
    result = secrets.scan(str(tmp_path))
    assert not result.findings
    assert result.passed == ["Native secrets: 2 source files examined; 1 reviewed fixture match(es) excepted"]
    # Source includes the policy itself; neither message nor gate claims history.
    assert check_gate(result, "flow_finish")[0]


@pytest.mark.parametrize("change", ["additional", "changed", "moved", "wrong-id"])
def test_exception_never_hides_a_neighbours_finding(tmp_path: Path, change: str) -> None:
    write_source(tmp_path, token())
    entry = record(token())
    if change == "additional":
        write_source(tmp_path, token(), token("B"))
    elif change == "changed":
        write_source(tmp_path, token("B"))
    elif change == "moved":
        (tmp_path / "settings.py").rename(tmp_path / "neighbour.py")
    else:
        entry["finding_id"] = "GITHUB_PAT"
    write_policy(tmp_path, [entry])
    result = secrets.scan(str(tmp_path))
    assert [f.id for f in result.findings] == ["AWS_ACCESS_KEY"]
    assert not check_gate(result, "flow_finish")[0]


def test_assignment_digest_covers_the_entire_match(tmp_path: Path) -> None:
    matched = 'pass' + 'word = "fixture-value"'
    (tmp_path / "settings.py").write_text(matched)
    entry = record(matched, finding_id="HARDCODED_PASSWORD")
    write_policy(tmp_path, [entry])
    assert not secrets.scan(str(tmp_path)).findings
    (tmp_path / "settings.py").write_text(matched.replace(" = ", "="))
    assert [f.id for f in secrets.scan(str(tmp_path)).findings] == ["HARDCODED_PASSWORD"]


@pytest.mark.parametrize("changes", [
    {"path": "../settings.py"}, {"path": "/settings.py"}, {"path": "tests/*.py"},
    {"path": "tests/?.py"}, {"path": "tests/[ab].py"}, {"path": "tests\\settings.py"},
    {"path": "./settings.py"}, {"path": "tests//settings.py"}, {"path": "tests/../settings.py"},
    {"path": "settings.py/"}, {"path": "C:settings.py"}, {"path": "settings\n.py"},
    {"sha256": "0" * 63}, {"sha256": "A" * 64}, {"finding_id": "UNKNOWN"},
    {"reason": " "}, {"reason": False}, {"wildcard": True},
])
def test_invalid_record_is_a_blocker_not_a_silent_exception(tmp_path: Path, changes: dict) -> None:
    write_source(tmp_path, token())
    write_policy(tmp_path, [record(token(), **changes)])
    result = secrets.scan(str(tmp_path))
    assert {f.id for f in result.findings} == {"INVALID_FIXTURE_POLICY", "AWS_ACCESS_KEY"}
    assert not check_gate(result, "flow_finish")[0]


@pytest.mark.parametrize("contents", [
    "version = true\nfixtures = []", "version = 2\nfixtures = []", "fixtures = []",
    "version = 1\nfixtures = {}", "version = 1\nfixtures = [2]",
    "version = 1\nfixtures = []\nextra = true", "version = 1\n[[fixtures]]\npath = 'settings.py'",
    "version = 1\nversion = 1\nfixtures = []",
])
def test_invalid_schema_refuses_even_without_a_secret(tmp_path: Path, contents: str) -> None:
    policy = write_policy(tmp_path, [])
    policy.write_text(contents)
    assert secrets.scan(str(tmp_path)).has_blockers


def test_duplicate_records_are_refused(tmp_path: Path) -> None:
    write_policy(tmp_path, [record(token()), record(token())])
    with pytest.raises(InvalidFixturePolicy, match="duplicate"):
        load_fixture_policy(tmp_path, IDS)


@pytest.mark.parametrize("kind", ["file", "parent", "dangling", "directory"])
def test_policy_path_must_be_local_regular_file(tmp_path: Path, kind: str) -> None:
    actual = tmp_path / "actual"
    policy = write_policy(actual, [])
    subject = tmp_path / "subject"
    subject.mkdir()
    (subject / ".codex").mkdir()
    target = subject / ".codex/security-fixtures.toml"
    if kind == "parent":
        (subject / ".codex").rmdir()
        (subject / ".codex").symlink_to(actual / ".codex", target_is_directory=True)
    elif kind == "directory":
        target.mkdir()
    else:
        target.symlink_to(policy if kind == "file" else tmp_path / "absent")
    assert secrets.scan(str(subject)).has_blockers


@pytest.mark.parametrize("outside", [False, True])
def test_fixture_symlink_cannot_inherit_an_exception(tmp_path: Path, outside: bool) -> None:
    subject = tmp_path / "subject"
    write_policy(subject, [record(token())])
    source = write_source(tmp_path if outside else subject, token(), relative="other.py")
    (subject / "settings.py").symlink_to(source)
    result = secrets.scan(str(subject))
    assert "INVALID_FIXTURE_POLICY" in {f.id for f in result.findings}
    assert "AWS_ACCESS_KEY" in {f.id for f in result.findings}


def test_symlink_added_after_load_cannot_match(tmp_path: Path) -> None:
    write_policy(tmp_path, [record(token())])
    policy = load_fixture_policy(tmp_path, IDS)
    (tmp_path / "settings.py").symlink_to(tmp_path / "other.py")
    assert not policy.matches("settings.py", "AWS_ACCESS_KEY", token())


def test_unreadable_policy_cannot_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = write_policy(tmp_path, [])
    original = Path.open

    def refuse(self: Path, *args, **kwargs):
        if self == policy:
            raise PermissionError("not printed")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse)
    result = secrets.scan(str(tmp_path))
    assert result.has_blockers
    assert "not printed" not in str(result)


def test_malformed_policy_diagnostic_does_not_echo_input(tmp_path: Path) -> None:
    policy = write_policy(tmp_path, [])
    policy.write_text(f"[BROKEN {token()}\n")
    result = secrets.scan(str(tmp_path))
    assert result.has_blockers
    assert token() not in str(result)


def run_scan(root: Path, script: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script or ROOT / "scripts/native-secret-scan.py"), "--root", str(root)],
        capture_output=True, text=True, check=False, timeout=30, cwd=ROOT,
    )


def test_native_command_refuses_missing_or_empty_population(tmp_path: Path) -> None:
    for path in (tmp_path, tmp_path / "missing"):
        proc = run_scan(path)
        assert proc.returncode == 2
        assert "UNKNOWN" in proc.stderr


def test_native_command_separates_finding_from_policy_failure(tmp_path: Path) -> None:
    write_source(tmp_path, token())
    found = run_scan(tmp_path)
    assert found.returncode == 1
    assert "finding AWS_ACCESS_KEY" in found.stdout
    assert token() not in found.stdout + found.stderr
    write_policy(tmp_path, [record(token())])
    assert run_scan(tmp_path).returncode == 0
    write_policy(tmp_path, [record(token(), reason="")])
    assert run_scan(tmp_path).returncode == 2


def test_committed_control_rejects_path_only_mutant() -> None:
    control = ROOT / "controls/native-secret-fixture-scope"
    good, bad = control / "cases/known-fixture", control / "cases/extra-secret"
    actual_good, actual_bad = run_scan(good), run_scan(bad)
    assert actual_good.returncode == 0
    assert actual_bad.returncode == 1
    assert "finding GITHUB_PAT" in actual_bad.stdout
    anchor = control / "anchors/path-only-native-scan.py"
    assert run_scan(good, anchor).returncode == 0
    assert run_scan(bad, anchor).returncode == 0


def test_empty_policy_is_not_a_global_exception(tmp_path: Path) -> None:
    write_source(tmp_path, token())
    write_policy(tmp_path, [])
    assert secrets.scan(str(tmp_path)).has_blockers
    assert not FixturePolicy(tmp_path).matches("settings.py", "AWS_ACCESS_KEY", token())


def test_identical_occurrences_are_counted_individually(tmp_path: Path) -> None:
    write_source(tmp_path, token(), token())
    write_policy(tmp_path, [record(token())])
    result = secrets.scan(str(tmp_path))
    assert not result.findings
    assert "2 reviewed fixture match(es) excepted" in result.passed[0]


def test_unscanned_suffix_is_not_a_clean_population(tmp_path: Path) -> None:
    write_source(tmp_path, token(), relative="fixture.txt")
    result = run_scan(tmp_path)
    assert result.returncode == 2
    assert "0 source files examined" in result.stdout
    assert token() not in result.stdout + result.stderr


def test_scanner_crash_is_unknown_and_never_echoed(tmp_path: Path, monkeypatch, capsys) -> None:
    def crash(*args, **kwargs):
        raise RuntimeError(token())

    monkeypatch.setattr(secrets, "scan", crash)
    script = runpy.run_path(str(ROOT / "scripts/native-secret-scan.py"))
    assert script["main"](["--root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "UNKNOWN" in captured.err
    assert "finding" not in captured.out
    assert token() not in captured.out + captured.err


def test_non_ascii_assignment_digest_is_locale_independent(tmp_path: Path) -> None:
    matched = 'pass' + 'word = "synthetic-caf\u00e9-value"'
    (tmp_path / "settings.py").write_text(matched, encoding="utf-8")
    write_policy(tmp_path, [record(matched, finding_id="HARDCODED_PASSWORD")])
    for utf8 in ("0", "1"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/native-secret-scan.py"), "--root", str(tmp_path)],
            env={**os.environ, "LC_ALL": "C", "PYTHONUTF8": utf8, "PYTHONCOERCECLOCALE": "0"},
            capture_output=True, text=True, check=False, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 reviewed fixture match(es) excepted" in result.stdout


def test_real_make_recipe_reports_a_planted_token(tmp_path: Path) -> None:
    write_source(tmp_path, token())
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    result = subprocess.run(
        ["make", "-f", str(ROOT / "Makefile"), "native-secret-scan"], cwd=tmp_path,
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode != 0
    assert "native-secret-scan: finding AWS_ACCESS_KEY" in result.stdout
    assert token() not in result.stdout + result.stderr
