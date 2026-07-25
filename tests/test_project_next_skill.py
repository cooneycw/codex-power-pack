"""Behavioral contract tests for the native project-next skill."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NATIVE_SKILL = REPO_ROOT / ".codex" / "skills" / "project-next" / "SKILL.md"
PLUGIN_SKILL = REPO_ROOT / "plugins" / "project" / "skills" / "project-next" / "SKILL.md"


def test_native_and_plugin_project_next_payloads_match() -> None:
    assert NATIVE_SKILL.read_bytes() == PLUGIN_SKILL.read_bytes()


def test_project_next_has_a_hard_in_flight_exclusion_gate() -> None:
    text = NATIVE_SKILL.read_text(encoding="utf-8")

    required_contract = (
        "git worktree list --porcelain",
        "closingIssuesReferences",
        "IN_FLIGHT_ISSUES",
        "DEPENDENCY_MAP",
        "BLOCKED_ISSUES",
        "AVAILABLE_ISSUES",
        'Choose a "next issue to start" only from `AVAILABLE_ISSUES`.',
        "Never place an issue from `IN_FLIGHT_ISSUES` or `BLOCKED_ISSUES`",
        "Keep in-flight issues in this graph so their dependents remain blocked.",
        "Unmapped worktrees:",
    )

    for instruction in required_contract:
        assert instruction in text
