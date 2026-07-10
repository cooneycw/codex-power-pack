"""Native marketplace scaffold tests for CxPP per-family plugins."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGINS_ROOT = REPO_ROOT / "plugins"
GENERATED_SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"

PINNING_POLICY = {
    "required": True,
    "mode": "git-ref",
    "acceptedRefs": [
        "immutable-commit-sha",
        "signed-release-tag",
    ],
    "resolvedBy": "codex plugin marketplace add --ref",
}

FAMILY_SKILLS = {
    "project": ["project-help", "project-init", "project-lite", "project-next"],
    "spec": ["spec-adopt", "spec-sync"],
    "flow": [
        "flow-auto",
        "flow-check",
        "flow-cleanup",
        "flow-deploy",
        "flow-doctor",
        "flow-eli5",
        "flow-finish",
        "flow-help",
        "flow-merge",
        "flow-start",
        "flow-status",
        "flow-sync",
    ],
    "github": [
        "github-help",
        "github-issue-close",
        "github-issue-create",
        "github-issue-list",
        "github-issue-update",
        "github-issue-view",
    ],
    "cicd": [
        "cicd-check",
        "cicd-container",
        "cicd-health",
        "cicd-help",
        "cicd-infra-discover",
        "cicd-infra-init",
        "cicd-infra-pipeline",
        "cicd-init",
        "cicd-pipeline",
        "cicd-smoke",
        "cicd-verify",
    ],
    "secrets": [
        "secrets-delete",
        "secrets-get",
        "secrets-help",
        "secrets-list",
        "secrets-rotate",
        "secrets-run",
        "secrets-set",
        "secrets-ui",
        "secrets-validate",
    ],
    "woodpecker": [
        "woodpecker-help",
        "woodpecker-logs",
        "woodpecker-restart",
        "woodpecker-status",
    ],
    "security": [
        "security-deep",
        "security-explain",
        "security-help",
        "security-permissions",
        "security-quick",
        "security-scan",
    ],
    "agents-md": ["agents-md-help", "agents-md-lint"],
    "documentation": ["documentation-c4", "documentation-help", "documentation-pptx"],
    "qa": ["qa-help", "qa-test"],
    "evaluate": ["evaluate-help", "evaluate-issue"],
    "second-opinion": ["second-opinion-help", "second-opinion-models", "second-opinion-start"],
    "self-improvement": [
        "self-improvement-deployment",
        "self-improvement-help",
        "self-improvement-retro",
    ],
    "cxpp": ["cxpp-init", "cxpp-status", "cxpp-update"],
}

EXPECTED_FAMILIES = list(FAMILY_SKILLS)
CORE_BUDGET_FAMILIES = ("project", "spec", "github")
SKILL_LIST_BUDGET_CHARS = 8_000


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marketplace_entries() -> dict[str, dict[str, Any]]:
    marketplace = load_json(MARKETPLACE_PATH)
    return {entry["name"]: entry for entry in marketplace["plugins"]}


def source_files_for_skill(skill_name: str) -> dict[str, Path]:
    source_root = GENERATED_SKILLS_ROOT / skill_name
    return {
        f"{skill_name}/{source_file.relative_to(source_root).as_posix()}": source_file
        for source_file in source_root.rglob("*")
        if source_file.is_file()
    }


def packaged_files_for_family(family: str) -> dict[str, Path]:
    plugin_skills_root = PLUGINS_ROOT / family / "skills"
    return {
        path.relative_to(plugin_skills_root).as_posix(): path
        for path in plugin_skills_root.rglob("*")
        if path.is_file()
    }


def load_agent_manifest(family: str, skill_name: str) -> dict[str, Any]:
    path = PLUGINS_ROOT / family / "skills" / skill_name / "agents" / "openai.yaml"
    assert path.is_file(), f"{family}/{skill_name}: missing agents/openai.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_repo_marketplace_exposes_all_family_plugins() -> None:
    marketplace = load_json(MARKETPLACE_PATH)

    assert marketplace["name"] == "codex-power-pack"
    assert marketplace["interface"]["displayName"] == "Codex Power Pack"

    entries = marketplace["plugins"]
    assert [entry["name"] for entry in entries] == EXPECTED_FAMILIES

    for entry in entries:
        family = entry["name"]
        assert entry["source"] == {
            "source": "local",
            "path": f"./plugins/{family}",
        }
        assert entry["policy"] == {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        }
        assert entry["pinning"] == PINNING_POLICY
        assert isinstance(entry["category"], str) and entry["category"]


def test_each_family_plugin_manifest_is_native_codex_shape() -> None:
    entries = marketplace_entries()

    for family in EXPECTED_FAMILIES:
        manifest = load_json(PLUGINS_ROOT / family / ".codex-plugin" / "plugin.json")

        assert manifest["name"] == family
        assert manifest["version"] == "0.1.0"
        assert manifest["skills"] == "./skills/"
        assert manifest["repository"] == "https://github.com/cooneycw/codex-power-pack"
        assert manifest["license"] == "MIT"
        assert manifest["interface"]["displayName"]
        assert manifest["interface"]["category"] == entries[family]["category"]
        assert manifest["interface"]["capabilities"]
        assert manifest["interface"]["defaultPrompt"]


def test_plugin_skill_payloads_match_generated_source_with_metadata_overlay() -> None:
    for family, expected_skills in FAMILY_SKILLS.items():
        plugin_files = packaged_files_for_family(family)
        expected_source_files: dict[str, Path] = {}
        expected_agent_files: set[str] = set()

        for skill_name in expected_skills:
            expected_source_files.update(source_files_for_skill(skill_name))
            expected_agent_files.add(f"{skill_name}/agents/openai.yaml")

        expected_files = set(expected_source_files) | expected_agent_files
        if not expected_skills:
            expected_files.add(".gitkeep")

        assert set(plugin_files) == expected_files, family

        for rel, source_file in expected_source_files.items():
            assert sha256(plugin_files[rel]) == sha256(source_file), rel


def test_packaged_skills_disable_implicit_invocation_by_default() -> None:
    for family, expected_skills in FAMILY_SKILLS.items():
        for skill_name in expected_skills:
            payload = load_agent_manifest(family, skill_name)

            interface = payload["interface"]
            assert interface["display_name"]
            assert interface["short_description"]
            assert interface["default_prompt"].startswith(f"Use ${skill_name}")
            assert payload["policy"]["allow_implicit_invocation"] is False


def test_github_issue_skills_resolve_the_target_repository() -> None:
    """Issue #85: GitHub commands must work outside the CPP checkout."""
    github_skills = FAMILY_SKILLS["github"]

    for skill_name in github_skills:
        text = (GENERATED_SKILLS_ROOT / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        reference = GENERATED_SKILLS_ROOT / skill_name / "reference.md"
        if reference.exists():
            text += reference.read_text(encoding="utf-8")

        assert "cooneycw/claude-power-pack" not in text, skill_name

    for skill_name in [
        "github-issue-create",
        "github-issue-list",
        "github-issue-view",
        "github-issue-update",
        "github-issue-close",
    ]:
        text = (GENERATED_SKILLS_ROOT / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        reference = GENERATED_SKILLS_ROOT / skill_name / "reference.md"
        if reference.exists():
            text += reference.read_text(encoding="utf-8")

        assert 'gh repo view --json nameWithOwner --jq .nameWithOwner' in text
        assert '--repo "$REPO"' in text


def test_core_family_skill_list_stays_under_budget() -> None:
    """The initial project/spec/github install stays below the Codex skill-list budget."""
    skill_list_text = []
    for family in CORE_BUDGET_FAMILIES:
        for skill_name in FAMILY_SKILLS[family]:
            skill_md = PLUGINS_ROOT / family / "skills" / skill_name / "SKILL.md"
            payload = load_agent_manifest(family, skill_name)
            skill_list_text.append(skill_md.read_text(encoding="utf-8").split("---", 2)[1])
            skill_list_text.append(payload["interface"]["short_description"])

    assert len("\n".join(skill_list_text)) < SKILL_LIST_BUDGET_CHARS
