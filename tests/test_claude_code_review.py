"""Guardrails and git-context tests for the Claude review escalation."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    REPO_ROOT
    / ".codex"
    / "skills"
    / "claude-code-review"
    / "scripts"
    / "claude_code_review.py"
)
SYNC_PATH = REPO_ROOT / "scripts" / "codex_skills_sync.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


runner = _load(RUNNER_PATH, "claude_code_review")
sync = _load(SYNC_PATH, "codex_skills_sync_claude_review")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_review_context_includes_worktree_diff(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    source = tmp_path / "app.py"
    source.write_text("answer = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "app.py")
    _git(tmp_path, "commit", "-m", "initial")
    _git(tmp_path, "switch", "-c", "issue-1-review")
    source.write_text("answer = 2\n", encoding="utf-8")

    prompt = runner.build_review_context(tmp_path, "main", "Issue 1", "Tests fail")

    assert "Issue 1" in prompt
    assert "Tests fail" in prompt
    assert "+answer = 2" in prompt
    assert "-answer = 1" in prompt


def test_sdk_runner_is_read_only_and_isolated() -> None:
    assert runner.READ_ONLY_TOOLS == ["Read", "Glob", "Grep"]
    for tool in ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task", "Agent"):
        assert tool in runner.DISALLOWED_TOOLS
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "strict_mcp_config=True" in source
    assert "setting_sources=[]" in source
    assert "skills=[]" in source
    assert "plugins=[]" in source
    assert 'permission_mode="dontAsk"' in source


def test_flow_auto_overlay_adds_bounded_claude_escalation() -> None:
    upstream = """If implementation hits a blocker that cannot be resolved:
- **STOP** and report the blocker.
- Suggest manual intervention."""
    skill_dir = REPO_ROOT / "upstream" / "flow-auto"

    adapted = sync._adapt_flow_claude_review(skill_dir, Path("reference.md"), upstream)

    assert "$claude-code-review" in adapted
    assert "two materially distinct" in adapted
    assert "once for that blocker fingerprint" in adapted
    assert "Claude is read-only support" in adapted


def test_flow_auto_payloads_match_and_include_escalation() -> None:
    source = (REPO_ROOT / ".codex/skills/flow-auto/reference.md").read_text(encoding="utf-8")
    packaged = (
        REPO_ROOT / "plugins/flow/skills/flow-auto/reference.md"
    ).read_text(encoding="utf-8")

    assert source == packaged
    assert "$claude-code-review" in source
