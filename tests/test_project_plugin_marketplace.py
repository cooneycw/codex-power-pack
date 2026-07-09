"""Native marketplace scaffold tests for the first CxPP plugin."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "project"
GENERATED_SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"
PLUGIN_SKILLS_ROOT = PLUGIN_ROOT / "skills"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_marketplace_entry() -> dict:
    marketplace = load_json(MARKETPLACE_PATH)
    matches = [entry for entry in marketplace["plugins"] if entry.get("name") == "project"]
    assert len(matches) == 1
    return matches[0]


def test_repo_marketplace_exposes_project_plugin() -> None:
    marketplace = load_json(MARKETPLACE_PATH)

    assert marketplace["name"] == "codex-power-pack"
    assert marketplace["interface"]["displayName"] == "Codex Power Pack"

    entry = project_marketplace_entry()
    assert entry["source"] == {
        "source": "local",
        "path": "./plugins/project",
    }
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["category"] == "Developer Tools"


def test_project_marketplace_entry_declares_pinning_policy() -> None:
    pinning = project_marketplace_entry()["pinning"]

    assert pinning["required"] is True
    assert pinning["mode"] == "git-ref"
    assert pinning["acceptedRefs"] == [
        "immutable-commit-sha",
        "signed-release-tag",
    ]
    assert pinning["resolvedBy"] == "codex plugin marketplace add --ref"


def test_project_plugin_manifest_is_native_codex_shape() -> None:
    manifest = load_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")

    assert manifest["name"] == "project"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["repository"] == "https://github.com/cooneycw/codex-power-pack"
    assert manifest["license"] == "MIT"
    assert manifest["interface"]["displayName"] == "Project"
    assert manifest["interface"]["category"] == "Developer Tools"
    assert manifest["interface"]["capabilities"] == ["Automation", "Write"]


def test_project_plugin_skills_match_generated_source() -> None:
    expected_roots = [
        GENERATED_SKILLS_ROOT / "project-help",
        GENERATED_SKILLS_ROOT / "project-init",
    ]
    source_files: dict[str, Path] = {}
    for source_root in expected_roots:
        for source_file in source_root.rglob("*"):
            if source_file.is_file():
                rel = f"{source_root.name}/{source_file.relative_to(source_root).as_posix()}"
                source_files[rel] = source_file

    plugin_files = {
        path.relative_to(PLUGIN_SKILLS_ROOT).as_posix(): path
        for path in PLUGIN_SKILLS_ROOT.rglob("*")
        if path.is_file()
    }

    assert set(plugin_files) == set(source_files)
    for rel, source_file in source_files.items():
        assert sha256(plugin_files[rel]) == sha256(source_file), rel
