"""Installed-flow helper and currency contracts (issue #139)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

LOAD_BEARING_REFERENCES = [
    REPO_ROOT / ".codex/skills/flow-auto/reference.md",
    REPO_ROOT / ".codex/skills/flow-start/reference.md",
    REPO_ROOT / ".codex/skills/flow-merge/reference.md",
]

RESOLVERS = [
    REPO_ROOT / ".codex/skills/flow-auto/scripts/flow-start-resolve.sh",
    REPO_ROOT / ".codex/skills/flow-start/scripts/flow-start-resolve.sh",
    REPO_ROOT / "plugins/flow/skills/flow-auto/scripts/flow-start-resolve.sh",
    REPO_ROOT / "plugins/flow/skills/flow-start/scripts/flow-start-resolve.sh",
]


@pytest.mark.parametrize("path", LOAD_BEARING_REFERENCES, ids=lambda path: path.parent.name)
def test_load_bearing_helpers_resolve_from_the_installed_skill(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    assert "<SKILL_DIR>" in text
    assert "never interpret bundled helper paths relative to the target repository" in text
    assert "~/.claude/scripts/" not in text


@pytest.mark.parametrize("path", RESOLVERS, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_resolver_uses_codex_visible_sibling_git_lane(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    assert path.is_file()
    assert path.stat().st_mode & 0o111
    assert "PROJECT" in text
    assert "GIT_LANE=1" in text
    assert 'echo "$(dirname "$TARGET_REPO")/$(basename "$TARGET_REPO")-$1"' in text
    assert '.claude/worktrees' not in text


def test_plugin_payloads_carry_the_same_installed_skill_contract() -> None:
    for skill in ("flow-auto", "flow-start", "flow-merge"):
        source = REPO_ROOT / ".codex/skills" / skill / "reference.md"
        packaged = REPO_ROOT / "plugins/flow/skills" / skill / "reference.md"
        assert packaged.read_bytes() == source.read_bytes()


def test_flow_doctor_checks_the_installed_plugin_helper_family() -> None:
    text = (REPO_ROOT / ".codex/skills/flow-doctor/reference.md").read_text(encoding="utf-8")

    assert 'FLOW_SKILLS_ROOT="<SKILL_DIR>/.."' in text
    assert "reinstall or upgrade flow@codex-power-pack" in text
    assert "Flow helper(s) not at ~/.claude/scripts/" not in text


def test_ci_runs_live_upstream_currency_gate() -> None:
    pipeline = (REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "codex-skills-currency:" in pipeline
    assert "--source-check --cpp-root /tmp/claude-power-pack-current" in pipeline
    assert "codex-skills-currency-check:" in makefile


@pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash",
)
def test_bundled_resolver_creates_default_visible_sibling(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=origin, check=True)
    (origin / "fixture.txt").write_text("fixture\n", encoding="utf-8")

    git_env = os.environ.copy()
    git_env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(["git", "add", "fixture.txt"], cwd=origin, env=git_env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=origin, env=git_env, check=True)

    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True)
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$*\" in\n"
        "  *\"--json state\"*) echo OPEN ;;\n"
        "  *\"--json title\"*) echo 'Fix bundled flow' ;;\n"
        "  *\"pr list\"*) echo none ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    env = git_env | {"FLOW_START_RESOLVE_GH": str(fake_gh)}
    env.pop("FLOW_WORKTREE_BASE", None)
    result = subprocess.run(
        ["bash", str(RESOLVERS[0]), "42"],
        cwd=checkout,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    contract = dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line and not line.startswith("FLOW_START")
    )

    expected = tmp_path / "checkout-issue-42-fix-bundled-flow"
    assert contract["GIT_LANE"] == "1"
    assert contract["WT_CREATED"] == "1"
    assert contract["WT_PATH"] == str(expected)
    assert expected.is_dir()
