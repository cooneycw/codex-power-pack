"""Regression checks for the plugin-era newcomer documentation."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_readme_quick_start_uses_marketplace_plugins_and_cxpp_bootstrap() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    quick_start = text.split("## Quick Start", 1)[1].split("## ", 1)[0]

    assert "codex plugin marketplace add" in quick_start
    assert "codex plugin add project@codex-power-pack" in quick_start
    assert "codex plugin add cxpp@codex-power-pack" in quick_start
    assert "/cxpp:init" in quick_start
    assert "git clone" not in quick_start


def test_canonical_docs_do_not_reintroduce_retired_install_surfaces() -> None:
    canonical_docs = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md"]
    retired_surfaces = [
        "scripts/skills_install_codex.py",
        "scripts/mcp_install_codex.py",
        ".codex/prompts/",
        "docs/skills/*-command-skill-map.md",
        "/plugin install",
    ]

    for path in canonical_docs:
        text = path.read_text(encoding="utf-8")
        for retired in retired_surfaces:
            assert retired not in text, f"{path.name}: {retired}"
