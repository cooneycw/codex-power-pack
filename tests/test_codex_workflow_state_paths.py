from __future__ import annotations

import os
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
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    git_dir = main_repo / ".git"
    git_dir.mkdir()
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_git = bin_dir / "git"
    fake_git.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "rev-parse" ] && [ "$2" = "--git-common-dir" ]; then\n'
        '  printf "%s\\n" "$GIT_COMMON_DIR"\n'
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)

    env = os.environ.copy()
    env["GIT_COMMON_DIR"] = str(git_dir)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

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
        cwd=worktree,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (main_repo / ".codex" / "friction.jsonl").is_file()
    assert not (worktree / ".codex" / "friction.jsonl").exists()
    assert not (main_repo / ".claude" / "friction.jsonl").exists()
