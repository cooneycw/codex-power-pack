"""Empty-input vacuity controls for the `make verify` sub-gates (issue #245).

A gate that reports success having examined nothing is indistinguishable from one
that examined everything and found it clean. Both print a cheerful line and exit 0,
and the difference is only ever found later, by someone relying on it. This module
is the committed negative-control battery: for each gate, an input that makes it
report the OTHER verdict.

PER-GATE TABLE. Every cell below was MEASURED at 0f0491d, not read off the source -
on a clean `git clone` whose unmutated control was green on all six scripts first.
"covered here" marks cells with an executable case in this module; the rest are
recorded measurements against gates that already refuse (they need a full repo
clone with real git provenance, which does not belong in a unit test).

  gate                    | empty-input verdict                      | known-bad verdict
  ------------------------|------------------------------------------|-------------------------------
  codex-skills-check      | exit 1, "MISSING: <path> (in manifest,    | exit 1, same (tree emptied)
                          |   not on disk)" - committed sha256        |
                          |   manifest refuses                        |
  harness-lint            | WAS exit 0, "0 markdown file(s) passed"   | exit 1, rule findings
                          |   for an empty AND a MISSING root;        |   (covered here)
                          |   now exit 3 (covered here)               |
  skill-contract-lint     | exit 1, stale generated files (baseline); | exit 1, package-drift
                          |   exit 1 inventory / exit 2 on a missing  |
                          |   root (lint) - committed contract        |
  project-next-check      | WAS exit 0, "bundle is current" with the  | exit 1, drift detected
                          |   package absent from BOTH sides;         |   (covered here)
                          |   now exit 3 (covered here)               |
  skill-eval-check        | exit 2, "filters selected zero evaluation | exit 1, activation_failure
                          |   cases" - already refuses (covered here) |   (required_text removed)

WHY harness-lint's GREEN IS LOAD-BEARING, which is what justifies changing it.
`codex_skills_sync.py` excludes LOCAL_SKILL_DIRS (29 of 85 skill dirs) from the
generated manifest, so their CONTENT is never hashed. `skill_contract_lint`'s
package-drift arm compares the installed copy against the packaged copy - it detects
a DIFFERENCE between two copies, not the presence of a construct - and regenerating
a skill writes both copies. Measured: an identical `CLAUDE.md` line appended to both
`.codex/skills/project-next/SKILL.md` and `plugins/project/skills/project-next/SKILL.md`,
verified byte-identical, leaves codex-skills-check, baseline, contract-lint and
skill-eval all at exit 0 - and only harness-lint at exit 1. For that set of skills it
is the sole content gate, so nothing downstream re-derives its verdict.

NOT claimed here: that `make verify` would go green against an emptied `.codex/skills`.
It would go RED - four of the five gates refuse. That scenario is already defended by
the committed manifest and contract; the LOCAL_SKILL_DIRS gap above is the real one.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves cls.__module__ through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


harness_lint = _load("harness_lint_vacuity", "scripts/harness_lint.py")
project_next_sync = _load("project_next_sync_vacuity", "scripts/project_next_sync.py")


# --------------------------------------------------------------------------
# harness-lint
# --------------------------------------------------------------------------

# One line per rule that MUST trip it. The universe is derived from RULES (see
# test_every_rule_has_a_control); only the samples are written by hand, so a new
# rule with no control fails the suite instead of shipping unexercised.
RULE_SAMPLES = {
    "agent-tool": "Dispatch it with the Agent tool when the work fans out.",
    "skill-tool": "Invoke it through the Skill tool rather than by hand.",
    "ask-user-question": "Use AskUserQuestion when the choice is the user's.",
    "claude-worktree-path": "Worktrees land under .claude/worktrees/<name>/ here.",
    "bang-command-prefix": "!ls -la",
    "claude-plugin-command": "Run /plugin to install it.",
    "claude-md-reference": "Read CLAUDE.md before starting.",
}

# Tokens that LOOK Claude-only but are not rules. This is the orchestrator's own
# near-miss encoded as a guard: its first known-bad fixture was built from these,
# passed, and nearly got harness-lint reported as blind. If a future rule starts
# matching one of these, this test fails and forces that to be a decision.
NON_RULE_TOKENS = (
    "Reach the peer with SendMessage when it is listed.",
    "Helpers are installed under ~/.claude/scripts/ on this host.",
    "Drive the issue with /flow:auto from the worktree.",
)


def _skill_tree(root: Path, *, skill: str = "some-skill", body: str = "") -> Path:
    skill_dir = root / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "reference.md").write_text(body, encoding="utf-8")
    return skill_dir


def _run_harness_lint(tmp_path: Path, skills_root: Path) -> int:
    # An allowlist path that does not exist reads as empty, isolating these cases
    # from whatever the repo's real allowlist happens to carry.
    return harness_lint.run_check(skills_root=skills_root, allowlist_path=tmp_path / "no-allowlist.txt")


def test_every_rule_has_a_control() -> None:
    """A rule with no sample line would ship unexercised by the cases below."""
    declared = {rule.id for rule in harness_lint.RULES}
    assert declared == set(RULE_SAMPLES), (
        "RULES and RULE_SAMPLES disagree; add a known-bad line for every rule. "
        f"missing={sorted(declared - set(RULE_SAMPLES))} extra={sorted(set(RULE_SAMPLES) - declared)}"
    )


@pytest.mark.parametrize("rule_id", sorted(RULE_SAMPLES))
def test_harness_lint_detects_each_rule(tmp_path: Path, rule_id: str) -> None:
    root = tmp_path / "skills"
    _skill_tree(root, body=RULE_SAMPLES[rule_id] + "\n")
    assert _run_harness_lint(tmp_path, root) == 1, f"rule {rule_id} did not fire on its own sample"


def test_non_rule_tokens_do_not_fire(tmp_path: Path) -> None:
    """Guards the near-miss: these are NOT rules, and a fixture built from them passes."""
    root = tmp_path / "skills"
    _skill_tree(root, body="\n".join(NON_RULE_TOKENS) + "\n")
    assert _run_harness_lint(tmp_path, root) == 0


def test_harness_lint_refuses_empty_root(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    assert _run_harness_lint(tmp_path, root) == 3


def test_harness_lint_refuses_missing_root(tmp_path: Path) -> None:
    """`_markdown_files` returns [] for a non-directory, which is what a rename produces."""
    assert _run_harness_lint(tmp_path, tmp_path / "definitely-not-here") == 3


def test_harness_lint_passes_a_scanned_clean_tree(tmp_path: Path) -> None:
    """The discriminator: without this, 'refuses empty' could just be 'always fails'."""
    root = tmp_path / "skills"
    _skill_tree(root, body="Nothing Claude-only lives in this file.\n")
    assert _run_harness_lint(tmp_path, root) == 0


def test_harness_lint_catches_construct_mirrored_into_both_copies(tmp_path: Path) -> None:
    """The LOCAL_SKILL_DIRS case: the construct is in BOTH copies, so package-drift
    sees no difference and the manifest never hashes it. harness-lint is the only
    gate left, which is why its vacuous pass mattered."""
    installed = tmp_path / "installed"
    packaged = tmp_path / "packaged"
    body = "Read CLAUDE.md before starting.\n"
    _skill_tree(installed, skill="project-next", body=body)
    _skill_tree(packaged, skill="project-next", body=body)

    a = (installed / "project-next" / "reference.md").read_bytes()
    b = (packaged / "project-next" / "reference.md").read_bytes()
    assert a == b, "fixture must mirror byte-for-byte, or it tests drift instead"

    assert _run_harness_lint(tmp_path, installed) == 1


# --------------------------------------------------------------------------
# project-next-check
# --------------------------------------------------------------------------


def _project_next_tree(tmp_path: Path, *, sources: dict[str, str], mirror: dict[str, str] | None) -> None:
    """Point the module's REPO_ROOT-derived constants at a scratch tree."""
    source_pkg = tmp_path / "lib" / "project_next"
    target_pkg = tmp_path / "plugins" / "project" / "lib" / "project_next"
    source_entry = tmp_path / "scripts" / "project-next.py"
    target_entry = tmp_path / "plugins" / "project" / "scripts" / "project-next.py"
    for directory in (source_pkg, target_pkg, source_entry.parent, target_entry.parent):
        directory.mkdir(parents=True, exist_ok=True)
    source_entry.write_text("# entry\n", encoding="utf-8")
    target_entry.write_text("# entry\n", encoding="utf-8")
    for name, text in sources.items():
        (source_pkg / name).write_text(text, encoding="utf-8")
    for name, text in (mirror or {}).items():
        (target_pkg / name).write_text(text, encoding="utf-8")

    project_next_sync.REPO_ROOT = tmp_path
    project_next_sync.SOURCE_PACKAGE = source_pkg
    project_next_sync.SOURCE_ENTRY = source_entry
    project_next_sync.TARGET_PACKAGE = target_pkg
    project_next_sync.TARGET_ENTRY = target_entry


def test_project_next_refuses_when_no_source_modules(tmp_path: Path) -> None:
    """Both sides absent with matching entry scripts used to print 'bundle is current'."""
    _project_next_tree(tmp_path, sources={}, mirror={})
    assert project_next_sync.check() == 3


def test_project_next_passes_when_mirrored(tmp_path: Path) -> None:
    """The discriminator for the refusal above."""
    _project_next_tree(tmp_path, sources={"rank.py": "VALUE = 1\n"}, mirror={"rank.py": "VALUE = 1\n"})
    assert project_next_sync.check() == 0


def test_project_next_refuses_a_py_directory_as_a_module(tmp_path: Path) -> None:
    """`glob("*.py")` matches directories; `source_files()` filters them with is_file().
    Guarding on a second glob would let this satisfy the guard while comparing nothing
    (found by Codex pre-PR review on #245)."""
    _project_next_tree(tmp_path, sources={}, mirror={})
    (project_next_sync.SOURCE_PACKAGE / "not_a_module.py").mkdir()
    assert project_next_sync.check() == 3


def test_project_next_refuses_a_dangling_symlink_as_a_module(tmp_path: Path) -> None:
    """Same class as the directory case: matched by the glob, excluded by is_file()."""
    _project_next_tree(tmp_path, sources={}, mirror={})
    (project_next_sync.SOURCE_PACKAGE / "ghost.py").symlink_to(tmp_path / "nowhere.py")
    assert project_next_sync.check() == 3


def test_project_next_detects_drift(tmp_path: Path) -> None:
    _project_next_tree(tmp_path, sources={"rank.py": "VALUE = 1\n"}, mirror={"rank.py": "VALUE = 2\n"})
    assert project_next_sync.check() == 1


# --------------------------------------------------------------------------
# skill-eval-check - already refuses; pinned so it cannot regress to a pass
# --------------------------------------------------------------------------


def test_skill_eval_refuses_zero_selected_cases() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/skill-eval.py", "deterministic", "--skill", "no-such-skill-exists"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2, completed.stderr
    assert "zero evaluation cases" in completed.stderr
