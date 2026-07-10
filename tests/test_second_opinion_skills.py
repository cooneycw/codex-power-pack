"""Contracts for host-managed second-opinion clients (#93)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".codex" / "skills"


def test_client_skills_check_service_and_degrade_without_leaking_credentials() -> None:
    for name in ("second-opinion-start", "second-opinion-models"):
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert "codex mcp get second-opinion" in text
    help_text = (SKILLS / "second-opinion-help" / "SKILL.md").read_text(encoding="utf-8")
    evaluate = (SKILLS / "evaluate-issue" / "SKILL.md").read_text(encoding="utf-8")
    assert "Second-opinion service unavailable" in help_text
    assert "start a local server" in help_text
    assert "single-model fallback" in evaluate
    assert "paste an API key" not in help_text + evaluate


def test_second_opinion_workflow_uses_multimodel_service_as_advisory() -> None:
    start = (SKILLS / "second-opinion-start" / "SKILL.md").read_text(encoding="utf-8")
    evaluate = (SKILLS / "evaluate-issue" / "SKILL.md").read_text(encoding="utf-8")

    assert "get_multi_model_second_opinion" in start
    assert "two or more selected models" in evaluate
    assert "single-model fallback" in evaluate
    assert "authoritative over any model response" in evaluate
