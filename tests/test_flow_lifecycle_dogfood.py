"""Evidence contract for the native flow lifecycle dogfood (#84)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_flow_lifecycle_transcript_uses_sibling_worktree_and_quality_gate() -> None:
    text = (REPO_ROOT / "docs" / "flow-lifecycle-e2e.md").read_text(encoding="utf-8")

    # Worktrees are visible siblings of the repo, not hidden under .codex/ (issue #133).
    assert "git worktree add" in text
    assert "../codex-power-pack-issue-127" in text
    assert ".codex/worktrees" not in text
    assert "make verify" in text
    assert "gitleaks-first Woodpecker checks" in text
    assert "Claude-specific" in text
