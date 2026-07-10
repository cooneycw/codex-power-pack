"""Keep the recorded friction-retro dogfood outcome safe and actionable."""

from pathlib import Path


def test_friction_retro_dogfood_records_safe_real_ledger_result() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "friction-retro-e2e.md").read_text()

    assert ".claude/friction.jsonl" in text
    assert "`8`" in text
    assert "validation-gate" in text
    assert "explicit user decision" in text
    assert "source summaries" in text
