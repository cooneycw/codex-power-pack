"""Regression evidence for the fresh marketplace acceptance transcript (#99)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fresh_marketplace_transcript_covers_install_scaffold_and_sync() -> None:
    text = (REPO_ROOT / "docs" / "plugin-marketplace-fresh-e2e.md").read_text(encoding="utf-8")

    for needle in [
        "project@codex-power-pack",
        "spec@codex-power-pack",
        "github@codex-power-pack",
        "cxpp@codex-power-pack",
        "make verify",
        "Initial Codex project scaffold",
        "#122",
        "#123",
        "idempotency",
    ]:
        assert needle in text
