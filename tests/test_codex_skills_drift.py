"""Drift gate for the generated Codex skills pulled from claude-power-pack.

codex-power-pack#75: `.codex/skills/` is generated from CPP's `.claude/commands/`
single source (pull model) and vendored here pinned by commit SHA. These tests are
the pytest face of `scripts/codex_skills_sync.py --check` - they replace the former
per-family `test_*_skill_trigger_parity.py` suite, whose premise (a local
`.claude/commands/` fork + `.codex/prompts/` + `agents/openai.yaml` skill structure)
this issue deletes.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "codex_skills_sync.py"
_spec = importlib.util.spec_from_file_location("codex_skills_sync", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


def _skill_dirs() -> list[Path]:
    return sorted(d for d in sync.SKILLS_ROOT.iterdir() if d.is_dir())


def _generated_skill_dirs() -> list[Path]:
    return sorted(d for d in _skill_dirs() if d.name not in sync.LOCAL_SKILL_DIRS)


def test_skills_tree_in_sync_with_pin() -> None:
    """A hand-edit, addition, or deletion under generated skill dirs fails this gate."""
    assert sync.run_check() == 0


def test_manifest_covers_every_generated_file() -> None:
    assert sync.compute_manifest() == sync.read_manifest()


def test_every_skill_carries_the_generated_marker() -> None:
    for skill_dir in _generated_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file(), f"{skill_dir.name}: no SKILL.md"
        assert sync.MARKER_PREFIX in skill_md.read_text(), (
            f"{skill_dir.name}: SKILL.md is not generated-from-CPP (missing marker)"
        )


def test_native_cxpp_skills_are_present_without_generated_marker() -> None:
    for skill_name in sync.LOCAL_SKILL_DIRS:
        skill_md = sync.SKILLS_ROOT / skill_name / "SKILL.md"
        assert skill_md.is_file(), f"{skill_name}: no SKILL.md"
        assert sync.MARKER_PREFIX not in skill_md.read_text()
        assert all(not rel.startswith(f"{skill_name}/") for rel in sync.read_manifest())


def test_excluded_and_retired_generated_families_are_absent() -> None:
    # claude-md is Out-of-Scope for CxPP. The native spec-adopt and spec-sync
    # directories are explicitly covered by LOCAL_SKILL_DIRS above, so this
    # assertion protects only the retired generated family.
    forbidden = ("claude-md-",)
    offenders = [d.name for d in _skill_dirs() if d.name.startswith(forbidden)]
    assert offenders == [], f"unexpected skill dirs present: {offenders}"


def test_pin_records_a_claude_power_pack_commit() -> None:
    assert sync.PIN_PATH.is_file(), "vendor/claude-power-pack/PIN is missing"
    text = sync.PIN_PATH.read_text()
    assert "claude-power-pack" in text
    assert re.search(r"^commit: [0-9a-f]{40}$", text, re.MULTILINE), "PIN has no pinned commit SHA"


def test_current_flow_resolver_is_part_of_the_vendored_manifest() -> None:
    manifest = sync.read_manifest()
    required = {
        "flow-auto/scripts/flow-start-resolve.sh",
        "flow-start/scripts/flow-start-resolve.sh",
    }

    assert required <= manifest.keys()


def test_refresh_source_selection_never_overwrites_native_skills(tmp_path: Path) -> None:
    skills = tmp_path / "codex" / "skills"
    for name in ("flow-auto", "project-next", "project-lite"):
        skill_dir = skills / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("fixture", encoding="utf-8")

    selected = {path.name for path in sync._source_skill_dirs(tmp_path)}

    assert "flow-auto" in selected
    assert "project-next" not in selected
    assert "project-lite" not in selected
