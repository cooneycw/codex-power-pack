"""Acceptance contracts for the CxPP documentation plugin (#91)."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = REPO_ROOT / "docs" / "architecture"
SKILLS = REPO_ROOT / ".codex" / "skills"


def test_c4_dogfood_outputs_are_github_renderable_mermaid() -> None:
    model = json.loads((ARCHITECTURE / "c4-model.json").read_text(encoding="utf-8"))
    assert {level["level"] for level in model["levels"]} == {"L1", "L2", "L3", "L4"}

    index = (ARCHITECTURE / "index.md").read_text(encoding="utf-8")
    assert index.count("```mermaid") == 4
    assert "flowchart" in index
    assert "classDiagram" in index

    manifest = json.loads((ARCHITECTURE / "c4-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["diagrams"]) == 4
    for diagram in manifest["diagrams"]:
        assert (ARCHITECTURE / diagram["file"]).is_file()


def test_documentation_skills_use_codex_pptx_and_no_retired_image_service() -> None:
    c4 = (SKILLS / "documentation-c4" / "SKILL.md").read_text(encoding="utf-8")
    pptx = (SKILLS / "documentation-pptx" / "SKILL.md").read_text(encoding="utf-8")

    assert "scripts/c4-mermaid.py" in c4
    assert "nano-banana" not in c4
    assert "Codex `$pptx` skill" in pptx
    assert "Anthropic" not in pptx
