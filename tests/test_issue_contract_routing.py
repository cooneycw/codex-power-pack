"""Structural #221 routing regressions, not proof of live agent policy compliance.

The authored worked cases require semantic review. These tests check concrete
forms, maintained links, installed guidance, scaffold output and negative controls.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "docs/agents/issue-contract.md"
URL = "https://github.com/cooneycw/codex-power-pack/blob/main/" + CONTRACT
NATIVE = {
    "evaluate-issue": "evaluate",
    "project-init": "project",
    "spec-adopt": "spec",
    "spec-sync": "spec",
}
ROUTES = {
    "AGENTS.md": CONTRACT,
    ".specify/memory/constitution.md": "../../" + CONTRACT,
    "docs/skills/spec-driven-dev.md": "../agents/issue-contract.md",
    ".specify/templates/spec-template.md": URL,
    ".specify/templates/plan-template.md": URL,
    ".specify/templates/tasks-template.md": URL,
    ".github/ISSUE_TEMPLATE/feature-request.yml": URL,
    ".github/ISSUE_TEMPLATE/bug-report.yml": URL,
}
RETIRED = re.compile(r"/spec:(?:create|sync)|/github:issue-create|/project:init")


def _route_errors(text: str, target: str) -> list[str]:
    errors = []
    if f"]({target})" not in text:
        errors.append("missing canonical route")
    if RETIRED.search(text):
        errors.append("retired active command")
    return errors


def _form_errors(text: str) -> list[str]:
    form = yaml.safe_load(text)
    fields = {field["id"]: field for field in form["body"] if "id" in field}
    errors = []
    if not fields["problem"]["validations"]["required"]:
        errors.append("missing outcome requirement")
    for optional in ("solution", "constraints"):
        if fields[optional]["validations"]["required"]:
            errors.append("mandatory " + optional)
    return errors


@pytest.mark.parametrize("relative,target", ROUTES.items())
def test_repository_routes_resolve_to_the_one_authored_contract(relative: str, target: str) -> None:
    source = ROOT / relative
    assert not _route_errors(source.read_text(), target)
    if target.startswith("https:"):
        resolved = ROOT / target.removeprefix("https://github.com/cooneycw/codex-power-pack/blob/main/")
    else:
        resolved = source.parent / target
    assert resolved.resolve() == (ROOT / CONTRACT).resolve()
    assert resolved.is_file()


@pytest.mark.parametrize("name,family", NATIVE.items())
def test_native_and_independently_installed_plugin_route_to_cxpp(
    name: str, family: str, tmp_path: Path
) -> None:
    local = ROOT / ".codex/skills" / name / "SKILL.md"
    packaged = ROOT / "plugins" / family / "skills" / name / "SKILL.md"
    assert local.read_bytes() == packaged.read_bytes()
    installed = tmp_path / "plugin-cache" / name / "SKILL.md"
    installed.parent.mkdir(parents=True)
    shutil.copyfile(packaged, installed)
    foreign_doc = tmp_path / "unrelated-project" / CONTRACT
    foreign_doc.parent.mkdir(parents=True)
    foreign_doc.write_text("Foreign policy: proposals are mandatory.\n")
    text = installed.read_text()
    assert not _route_errors(text, URL)
    assert "](../../../docs/agents/issue-contract.md)" not in text
    assert "unavailable" in text or "missing remote" in text
    assert (ROOT / CONTRACT).is_file()


def test_generated_authoring_reference_routes_portably_and_preserves_repo_selection() -> None:
    local = ROOT / ".codex/skills/github-issue-create/reference.md"
    packaged = ROOT / "plugins/github/skills/github-issue-create/reference.md"
    assert local.read_bytes() == packaged.read_bytes()
    text = local.read_text()
    assert not _route_errors(text, URL)
    assert "Proposed approach (optional, and recorded as revisable)" in text
    assert "reference is unavailable" in text
    assert '--repo "$REPO"' in text
    assert "$github-issue-create" in text


def test_feature_form_accepts_outcome_without_a_proposal_or_spec() -> None:
    text = (ROOT / ".github/ISSUE_TEMPLATE/feature-request.yml").read_text()
    assert not _form_errors(text)
    fields = {field["id"]: field for field in yaml.safe_load(text)["body"] if "id" in field}
    assert "revisable" in fields["solution"]["attributes"]["label"]
    assert "rationale" in fields["constraints"]["attributes"]["description"]
    assert not {"spec", "plan", "tasks", "assumptions"} & fields.keys()


def test_bug_form_retains_observed_expected_and_reproduction_without_extra_requirements() -> None:
    text = (ROOT / ".github/ISSUE_TEMPLATE/bug-report.yml").read_text()
    fields = {field["id"]: field for field in yaml.safe_load(text)["body"] if "id" in field}
    assert {key for key, field in fields.items() if field["validations"]["required"]} == {
        "component", "description", "reproduce"
    }
    assert "What happened" in fields["description"]["attributes"]["placeholder"]
    assert "Expected behavior" in fields["description"]["attributes"]["placeholder"]


@pytest.mark.parametrize("packaged", [False, True])
def test_actual_scaffold_has_portable_contract_without_spec_or_git(tmp_path: Path, packaged: bool) -> None:
    script = ROOT / (
        "plugins/project/skills" if packaged else ".codex/skills"
    ) / "project-init/scripts/project-scaffold.py"
    target = tmp_path / "short-project"
    result = subprocess.run(
        [sys.executable, str(script), "short-project", "--path", str(target)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    agents = (target / "AGENTS.md").read_text()
    assert not _route_errors(agents, URL)
    assert "unavailable" in agents
    assert not (target / ".specify").exists()
    assert not (target / ".git").exists()
    assert not list(target.rglob("spec.md"))


def test_negative_controls_detect_broken_route_mandatory_proposal_and_retired_command() -> None:
    text = (ROOT / ".codex/skills/project-init/SKILL.md").read_text()
    assert _route_errors(text.replace(URL, URL + ".missing"), URL) == ["missing canonical route"]
    assert _route_errors(text + "\nUse /spec:create now.\n", URL) == ["retired active command"]
    form = yaml.safe_load((ROOT / ".github/ISSUE_TEMPLATE/feature-request.yml").read_text())
    next(field for field in form["body"] if field.get("id") == "solution")["validations"]["required"] = True
    assert _form_errors(yaml.safe_dump(form)) == ["mandatory solution"]


@pytest.mark.parametrize("name", ["spec", "plan", "tasks"])
def test_copied_full_spec_templates_keep_the_portable_route(tmp_path: Path, name: str) -> None:
    output = tmp_path / ".specify/specs/001-example" / f"{name}.md"
    output.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / f".specify/templates/{name}-template.md", output)
    assert not _route_errors(output.read_text(), URL)
