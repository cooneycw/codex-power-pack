"""CxPP-owned deterministic runner selection for Codex flow skills (#142)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from lib.cicd.runner import DeterministicRunner
from lib.cicd.steps import StepDef

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = REPO_ROOT / "scripts" / "codex_skills_sync.py"
_spec = importlib.util.spec_from_file_location("codex_skills_sync_runtime", SYNC_PATH)
assert _spec is not None and _spec.loader is not None
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

FLOW_RUNNER_REFERENCES = (
    "flow-auto/reference.md",
    "flow-finish/reference.md",
    "flow-merge/reference.md",
)


def test_codex_flow_references_prefer_cxpp_with_explicit_cpp_fallback() -> None:
    for rel in FLOW_RUNNER_REFERENCES:
        source = (REPO_ROOT / ".codex/skills" / rel).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "plugins/flow/skills" / rel).read_text(encoding="utf-8")

        assert source == packaged
        assert "<SKILL_DIR>/../../.." in source
        assert "<SKILL_DIR>/../../../.." in source
        assert source.index("$HOME/Projects/codex-power-pack") < source.index(
            "$HOME/Projects/claude-power-pack"
        )
        assert "claude-power-pack is an explicit compatibility fallback only" in source
        assert '[ -d "$dir/lib/cicd" ]' in source
        assert '[ -f "$dir/AGENTS.md" ] || [ -f "$dir/CLAUDE.md" ]' in source
        assert 'CICD_RUNTIME_KIND="cxpp"' in source
        assert 'CICD_RUNTIME_KIND="cpp-compat"' in source
        assert "uv run python -m lib.cicd" in source
        assert 'uv run --project "$CPP_DIR" python -m lib.cicd' in source


def test_marketplace_and_checkout_runtime_layouts_are_adapted() -> None:
    upstream = (
        "CPP_DIR=\"\"\n"
        "for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do\n"
        "  if [ -d \"$dir\" ] && [ -f \"$dir/CLAUDE.md\" ]; then\n"
        "    CPP_DIR=\"$dir\"\n"
        "    break\n"
        "  fi\n"
        "done\n"
        'PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" '
        "python -m lib.cicd run --plan finish\n"
    )
    skill_dir = REPO_ROOT / "upstream" / "flow-auto"
    adapted = sync._adapt_flow_cicd_runtime(skill_dir, Path("reference.md"), upstream)

    # Both relative layouts are emitted: .codex/skills/<skill> and
    # plugins/flow/skills/<skill> (including the installed marketplace copy).
    assert '"<SKILL_DIR>/../../.."' in adapted
    assert '"<SKILL_DIR>/../../../.."' in adapted
    assert adapted.index("$HOME/Projects/codex-power-pack") < adapted.index(
        "$HOME/Projects/claude-power-pack"
    )
    assert '[ -d "$dir/lib/cicd" ]' in adapted
    assert 'if [ "$CICD_RUNTIME_KIND" = "cxpp" ]; then' in adapted
    assert "uv run python -m lib.cicd run --plan finish" in adapted


def test_finish_runner_preserves_valid_newer_project_environment(tmp_path: Path) -> None:
    """A >=3.11 project with an existing 3.12 venv is never re-bootstrapped."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n',
        encoding="utf-8",
    )
    venv = tmp_path / ".venv"
    venv.mkdir()
    pyvenv = venv / "pyvenv.cfg"
    original = "version = 3.12.9\n"
    pyvenv.write_text(original, encoding="utf-8")
    marker = tmp_path / "finish-count.txt"

    steps = [
        StepDef(
            id="lint",
            command=f"printf 'lint\\n' >> {marker}",
            description="focused lint",
        ),
        StepDef(
            id="test",
            command=f"printf 'test\\n' >> {marker}",
            description="focused tests",
        ),
    ]
    result = DeterministicRunner(project_root=tmp_path).run("finish", steps)

    assert result.success
    assert pyvenv.read_text(encoding="utf-8") == original
    assert marker.read_text(encoding="utf-8").splitlines() == ["lint", "test"]
