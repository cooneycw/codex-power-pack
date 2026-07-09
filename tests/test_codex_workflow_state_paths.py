from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_flow_skills_do_not_reference_claude_worktree_state() -> None:
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / ".codex" / "skills").glob("flow-*/*.md")):
        if ".claude/worktrees" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_friction_log_defaults_to_codex_buffer(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)

    script = REPO_ROOT / ".codex" / "skills" / "flow-auto" / "scripts" / "friction-log.sh"
    subprocess.run(
        [
            str(script),
            "--class",
            "red-output",
            "--signal",
            "test signal",
            "--run",
            "test",
            "--step",
            "state-paths",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (repo / ".codex" / "friction.jsonl").is_file()
    assert not (repo / ".claude" / "friction.jsonl").exists()
