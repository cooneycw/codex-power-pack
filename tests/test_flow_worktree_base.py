"""FLOW_WORKTREE_BASE is honored in the CxPP flow skills (issue #136, ADR 0003).

Twin of claude-power-pack #584: the worktree base is configurable via the same
env var, with identical semantics. Default (unset) is the repo's parent dir - a
visible sibling (issue #133); set -> $FLOW_WORKTREE_BASE/<repo>-<branch>.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Both the generated Codex surface and its byte-identical plugin payload.
REFERENCE_FILES = [
    REPO_ROOT / ".codex" / "skills" / "flow-auto" / "reference.md",
    REPO_ROOT / ".codex" / "skills" / "flow-start" / "reference.md",
    REPO_ROOT / "plugins" / "flow" / "skills" / "flow-auto" / "reference.md",
    REPO_ROOT / "plugins" / "flow" / "skills" / "flow-start" / "reference.md",
]


@pytest.mark.parametrize("path", REFERENCE_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_worktree_base_is_configurable_with_visible_default(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # The knob is wired at the path-construction points.
    assert "FLOW_WORKTREE_BASE" in text

    # Default (unset) falls back to the repo's parent dir - the #133 visible sibling.
    assert 'WORKTREE_BASE="${FLOW_WORKTREE_BASE:-$(dirname "$MAIN_REPO")}"' in text

    # An overridden base is created if missing.
    assert '[ -n "$FLOW_WORKTREE_BASE" ] && mkdir -p "$WORKTREE_BASE"' in text

    # Dir naming is <repo>-<branch> for parity with CPP's $BASE/<repo>-<branch>.
    assert '"$WORKTREE_BASE/$(basename "$MAIN_REPO")-${BRANCH}"' in text  # fresh lane
    assert '"$WORKTREE_BASE/$(basename "$MAIN_REPO")-${LOCAL_BRANCH}"' in text  # pickup lane

    # The retired hidden path must not come back.
    assert ".codex/worktrees" not in text
