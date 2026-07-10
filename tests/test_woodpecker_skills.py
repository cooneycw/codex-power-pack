"""Contracts for the Codex-native Woodpecker client skills (#88)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".codex" / "skills"


def _skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def test_woodpecker_client_skills_use_secrets_run_without_exposing_tokens() -> None:
    for name in ("woodpecker-status", "woodpecker-logs", "woodpecker-restart"):
        text = _skill(name)
        assert "$secrets-run" in text
        assert "WOODPECKER_TOKEN" in text
        assert "echo $WOODPECKER_TOKEN" not in text
        assert "Authorization: Bearer" in text


def test_log_skill_decodes_woodpecker_api_base64_payload() -> None:
    text = _skill("woodpecker-logs")
    assert 'jq -r ".data" | base64 --decode' in text
    assert "never print the token" in text.lower()


def test_restart_skill_requires_explicit_pipeline_confirmation() -> None:
    text = _skill("woodpecker-restart")
    assert "Ask for explicit confirmation" in text
    assert "POST" in text
