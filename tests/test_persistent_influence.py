"""Consent, idempotency, conflict, and removal contracts for CxPP influence."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "cxpp-influence.py"
TEMPLATE = ROOT / ".agents" / "routing-block.md"
SCAFFOLD = ROOT / ".codex/skills/project-init/scripts/project-scaffold.py"


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), *(str(arg) for arg in args)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_routing_asset_is_bounded_and_packaged_helper_is_identical() -> None:
    assert len(TEMPLATE.read_bytes()) <= 1024
    assert (ROOT / "plugins/cxpp/assets/routing-block.md").read_bytes() == TEMPLATE.read_bytes()
    assert (ROOT / "plugins/cxpp/scripts/cxpp-influence.py").read_bytes() == HELPER.read_bytes()


def test_install_preview_decline_current_and_remove_are_consent_first(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Local guidance\n", encoding="utf-8")
    original = agents.read_bytes()

    preview = run("preview", tmp_path)
    assert preview.returncode == 0 and "cxpp-routing:start" in preview.stdout
    assert agents.read_bytes() == original
    assert run("apply", tmp_path).returncode == 3
    assert agents.read_bytes() == original
    assert "skipped by user" in run("decline", tmp_path).stdout
    assert agents.read_bytes() == original

    assert run("apply", tmp_path, "--approve").returncode == 0
    installed = agents.read_bytes()
    assert b"cxpp-routing:start" in installed
    assert "current" in run("status", tmp_path).stdout
    assert "already current" in run("apply", tmp_path, "--approve").stdout
    assert agents.read_bytes() == installed

    remove_preview = run("preview-remove", tmp_path)
    assert remove_preview.returncode == 0 and "cxpp-routing:start" in remove_preview.stdout
    assert agents.read_bytes() == installed
    assert run("remove", tmp_path).returncode == 3
    assert agents.read_bytes() == installed
    assert run("remove", tmp_path, "--approve").returncode == 0
    assert agents.read_text(encoding="utf-8") == "# Local guidance\n"


def test_upgrade_is_owned_and_user_edits_become_conflicts(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    assert run("apply", tmp_path, "--approve").returncode == 0
    prior = tmp_path / "prior.md"
    prior.write_text("prior managed body\n", encoding="utf-8")
    assert run("status", tmp_path, "--template", prior).stdout.startswith("inspected")

    # A new template upgrades only a block whose marker still authenticates its body.
    newer = tmp_path / "newer.md"
    newer.write_text("new managed body\n", encoding="utf-8")
    assert "upgrade" in run("status", tmp_path, "--template", newer).stdout
    assert run("apply", tmp_path, "--template", newer, "--approve").returncode == 0
    assert "new managed body" in agents.read_text(encoding="utf-8")

    agents.write_text(agents.read_text(encoding="utf-8").replace("new managed", "user changed"), encoding="utf-8")
    conflict = run("apply", tmp_path, "--template", newer, "--approve")
    assert conflict.returncode == 2
    assert "conflict" in conflict.stderr
    assert "user changed body" in agents.read_text(encoding="utf-8")


def test_project_init_decline_leaves_only_the_local_scaffold(tmp_path: Path) -> None:
    text = (ROOT / ".codex/skills/project-init/SKILL.md").read_text(encoding="utf-8")
    assert "$cxpp-init" in text
    assert "persistent" in text.lower()
    project = tmp_path / "demo"
    scaffold = subprocess.run(
        [sys.executable, str(SCAFFOLD), "demo", "--path", str(project)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert scaffold.returncode == 0, scaffold.stderr
    before = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    assert b"cxpp-routing:start" not in before[Path("AGENTS.md")]
    assert not list(project.rglob("hooks.json"))

    assert run("decline", project).returncode == 0
    after = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    assert after == before
