from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "harness_lint.py"
_spec = importlib.util.spec_from_file_location("harness_lint", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
harness_lint = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = harness_lint
_spec.loader.exec_module(harness_lint)


def _write_skill(root: Path, name: str, skill_md: str, reference_md: str = "") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(skill_md)
    if reference_md:
        (skill_dir / "reference.md").write_text(reference_md)


def _skill_with_adaptation(term: str) -> str:
    return f"""---
name: adapted
description: adapted fixture
---

## Codex harness adaptations

- {term}: Codex-safe replacement is documented here.

# Adapted Skill
"""


def test_real_skill_tree_has_no_unadapted_claude_only_constructs() -> None:
    assert harness_lint.lint_skills() == []


def test_each_rule_flags_unadapted_skill_text(tmp_path: Path) -> None:
    cases = {
        "agent-tool": "Use the Agent tool to delegate this work.",
        "skill-tool": "Use the Skill tool before acting.",
        "ask-user-question": "Use AskUserQuestion to collect missing input.",
        "claude-worktree-path": "Open .claude/worktrees/issue-1 before editing.",
        "bang-command-prefix": "! pytest tests",
        "claude-plugin-command": "Run /plugin install example.",
        "claude-md-reference": "Update CLAUDE.md after changing commands.",
    }

    for rule_id, body in cases.items():
        root = tmp_path / rule_id
        _write_skill(
            root,
            "bad-skill",
            "---\nname: bad\n---\n# Bad Skill\n",
            body,
        )
        findings = harness_lint.lint_skills(root, root / "missing-allowlist.txt")
        assert [finding.rule_id for finding in findings] == [rule_id]


def test_matching_codex_adaptation_allows_reference_text(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(
        root,
        "project-init",
        _skill_with_adaptation("AskUserQuestion"),
        "Use AskUserQuestion to ask the user directly.",
    )

    assert harness_lint.lint_skills(root, root / "missing-allowlist.txt") == []


def test_adaptation_block_itself_is_not_a_violation(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(
        root,
        "flow-start",
        _skill_with_adaptation(".claude/worktrees"),
    )

    assert harness_lint.lint_skills(root, root / "missing-allowlist.txt") == []


def test_reviewed_allowlist_requires_reason_and_allows_exact_finding(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    allowlist = tmp_path / "allowlist.txt"
    _write_skill(
        root,
        "help",
        "---\nname: help\n---\n# Help\n",
        "Run /plugin only when documenting the legacy Claude path.",
    )

    allowlist.write_text(
        "claude-plugin-command|help/reference.md|legacy Claude path|documents historical migration path\n"
    )
    assert harness_lint.lint_skills(root, allowlist) == []

    allowlist.write_text("claude-plugin-command|help/reference.md|legacy Claude path|\n")
    try:
        harness_lint.lint_skills(root, allowlist)
    except ValueError as exc:
        assert "expected rule|path|needle|reason" in str(exc)
    else:
        raise AssertionError("invalid allowlist entry did not fail")
