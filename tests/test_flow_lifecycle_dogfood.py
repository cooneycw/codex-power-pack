"""Evidence contract for the native flow lifecycle dogfood (#84)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_flow_lifecycle_transcript_uses_codex_worktrees_and_quality_gate() -> None:
    text = (REPO_ROOT / "docs" / "flow-lifecycle-e2e.md").read_text(encoding="utf-8")

    assert ".codex/worktrees" in text
    assert "make verify" in text
    assert "gitleaks-first Woodpecker checks" in text
    assert "Claude-specific" in text
