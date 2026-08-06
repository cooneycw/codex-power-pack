"""Wave 7 Stage 2 invocation, metadata, and fresh-install contracts (#159)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.test_project_init_spec_kit_contract import validate

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / ".agents" / "skill-invocation-policy.json"
POLICY_SCHEMA_PATH = ROOT / ".agents" / "skill-invocation-policy.schema.json"
PLUGINS_ROOT = ROOT / "plugins"
SKILLS_ROOT = ROOT / ".codex" / "skills"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def policy() -> dict[str, Any]:
    return load_json(POLICY_PATH)


def family_skills() -> dict[str, set[str]]:
    return {
        plugin.name: {
            skill.name
            for skill in (plugin / "skills").iterdir()
            if skill.is_dir() and (skill / "SKILL.md").is_file()
        }
        for plugin in sorted(PLUGINS_ROOT.iterdir())
        if (plugin / ".codex-plugin" / "plugin.json").is_file()
    }


def implicit_names() -> set[str]:
    return {entry["name"] for entry in policy()["implicit_entrypoints"]}


def metadata(family: str, skill: str) -> dict[str, Any]:
    payload = yaml.safe_load(
        (PLUGINS_ROOT / family / "skills" / skill / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(payload, dict)
    return payload


def test_invocation_policy_validates_against_its_schema() -> None:
    schema = load_json(POLICY_SCHEMA_PATH)
    instance = policy()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    validate(instance, schema, schema)


def test_curated_implicit_metadata_matches_versioned_policy() -> None:
    actual: set[str] = set()
    for family, skills in family_skills().items():
        for skill in skills:
            payload = metadata(family, skill)
            if payload["policy"]["allow_implicit_invocation"]:
                actual.add(skill)

    assert implicit_names() == {"flow-auto", "project-next"}
    assert actual == implicit_names()
    assert "project-init" not in actual

    evaluation = load_json(ROOT / ".agents" / "skill-evaluation-cases.json")
    case_ids = {
        case["id"]
        for capture in evaluation["captures"]
        for case in capture["cases"]
    }
    for entry in policy()["implicit_entrypoints"]:
        assert set(entry["evidence_cases"]) <= case_ids


def test_plugin_versions_and_starters_resolve_to_bundled_skills() -> None:
    expected_version = policy()["payload_version"]
    for family, skills in family_skills().items():
        manifest = load_json(PLUGINS_ROOT / family / ".codex-plugin" / "plugin.json")
        assert manifest["version"] == expected_version

        starters = manifest["interface"]["defaultPrompt"]
        if isinstance(starters, str):
            starters = [starters]
        assert starters
        for starter in starters:
            selected = set(re.findall(r"\$([a-z][a-z0-9-]+)", starter))
            assert selected, f"{family}: starter does not explicitly select a bundled skill: {starter}"
            assert selected <= skills, f"{family}: starter selects {selected - skills} outside the plugin"


def test_profiles_are_unique_complete_and_preserve_priority_entrypoints() -> None:
    invocation_policy = policy()
    profiles = invocation_policy["profiles"]
    published = set(family_skills())
    priority_plugins = {entry["plugin"] for entry in invocation_policy["implicit_entrypoints"]}

    assert set(profiles["full"]) == published
    assert set(profiles["recommended"]) < published
    assert set(profiles["minimal"]) == {"cxpp"}
    assert len(profiles["recommended"]) == len(set(profiles["recommended"]))
    assert len(profiles["full"]) == len(set(profiles["full"]))
    assert priority_plugins <= set(profiles["recommended"])

    enabled_metadata_bytes = 0
    for family, skills in family_skills().items():
        for skill in skills & implicit_names():
            short_description = metadata(family, skill)["interface"]["short_description"]
            enabled_metadata_bytes += len(f"{family}:{skill}: {short_description}".encode())

    budgets = invocation_policy["budgets"]
    assert len(implicit_names()) <= budgets["recommended_max_implicit_entries"]
    assert len(implicit_names()) <= budgets["full_max_implicit_entries"]
    assert enabled_metadata_bytes <= budgets["full_max_entry_metadata_bytes"]


def test_priority_descriptions_state_goals_and_negative_boundaries() -> None:
    def frontmatter(skill: str) -> dict[str, Any]:
        text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
        payload = yaml.safe_load(text.split("---", 2)[1])
        assert isinstance(payload, dict)
        return payload

    flow_description = frontmatter("flow-auto")["description"]
    project_description = frontmatter("project-next")["description"]

    for description in (flow_description, project_description):
        assert "..." not in description
        assert "claude-power-pack" not in description.lower()
        assert "use" in description.lower()
        assert "do not use" in description.lower()


def test_project_init_is_explicit_local_and_negatively_routed() -> None:
    text = (SKILLS_ROOT / "project-init" / "SKILL.md").read_text(encoding="utf-8")
    payload = metadata("project", "project-init")

    assert payload["policy"]["allow_implicit_invocation"] is False
    for needle in [
        "new local Python project",
        "$project-lite",
        "$project-next",
        "GitHub publication",
        "$spec-adopt",
        "$spec-sync",
        "$cxpp-init",
        "ordinary changes",
        "only as separate",
        "reviewable handoffs",
    ]:
        assert needle in text

    for contradiction in [
        "zero to GitHub",
        "Python/Node/Go/Rust",
        "Installs the CPP toolkit",
        "Initializes `.specify/`",
    ]:
        assert contradiction not in text
        assert contradiction not in payload["interface"]["default_prompt"]


def test_user_guidance_contains_no_faux_skill_slash_commands() -> None:
    names = sorted({skill for skills in family_skills().values() for skill in skills}, key=len, reverse=True)
    bare = re.compile(
        r"(?<![A-Za-z0-9./])/(?!/)(" + "|".join(re.escape(name) for name in names) + r")(?![A-Za-z0-9_-])"
    )
    namespaced = re.compile(
        r"(?<![A-Za-z0-9./])/(?!/)([a-z][a-z0-9_-]+):([a-z][a-z0-9_-]+)"
    )
    replacements = {"cpp-init", "cpp-status", "cpp-update", "codex-code_review"}
    paths = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / ".codex" / "skills" / "README.md"]
    paths.extend(sorted(SKILLS_ROOT.glob("*/SKILL.md")))
    paths.extend(sorted(SKILLS_ROOT.glob("*/reference.md")))
    paths.extend(sorted(PLUGINS_ROOT.glob("*/skills/*/SKILL.md")))
    paths.extend(sorted(PLUGINS_ROOT.glob("*/skills/*/reference.md")))
    paths.extend([ROOT / "docs" / "HOST_MANAGED.md", ROOT / "docs" / "release-process.md"])

    violations = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        unresolved_namespaced = any(
            f"{match.group(1)}-{match.group(2)}" in set(names) | replacements
            for match in namespaced.finditer(text)
        )
        if bare.search(text) or unresolved_namespaced:
            violations.append(path.relative_to(ROOT).as_posix())
    assert not violations


def run_codex(codex: str, codex_home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        [codex, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )


@pytest.mark.parametrize("family", sorted(family_skills()))
def test_fresh_family_install_exposes_only_curated_implicit_entries(
    family: str, tmp_path: Path
) -> None:
    codex = shutil.which("codex")
    if codex is None:
        pytest.skip("Codex CLI is not installed")
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()

    run_codex(codex, codex_home, "plugin", "marketplace", "add", str(ROOT), "--json")
    run_codex(codex, codex_home, "plugin", "add", f"{family}@codex-power-pack", "--json")
    prompt = run_codex(codex, codex_home, "-C", str(tmp_path), "debug", "prompt-input")
    prompt_payload = json.loads(prompt.stdout)
    prompt_text = json.dumps(prompt_payload)

    skills = family_skills()[family]
    expected = skills & implicit_names()
    for skill in skills:
        entry = f"- {family}:{skill}:"
        assert (entry in prompt_text) is (skill in expected), entry


@pytest.mark.parametrize("profile_name", ["recommended", "full"])
def test_fresh_profile_inventory_is_unique_and_within_budget(
    profile_name: str, tmp_path: Path
) -> None:
    codex = shutil.which("codex")
    if codex is None:
        pytest.skip("Codex CLI is not installed")
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()

    run_codex(codex, codex_home, "plugin", "marketplace", "add", str(ROOT), "--json")
    for family in policy()["profiles"][profile_name]:
        run_codex(codex, codex_home, "plugin", "add", f"{family}@codex-power-pack", "--json")
    prompt = run_codex(codex, codex_home, "-C", str(tmp_path), "debug", "prompt-input")
    prompt_payload = json.loads(prompt.stdout)
    skills_text = prompt_payload[0]["content"][0]["text"]

    expected = {
        entry["name"]
        for entry in policy()["implicit_entrypoints"]
        if entry["plugin"] in policy()["profiles"][profile_name]
    }
    found = re.findall(r"- [a-z][a-z0-9-]+:([a-z][a-z0-9-]+):", skills_text)
    cxpp_found = [name for name in found if name in implicit_names()]
    assert set(cxpp_found) == expected
    assert len(cxpp_found) == len(set(cxpp_found))
    assert len(cxpp_found) <= policy()["budgets"][f"{profile_name}_max_implicit_entries"]
    entry_lines = [
        line for line in skills_text.splitlines() if line.startswith("- ") and " (file: " in line
    ]
    entry_metadata_bytes = len(("\n".join(entry_lines) + "\n").encode())
    assert entry_metadata_bytes <= policy()["budgets"]["full_max_entry_metadata_bytes"]
    if profile_name == "full":
        capture = policy()["fresh_full_suite_capture"]
        assert len(entry_lines) == capture["total_entries"]
        assert len(cxpp_found) == capture["cxpp_entries"]
        assert len(entry_lines) - len(cxpp_found) == capture["system_entries"]
        assert capture["entry_metadata_bytes"] <= policy()["budgets"][
            "full_max_entry_metadata_bytes"
        ]
