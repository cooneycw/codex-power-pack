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

CI_STATUS_HELPER = REPO_ROOT / ".codex/skills/flow-auto/scripts/flow-ci-status.sh"
MERGE_HELPER = REPO_ROOT / ".codex/skills/flow-auto/scripts/gh-pr-merge.sh"


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


def test_flow_docs_do_not_publish_deferred_claude_runtime_contracts() -> None:
    flow_auto = (REPO_ROOT / ".codex/skills/flow-auto/reference.md").read_text(
        encoding="utf-8"
    )
    flow_help = (REPO_ROOT / ".codex/skills/flow-help/reference.md").read_text(
        encoding="utf-8"
    )
    flow_eli5 = (REPO_ROOT / ".codex/skills/flow-eli5/reference.md").read_text(
        encoding="utf-8"
    )

    assert "/codex:auto" not in flow_auto
    assert "/qwen:auto" not in flow_auto
    assert "/gemma:auto" not in flow_auto
    assert "/plugin" not in flow_help
    assert ".claude/security.yml" not in flow_help
    assert "/plugin" not in flow_eli5


def test_ci_separates_exact_pin_integrity_from_latest_upstream_reporting() -> None:
    pipeline = (REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "codex-skills-pin-integrity:" in pipeline
    assert "--pin-ref" in pipeline
    assert "make codex-skills-pin-check CPP_ROOT=/tmp/claude-power-pack-pinned" in pipeline
    assert "codex-skills-upstream-report:" in pipeline
    assert "--latest-ref" in pipeline
    assert "cron: codex-skills-upstream-report" in pipeline
    assert "make codex-skills-upstream-report CPP_ROOT=/tmp/claude-power-pack-current" in pipeline
    assert "codex-skills-pin-check:" in makefile
    assert "codex-skills-currency-check:" in makefile
    assert "codex-skills-upstream-report:" in makefile


@pytest.mark.parametrize(
    "args, missing",
    [
        ([], "SHA is required"),
        (["a" * 40], "--path is required"),
        (["a" * 40, "--path", "."], "--repo is required"),
    ],
)
def test_ci_status_requires_explicit_sha_path_and_repository(
    args: list[str], missing: str
) -> None:
    result = subprocess.run(
        [str(CI_STATUS_HELPER), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 2
    assert missing in result.stderr


def _write_executable(path: Path, text: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + text, encoding="utf-8")
    path.chmod(0o755)


def _merge_stubs(
    tmp_path: Path, *, check_state: str, required: bool, protection_failure: bool = False
) -> tuple[dict[str, str], Path]:
    calls = tmp_path / "merge-calls.log"
    gh = tmp_path / "gh"
    required_line = "echo required-context" if required else ":"
    merge_result = (
        "echo \"failed to merge pull request: GraphQL: You're not authorized to "
        "push to this branch. (mergePullRequest)\" >&2; exit 1"
        if protection_failure
        else "exit 0"
    )
    _write_executable(
        gh,
        f'echo "gh $*" >> "{calls}"\n'
        'if [[ "$1 $2" == "pr list" ]]; then exit 0; fi\n'
        'if [[ "$1" == "api" ]]; then\n'
        '  if [[ "$2" == *"/protection/required_status_checks"* ]]; then '
        f'{required_line}; fi\n'
        '  exit 0\n'
        'fi\n'
        'if [[ "$1 $2" == "repo view" ]]; then\n'
        '  if [[ "$*" == *defaultBranchRef* ]]; then echo main; '
        'elif [[ "$*" == *nameWithOwner* ]]; then echo cooneycw/codex-power-pack; '
        'else echo ADMIN; fi\n'
        '  exit 0\n'
        'fi\n'
        'if [[ "$1 $2" == "pr view" ]]; then\n'
        '  if [[ "$*" == *baseRefName* ]]; then echo main; '
        f'elif [[ "$*" == *statusCheckRollup* ]]; then echo "required-context|{check_state}"; '
        'elif [[ "$*" == *mergeable* ]]; then echo MERGEABLE; '
        'elif [[ "$*" == *reviewDecision* ]]; then :; '
        'elif [[ "$*" == *mergeCommit* ]]; then :; '
        'elif [[ "$*" == *"--json state"* ]]; then echo OPEN; '
        'else :; fi\n'
        '  exit 0\n'
        'fi\n'
        f'if [[ "$1 $2" == "pr merge" ]]; then {merge_result}; fi\n'
        'exit 0\n',
    )
    git = tmp_path / "git"
    _write_executable(
        git,
        f'echo "git $*" >> "{calls}"\n'
        'if [[ "$*" == *"rev-parse --show-toplevel"* ]]; then pwd; '
        'elif [[ "$*" == *"rev-parse refs/remotes/origin/main"* ]]; then printf "%040d\\n" 1; '
        'elif [[ "$*" == *"rev-parse HEAD^{tree}"* ]]; then printf "%040d\\n" 2; '
        'elif [[ "$*" == "rev-parse HEAD" ]]; then printf "%040d\\n" 3; '
        'elif [[ "$*" == *"merge-base --is-ancestor"* ]]; then exit 1; fi\n'
        'exit 0\n',
    )
    env = os.environ | {
        "GH_PR_MERGE_GH": str(gh),
        "GH_PR_MERGE_GIT": str(git),
        "GH_PR_MERGE_CHECK_ATTEMPTS": "1",
        "GH_PR_MERGE_CHECK_DELAY": "0",
        "GH_PR_MERGE_POLL_DELAY": "0",
        "GH_PR_MERGE_BASE_RETRY_DELAY": "0",
    }
    env.pop("WOODPECKER_API_TOKEN", None)
    env.pop("WOODPECKER_SERVER", None)
    return env, calls


@pytest.mark.parametrize("check_state", ["FAILURE", "PENDING", "UNKNOWN"])
def test_merge_helper_refuses_failed_pending_or_unknown_required_checks(
    tmp_path: Path, check_state: str
) -> None:
    (tmp_path / ".git").write_text("gitdir: /fixture/worktree\n", encoding="utf-8")
    env, calls = _merge_stubs(tmp_path, check_state=check_state, required=True)
    result = subprocess.run(
        [str(MERGE_HELPER), "196", "issue-196-fixture"],
        cwd=tmp_path,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    assert not any(
        line.startswith("gh pr merge") for line in calls.read_text().splitlines()
    )


def test_merge_helper_never_automatically_retries_with_admin(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /fixture/worktree\n", encoding="utf-8")
    env, calls = _merge_stubs(
        tmp_path,
        check_state="SUCCESS",
        required=False,
        protection_failure=True,
    )
    result = subprocess.run(
        [str(MERGE_HELPER), "196", "issue-196-fixture"],
        cwd=tmp_path,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    merge_calls = [
        line for line in calls.read_text().splitlines() if line.startswith("gh pr merge")
    ]
    assert result.returncode == 1
    assert len(merge_calls) == 1
    assert "--admin" not in merge_calls[0]
    assert "refusing an automatic --admin retry" in result.stderr


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
