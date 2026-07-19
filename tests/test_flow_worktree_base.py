"""FLOW_WORKTREE_BASE is honored in the CxPP flow skills (issue #136, ADR 0003).

Twin of claude-power-pack #584: the worktree base is configurable via the same
env var, with identical semantics. Default (unset) is the repo's parent dir - a
visible sibling (issue #133); set -> $FLOW_WORKTREE_BASE/<repo>-<branch>.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Both generated resolver copies and their byte-identical plugin payloads.
RESOLVER_FILES = [
    REPO_ROOT / ".codex" / "skills" / "flow-auto" / "scripts" / "flow-start-resolve.sh",
    REPO_ROOT / ".codex" / "skills" / "flow-start" / "scripts" / "flow-start-resolve.sh",
    REPO_ROOT / "plugins" / "flow" / "skills" / "flow-auto" / "scripts" / "flow-start-resolve.sh",
    REPO_ROOT / "plugins" / "flow" / "skills" / "flow-start" / "scripts" / "flow-start-resolve.sh",
]


@pytest.mark.parametrize("path", RESOLVER_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_worktree_base_is_configurable_with_visible_default(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # The knob is wired at the path-construction points.
    assert "FLOW_WORKTREE_BASE" in text

    # Default (unset) falls back to the repo's parent dir - the #133 visible sibling.
    assert 'echo "$(dirname "$TARGET_REPO")/$(basename "$TARGET_REPO")-$1"' in text

    # An overridden base is created if missing, and both lanes use plain git.
    assert '[ -n "${FLOW_WORKTREE_BASE:-}" ] && mkdir -p "$FLOW_WORKTREE_BASE"' in text
    assert 'echo "$FLOW_WORKTREE_BASE/$(basename "$TARGET_REPO")-$1"' in text
    assert "GIT_LANE=1" in text

    # The retired hidden path must not come back.
    assert ".codex/worktrees" not in text
    assert ".claude/worktrees" not in text
