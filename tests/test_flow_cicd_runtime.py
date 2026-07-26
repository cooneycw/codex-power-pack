"""CxPP-owned deterministic runner selection for Codex flow skills (#142)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
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
FLOW_FINISH_GATE_HELPERS = (
    "flow-auto/scripts/flow-finish-gate.sh",
    "flow-check/scripts/flow-finish-gate.sh",
    "flow-finish/scripts/flow-finish-gate.sh",
    "flow-merge/scripts/flow-finish-gate.sh",
)


def test_codex_flow_references_delegate_to_bundled_finish_gate() -> None:
    for rel in FLOW_RUNNER_REFERENCES:
        source = (REPO_ROOT / ".codex/skills" / rel).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "plugins/flow/skills" / rel).read_text(encoding="utf-8")

        assert source == packaged
        assert "<SKILL_DIR>/scripts/flow-finish-gate.sh" in source


def test_marketplace_and_checkout_runtime_layouts_are_adapted() -> None:
    for indent in ("", "   ", "    "):
        upstream = (
            f'{indent}CPP_DIR=""\n'
            f"{indent}for dir in ~/Projects/claude-power-pack /opt/claude-power-pack "
            "~/.claude-power-pack; do\n"
            f'{indent}  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then\n'
            f'{indent}    CPP_DIR="$dir"\n'
            f"{indent}    break\n"
            f"{indent}  fi\n"
            f"{indent}done\n"
            f'{indent}PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" '
            "python -m lib.cicd run --plan finish\n"
        )
        skill_dir = REPO_ROOT / "upstream" / "flow-auto"
        adapted = sync._adapt_flow_cicd_runtime(skill_dir, Path("reference.md"), upstream)

        # Both relative layouts are emitted: .codex/skills/<skill> and
        # plugins/flow/skills/<skill> (including the installed marketplace copy).
        assert f'{indent}"<SKILL_DIR>/../../.."' in adapted
        assert f'{indent}"<SKILL_DIR>/../../../.."' in adapted
        assert adapted.index("$HOME/Projects/codex-power-pack") < adapted.index(
            "$HOME/Projects/claude-power-pack"
        )
        assert '[ -d "$dir/lib/cicd" ]' in adapted
        assert f'{indent}if [ "$CICD_RUNTIME_KIND" = "cxpp" ]; then' in adapted
        assert "uv run python -m lib.cicd run --plan finish" in adapted


def test_finish_gate_helpers_prefer_cxpp_and_provision_runtime_dependencies() -> None:
    for rel in FLOW_FINISH_GATE_HELPERS:
        source = (REPO_ROOT / ".codex/skills" / rel).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "plugins/flow/skills" / rel).read_text(encoding="utf-8")

        assert source == packaged
        assert 'SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)' in source
        assert source.index("$HOME/Projects/codex-power-pack") < source.index(
            "$HOME/Projects/claude-power-pack"
        )
        assert 'CICD_RUNTIME_KIND="cxpp"' in source
        assert 'CICD_RUNTIME_KIND="cpp-compat"' in source
        assert 'uv run --project "$CPP_DIR" --extra dev python -m lib.cicd' in source
        assert 'uv run --project "$CPP_DIR" python -m lib.cicd' in source


def test_finish_gate_executes_cxpp_runner_with_dev_extra(tmp_path: Path) -> None:
    cxpp = tmp_path / "cxpp"
    (cxpp / "lib" / "cicd").mkdir(parents=True)
    (cxpp / "AGENTS.md").write_text("# fixture\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    invocation = tmp_path / "uv-invocation.txt"
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n%s\\n" "$*" "$UV_CACHE_DIR" > "$FLOW_GATE_TEST_INVOCATION"\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    helper = REPO_ROOT / ".codex/skills/flow-auto/scripts/flow-finish-gate.sh"
    sandbox_tmp = tmp_path / "tmp"
    sandbox_tmp.mkdir()
    env = os.environ | {
        "FLOW_GATE_CPP_DIR": str(cxpp),
        "FLOW_GATE_TEST_INVOCATION": str(invocation),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TMPDIR": str(sandbox_tmp),
    }
    env.pop("UV_CACHE_DIR", None)
    result = subprocess.run(
        [str(helper)],
        cwd=tmp_path,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "FLOW_FINISH_GATE: ok" in result.stdout
    assert invocation.read_text(encoding="utf-8").splitlines() == [
        f"run --project {cxpp} --extra dev python -m lib.cicd run --plan finish",
        str(sandbox_tmp / "codex-power-pack-uv-cache"),
    ]


def test_deploy_verification_command_is_not_rewritten() -> None:
    upstream = (
        'PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" '
        "python -m lib.cicd verify\n"
    )
    skill_dir = REPO_ROOT / "upstream" / "flow-auto"

    assert sync._adapt_flow_cicd_runtime(skill_dir, Path("reference.md"), upstream) == upstream


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
