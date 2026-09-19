"""The reusable adapter must inspect the selected project, not ambient tools."""

import json
import subprocess

import pytest

from lib.security import dependency_audit as core
from lib.security.modules import pip_audit


def test_non_python_project_is_skipped(tmp_path):
    result = pip_audit.scan(str(tmp_path))
    assert result.skipped == ["pip-audit (not a Python project)"]
    assert not result.passed


@pytest.mark.parametrize("name", ["setup.py", "Pipfile"])
def test_unsupported_project_never_falls_back_to_environment(tmp_path, monkeypatch, name):
    (tmp_path / name).touch()
    monkeypatch.setattr(core, "run", lambda *a: pytest.fail("must not invoke ambient audit"))
    result = pip_audit.scan(str(tmp_path))
    assert result.errors and not result.passed and not result.skipped


def test_locked_project_preferred_over_requirements_and_findings_have_provenance(tmp_path, monkeypatch):
    nested = tmp_path / "service"
    nested.mkdir()
    lock = nested / "uv.lock"
    lock.touch()
    (nested / "requirements.txt").write_text("ambient==1\n")

    def population(source):
        assert source == lock
        return [core.Package("pyyaml", "5.1")]

    monkeypatch.setattr(core, "population", population)
    data = {"dependencies": [{"name": "pyyaml", "version": "5.1", "vulns": [
        {"id": "PYSEC-2020-96", "description": "unsafe load", "fix_versions": ["5.3.1"]}
    ]}]}
    monkeypatch.setattr(core, "run", lambda *a: subprocess.CompletedProcess([], 1, json.dumps(data), ""))
    result = pip_audit.scan(str(tmp_path))
    assert not result.errors and not result.passed
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.file_path == "service/uv.lock"
    assert "5.1" in finding.title
    assert "5.3.1" in finding.fix
    assert finding.id == "PIP_AUDIT_PYSEC_2020_96"


def test_requirements_fallback_is_explicit_and_missing_tool_is_error(tmp_path, monkeypatch):
    source = tmp_path / "requirements.txt"
    source.write_text("iniconfig==2.3.0\n")

    def missing(*args, **kwargs):
        raise FileNotFoundError("pip-audit")

    monkeypatch.setattr(core.subprocess, "run", missing)
    result = pip_audit.scan(str(tmp_path))
    assert result.errors and not result.passed and not result.skipped


def test_incomplete_report_never_reports_adapter_clean(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("iniconfig==2.3.0\n")
    monkeypatch.setattr(core, "run", lambda *a: subprocess.CompletedProcess([], 0, '{"dependencies":[]}', ""))
    result = pip_audit.scan(str(tmp_path))
    assert result.errors and not result.passed and not result.skipped


def test_explicit_dependency_free_project_needs_no_scanner(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="empty"\ndependencies=[]\n')
    monkeypatch.setattr(core, "run", lambda *a: pytest.fail("nothing to query"))
    result = pip_audit.scan(str(tmp_path))
    assert not result.errors and not result.skipped
    assert "explicitly dependency-free" in result.passed[0]
