"""Release process checks for pinned marketplace distribution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_DOC = REPO_ROOT / "docs" / "release-process.md"
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_process_documents_version_and_tag_gates() -> None:
    text = read_text(RELEASE_DOC).lower()

    for required in [
        "semantic versioning",
        "major version",
        "minor version",
        "patch version",
        "signed release tag",
        "resolved commit sha",
        "git tag -s",
        "make verify",
        "changelog.md",
    ]:
        assert required in text


def test_release_process_documents_explicit_upgrade_and_rollback() -> None:
    text = read_text(RELEASE_DOC).lower()

    for required in [
        "codex plugin marketplace add cooneycw/codex-power-pack",
        "--ref",
        "codex plugin add",
        "fresh codex config",
        "upgrade transcript",
        "rollback",
        "previous plugin ref",
        "new plugin ref",
    ]:
        assert required in text


def test_release_process_matches_marketplace_pinning_policy() -> None:
    text = read_text(RELEASE_DOC).lower()
    marketplace = load_json(MARKETPLACE_PATH)

    accepted_refs = {
        accepted_ref
        for entry in marketplace["plugins"]
        for accepted_ref in entry["pinning"]["acceptedRefs"]
    }

    assert accepted_refs == {"immutable-commit-sha", "signed-release-tag"}
    for accepted_ref in accepted_refs:
        assert accepted_ref.replace("-", " ") in text or accepted_ref in text
    assert "codex plugin marketplace add --ref" in text


def test_distribution_docs_link_release_process() -> None:
    for relative in [
        "README.md",
        "AGENTS.md",
        "docs/plugin-marketplace-project-e2e.md",
    ]:
        assert "docs/release-process.md" in read_text(REPO_ROOT / relative)
