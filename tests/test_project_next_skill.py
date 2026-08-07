"""Behavioral contract tests for the native project-next skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NATIVE_SKILL = REPO_ROOT / ".codex" / "skills" / "project-next" / "SKILL.md"
PLUGIN_SKILL = REPO_ROOT / "plugins" / "project" / "skills" / "project-next" / "SKILL.md"
RUNTIME_ENTRY = REPO_ROOT / "plugins" / "project" / "scripts" / "project-next.py"


def test_native_and_plugin_project_next_payloads_match() -> None:
    assert NATIVE_SKILL.read_bytes() == PLUGIN_SKILL.read_bytes()


def test_project_next_delegates_selection_to_the_deterministic_runtime() -> None:
    text = NATIVE_SKILL.read_text(encoding="utf-8")

    required_contract = (
        "bundled deterministic recommendation engine",
        "top_action",
        "next_startable_issue",
        "Only `available` issues can be named as safe to start.",
        "In-flight, blocked, cyclic, and uncertain issues remain non-startable.",
        "contract version `1.2`",
        "scripts/project-next.py",
    )

    for instruction in required_contract:
        assert instruction in text

    assert RUNTIME_ENTRY.is_file()
