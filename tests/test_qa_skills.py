"""Acceptance contracts for the Codex-native QA plugin (#92)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".codex" / "skills"


def test_qa_skill_uses_native_playwright_and_codex_config() -> None:
    text = (SKILLS / "qa-test" / "SKILL.md").read_text(encoding="utf-8")
    assert "@playwright/mcp" in text
    assert ".codex/qa.yml" in text
    assert ".claude/qa.yml" not in text
    assert "ask for explicit confirmation" in text


def test_qa_dogfood_fixture_and_transcript_are_present() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "qa-dogfood" / "index.html"
    test = REPO_ROOT / "tests" / "qa-dogfood.spec.cjs"
    transcript = REPO_ROOT / "docs" / "plugin-marketplace-qa-e2e.md"

    assert fixture.is_file()
    assert test.is_file()
    assert "consoleErrors" in test.read_text(encoding="utf-8")
    assert "1 passed" in transcript.read_text(encoding="utf-8")
