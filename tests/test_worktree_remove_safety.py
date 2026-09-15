"""Safety contract for worktree removal (codex-power-pack#243).

Two defects are covered here, both of the same class: a guard whose absence is
indistinguishable from its success.

1. `scripts/worktree-remove.sh` was a 182-line hand-maintained orphan with no #597
   claim check and no uncommitted-work guard once `--force` was passed - and
   `--force` is what the ordinary cleanup path passes every time. It is deleted:
   the eight generated skill copies are the supported path, and a ninth hand-kept
   version matching neither the pin nor its siblings would be a new divergence.

2. The generated flow-merge / flow-auto references fell back to a RAW
   `git worktree remove "$WORKTREE_PATH" --force` when the guarded helper was
   absent. That fallback is blocked by git itself only on a LOCKED worktree (git
   demands `-f -f`); on an unlocked one it is completely unguarded for uncommitted
   work and unpushed commits. CPP fixed this in merge.md under #899 and left the
   same line raw in auto.md (claude-power-pack#973), so a pin bump would import it
   rather than remove it. The correction therefore lives in CxPP's overlay.

The overlay is an exact-string replacement, so it can silently stop matching when
upstream reflows. `test_overlay_assertion_fires_*` is the committed negative control
for that: it feeds text the replacement does NOT match and requires the generator to
raise. Without it, a no-op overlay and a working one produce identical green runs.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "codex_skills_sync.py"
_spec = importlib.util.spec_from_file_location("codex_skills_sync", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

RAW_FALLBACK = 'git worktree remove "$WORKTREE_PATH" --force'
CLAIM_MARKER = "flow-worktree-claim.sh"

GENERATED_ROOTS = (".codex/skills", "plugins/flow/skills")


# --- helpers parameterized on a tree root, so the identical assertion can be run
# --- against the PRE-FIX tree to prove these tests actually go red there.

def raw_fallback_sites(root: Path) -> list[str]:
    """Every generated file under `root` still carrying the raw --force fallback."""
    hits: list[str] = []
    for rel in GENERATED_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if RAW_FALLBACK in text:
                hits.append(f"{path.relative_to(root)}:{text.count(RAW_FALLBACK)}")
    return hits


def unguarded_remover_scripts(root: Path) -> list[str]:
    """Every worktree-remove.sh under `root` that lacks the #597 claim check."""
    offenders: list[str] = []
    for path in sorted(root.rglob("worktree-remove.sh")):
        if ".git/" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if CLAIM_MARKER not in text:
            offenders.append(str(path.relative_to(root)))
    return offenders


# --- 1. the artifact, not the source -----------------------------------------

def test_generated_skills_carry_no_raw_worktree_fallback() -> None:
    """The shipped artifact must contain zero raw fallbacks.

    This asserts against generated OUTPUT. Asserting that the overlay source
    contains the replacement string would pass in exactly the no-op case the
    overlay exists to prevent.
    """
    assert raw_fallback_sites(REPO_ROOT) == []


def test_generated_skills_carry_the_refusal_instead() -> None:
    """Zero raw fallbacks could also mean the block vanished entirely."""
    found = [
        str(p.relative_to(REPO_ROOT))
        for rel in GENERATED_ROOTS
        for p in sorted((REPO_ROOT / rel).rglob("reference.md"))
        if "REFUSING: worktree-remove.sh is missing" in p.read_text(encoding="utf-8")
    ]
    assert len(found) == 4, f"expected all four reference.md sites, got {found}"


# --- 2. the negative control on the overlay ----------------------------------

def _payload(text: str):
    return sync.PreparedPayload(text.encode(), 0o644)


def test_overlay_assertion_fires_when_replacement_stops_matching() -> None:
    """NEGATIVE CONTROL: a surviving raw fallback must fail generation loudly.

    This is the input that makes the instrument report the OTHER verdict. If this
    test ever passes without raising, the overlay's guard is blind and a silent
    no-op after an upstream reflow would ship the raw fallback with nothing
    reporting it.
    """
    files = {"reference.md": _payload(f"prose\n    {RAW_FALLBACK}\n    more\n")}
    with pytest.raises(sync.IntegrityError) as excinfo:
        sync._assert_worktree_fallback_removed(Path("flow-merge"), files)
    assert "reference.md" in str(excinfo.value)
    assert "did not apply" in str(excinfo.value)


def test_overlay_assertion_passes_on_clean_output() -> None:
    """The control must also be able to report CLEAN, or it is merely always-red."""
    files = {"reference.md": _payload("prose\n    echo REFUSING ...\n")}
    sync._assert_worktree_fallback_removed(Path("flow-merge"), files)


def test_overlay_replaces_both_upstream_fallback_shapes() -> None:
    """flow-merge and flow-auto indent the block differently; cover both."""
    for raw in (sync._RAW_WORKTREE_FALLBACK_MERGE, sync._RAW_WORKTREE_FALLBACK_AUTO):
        out = sync._adapt_flow_text(Path("flow-merge"), Path("reference.md"), raw)
        assert RAW_FALLBACK not in out, f"overlay did not replace: {raw!r}"
        assert "REFUSING: worktree-remove.sh is missing" in out


# --- 3. no unguarded remover survives in the tree ----------------------------

def test_no_worktree_remove_script_lacks_the_claim_check() -> None:
    """Every remaining copy carries #597. The deleted 182-line orphan did not."""
    assert unguarded_remover_scripts(REPO_ROOT) == []


def test_root_orphan_is_gone() -> None:
    assert not (REPO_ROOT / "scripts" / "worktree-remove.sh").exists()


# --- 4. the deleted orphan really did destroy work ---------------------------

def test_deleted_orphan_destroyed_uncommitted_work(tmp_path: Path) -> None:
    """Reconstructs the orphan from git history and proves it was a data-loss path.

    This is why the file was deleted rather than kept. It runs entirely inside
    tmp_path against a disposable fixture repo - never against a real worktree.
    Skipped, not silently passed, if the pre-deletion blob cannot be read.
    """
    fixture = REPO_ROOT / "tests" / "fixtures" / "worktree-remove-prefix-orphan.sh.txt"
    # Committed rather than read from git history on purpose: a `git show HEAD:`
    # lookup stops resolving the moment the deletion is committed, and would turn
    # this into a silent skip - a skipped control is not a control. The fixture is
    # inert (not executable, and deliberately not named worktree-remove.sh so the
    # reintroduction scan below does not match it).
    script = tmp_path / "orphan.sh"
    script.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    script.chmod(0o755)

    main = tmp_path / "repo"
    main.mkdir()
    run = lambda *a, cwd=main: subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    (main / "tracked.txt").write_text("base\n")
    run("git", "add", ".")
    run("git", "commit", "-qm", "init")
    wt = tmp_path / "wt"
    run("git", "worktree", "add", "-q", str(wt), "-b", "feature")
    if not wt.is_dir():
        pytest.skip("fixture worktree could not be created")

    (wt / "tracked.txt").write_text("PRECIOUS UNCOMMITTED EDIT\n")
    (wt / "untracked.txt").write_text("PRECIOUS UNTRACKED FILE\n")

    proc = subprocess.run(
        ["bash", str(script), str(wt), "--force"],
        cwd=main,
        capture_output=True,
        text=True,
    )
    # The point is not that it errored - it SUCCEEDED, and that is the defect.
    assert proc.returncode == 0, f"fixture did not exercise the path: {proc.stderr}"
    assert not (wt / "untracked.txt").exists(), (
        "the orphan did NOT destroy uncommitted work; the premise for deleting it"
        " does not hold and this test is no longer evidence of anything"
    )
