"""Evidence contract for the agents-md lint dogfood run (#90)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_agents_md_dogfood_covers_this_repo_and_external_project() -> None:
    text = (REPO_ROOT / "docs" / "agents-md-lint-e2e.md").read_text(encoding="utf-8")

    assert "Codex Power Pack" in text
    assert "td-agentic" in text
    assert "Runtime boundary" in text
    assert "Secret handling" in text
    assert "no external files" in text
    assert "were modified during this dogfood run" in text
