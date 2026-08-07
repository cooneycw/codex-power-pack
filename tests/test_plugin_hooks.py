"""Security and lifecycle contracts for reviewed persistent plugin hooks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "plugins/secrets"
RETRO = ROOT / "plugins/self-improvement"
TRANSITION = ROOT / "scripts/cxpp-hook-transition.py"


def hook_commands(plugin: Path) -> list[str]:
    hooks = json.loads((plugin / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    return [entries[0]["hooks"][0]["command"] for entries in hooks.values()]


def invoke(
    script: Path,
    payload: str,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def invoke_hook_command(command: str, plugin_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input="{}",
        capture_output=True,
        text=True,
        shell=True,
        executable="/bin/sh",
        check=False,
        env={**os.environ, "PLUGIN_ROOT": str(plugin_root)},
    )


def plugin_payload(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def install_plugin_fixture(parent: Path, family: str, version: str, marker: str) -> Path:
    source = SECRETS if family == "secrets" else RETRO
    destination = parent / family / version
    shutil.copytree(source, destination)
    script = destination / "scripts" / (
        "hook-mask-output.py" if family == "secrets" else "friction-hook.py"
    )
    script.write_text(script.read_text(encoding="utf-8") + f"\n# {marker}\n", encoding="utf-8")
    return destination


def fake_codex(tmp_path: Path) -> Path:
    executable = tmp_path / "codex"
    executable.write_text(
        """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path

family = sys.argv[3].split("@", 1)[0]
home = Path(os.environ["CODEX_HOME"])
target = home / "plugins/cache/codex-power-pack" / family
candidate = Path(os.environ["CXPP_TEST_CANDIDATES"]) / family
shutil.rmtree(target, ignore_errors=True)
if os.environ.get("CXPP_TEST_FAIL_FAMILY") == family:
    raise SystemExit(9)
shutil.copytree(candidate, target)
print("{}")
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def run_transition(
    home: Path,
    executable: Path,
    candidates: Path,
    *families: str,
    fail_family: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(TRANSITION),
        "reinstall",
        "--codex-home",
        str(home),
        "--codex-bin",
        str(executable),
    ]
    for family in families:
        command.extend(("--family", family))
    command.append("--approve")
    env = {**os.environ, "CXPP_TEST_CANDIDATES": str(candidates)}
    if fail_family is not None:
        env["CXPP_TEST_FAIL_FAMILY"] = fail_family
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def test_manifests_use_plugin_relative_reviewed_hooks() -> None:
    secrets_manifest = json.loads((SECRETS / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    retro_manifest = json.loads((RETRO / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert secrets_manifest["hooks"] == "./hooks/hooks.json"
    assert retro_manifest["hooks"] == "./hooks/hooks.json"

    secrets_hooks = json.loads((SECRETS / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    retro_hooks = json.loads((RETRO / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(secrets_hooks) == {"PostToolUse"}
    assert set(retro_hooks) == {"PermissionRequest", "PostToolUse", "UserPromptSubmit"}
    commands = [entries[0]["hooks"][0]["command"] for entries in [*secrets_hooks.values(), *retro_hooks.values()]]
    assert all("${PLUGIN_ROOT}" in command for command in commands)
    assert all("allow" not in command.lower() for command in commands)


def test_secret_output_is_replaced_without_leaking_and_hook_fails_open() -> None:
    script = SECRETS / "scripts/hook-mask-output.py"
    secret = "sk-super-secret-value-123456789"
    blocked = invoke(script, json.dumps({"tool_response": {"token": secret}}))
    assert blocked.returncode == 0
    assert secret not in blocked.stdout
    assert json.loads(blocked.stdout)["decision"] == "block"
    assert json.loads(invoke(script, '{broken').stdout) == {}
    assert json.loads(invoke(script, json.dumps({"tool_response": "ordinary output"})).stdout) == {}


def test_friction_capture_is_minimized_opt_in_and_fail_open(tmp_path: Path) -> None:
    script = RETRO / "scripts/friction-hook.py"
    queue = tmp_path / "friction.jsonl"
    secret = "ghp_abcdefghijklmnopqrstuvwxyz123456"
    payload = json.dumps({"tool_name": "shell", "tool_response": f"token={secret}"})

    assert invoke(script, payload, "--event", "PostToolUse").returncode == 0
    assert not queue.exists()

    env = dict(os.environ, CXPP_FRICTION_QUEUE=str(queue))
    captured = invoke(script, payload, "--event", "PostToolUse", env=env)
    assert captured.returncode == 0 and json.loads(captured.stdout) == {}
    contents = queue.read_text(encoding="utf-8")
    assert secret not in contents
    record = json.loads(contents)
    assert set(record) == {"created_at", "event_type", "fingerprint", "harness", "severity", "source", "summary"}
    assert record["event_type"] == "secret_mask_hit"
    assert queue.stat().st_mode & 0o777 == 0o600
    assert invoke(script, "bad", "--event", "UserPromptSubmit", env=env).returncode == 0


@pytest.mark.parametrize(
    ("direction", "active_version", "candidate_version"),
    (("upgrade", "1.0.0", "2.0.0"), ("rollback", "2.0.0", "1.0.0")),
)
def test_hook_roots_survive_upgrade_and_rollback_with_exact_reviewed_bytes(
    tmp_path: Path,
    direction: str,
    active_version: str,
    candidate_version: str,
) -> None:
    home = tmp_path / "home"
    cache = home / "plugins/cache/codex-power-pack"
    candidates = tmp_path / "candidates"
    active_roots = {
        family: install_plugin_fixture(cache, family, active_version, f"active-{direction}")
        for family in ("secrets", "self-improvement")
    }
    candidate_roots = {
        family: install_plugin_fixture(candidates, family, candidate_version, f"candidate-{direction}")
        for family in ("secrets", "self-improvement")
    }
    reviewed_payloads = {family: plugin_payload(root) for family, root in active_roots.items()}
    reviewed_commands = {family: hook_commands(root) for family, root in active_roots.items()}

    preflight = subprocess.run(
        [
            sys.executable,
            str(TRANSITION),
            "preflight",
            "--codex-home",
            str(home),
            "--family",
            "secrets",
            "--family",
            "self-improvement",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert preflight.returncode == 0
    assert "reviewed roots to retain: 2" in preflight.stdout

    result = run_transition(
        home,
        fake_codex(tmp_path),
        candidates,
        "secrets",
        "self-improvement",
    )
    assert result.returncode == 0, result.stderr
    assert "retained 2 reviewed hook root(s)" in result.stdout

    for family, root in active_roots.items():
        assert root.is_dir() and not root.is_symlink()
        assert plugin_payload(root) == reviewed_payloads[family]
        assert candidate_roots[family].name != root.name
        installed_candidate = cache / family / candidate_version
        assert installed_candidate.is_dir() and not installed_candidate.is_symlink()
        assert plugin_payload(installed_candidate) != reviewed_payloads[family]

    retro_events = json.loads((active_roots["self-improvement"] / "hooks/hooks.json").read_text())["hooks"]
    assert set(retro_events) == {"PermissionRequest", "PostToolUse", "UserPromptSubmit"}
    for family, commands in reviewed_commands.items():
        results = [invoke_hook_command(command, active_roots[family]) for command in commands]
        assert all(result.returncode == 0 for result in results)


def test_failed_reinstall_restores_old_hook_before_returning(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cache = home / "plugins/cache/codex-power-pack"
    candidates = tmp_path / "candidates"
    active = install_plugin_fixture(cache, "secrets", "1.0.0", "reviewed")
    install_plugin_fixture(candidates, "secrets", "2.0.0", "candidate")
    reviewed = plugin_payload(active)
    command = hook_commands(active)[0]

    result = run_transition(
        home,
        fake_codex(tmp_path),
        candidates,
        "secrets",
        fail_family="secrets",
    )
    assert result.returncode == 9
    assert "retained hook roots were restored" in result.stderr
    assert plugin_payload(active) == reviewed
    assert invoke_hook_command(command, active).returncode == 0
    assert not (home / "plugins/.cxpp-hook-retention/codex-power-pack/secrets/1.0.0").exists()


def test_external_recovery_recreates_an_evicted_reviewed_root(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cache = home / "plugins/cache/codex-power-pack"
    active = install_plugin_fixture(cache, "secrets", "1.0.0", "reviewed")
    reviewed = plugin_payload(active)
    command = hook_commands(active)[0]
    retained = home / "plugins/.cxpp-hook-retention/codex-power-pack/secrets/1.0.0"
    shutil.copytree(active, retained)
    shutil.rmtree(active)

    result = subprocess.run(
        [
            sys.executable,
            str(TRANSITION),
            "recover",
            "--codex-home",
            str(home),
            "--approve",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert plugin_payload(active) == reviewed
    assert invoke_hook_command(command, active).returncode == 0
    assert not retained.exists()


def test_missing_hook_scripts_preserve_each_plugins_failure_policy(tmp_path: Path) -> None:
    retro = tmp_path / "self-improvement"
    secrets = tmp_path / "secrets"
    shutil.copytree(RETRO, retro)
    shutil.copytree(SECRETS, secrets)
    (retro / "scripts/friction-hook.py").unlink()
    (secrets / "scripts/hook-mask-output.py").unlink()

    retro_results = [invoke_hook_command(command, retro) for command in hook_commands(retro)]
    assert len(retro_results) == 3
    assert all(result.returncode == 0 for result in retro_results)

    blocked = invoke_hook_command(hook_commands(secrets)[0], secrets)
    assert blocked.returncode != 0
    assert "Secrets plugin" in blocked.stderr
    assert "Restart Codex" in blocked.stderr


def test_status_documents_changed_untrusted_disabled_and_removal_states() -> None:
    status = (ROOT / ".codex/skills/cxpp-status/SKILL.md").read_text(encoding="utf-8")
    init = (ROOT / ".codex/skills/cxpp-init/SKILL.md").read_text(encoding="utf-8")
    update = (ROOT / ".codex/skills/cxpp-update/SKILL.md").read_text(encoding="utf-8")
    for word in ("changed", "untrusted", "disabled", "exact-hash", "/hooks"):
        assert word in status
    assert "preview-remove" in init and "HELPER remove" in init and "--approve" in init
    assert "preview-remove" in update and "HELPER remove" in update and "--approve" in update
    assert "does not authorize" in init and "does not authorize" in update
    assert "preflight" in update
    assert "byte-identical" in update
    assert "exact-hash review" in update
    assert "recover --marketplace codex-power-pack --approve" in update


def test_hooks_never_grant_permissions_or_invoke_shipping_actions() -> None:
    secrets_script = (SECRETS / "scripts/hook-mask-output.py").read_text(encoding="utf-8").lower()
    retro_script = (RETRO / "scripts/friction-hook.py").read_text(encoding="utf-8").lower()
    assert '"decision": "block"' in secrets_script
    for forbidden in ("permissiondecision", '"allow"', "git push", "deploy", "publish"):
        assert forbidden not in secrets_script
        assert forbidden not in retro_script


def test_plugin_uninstall_removes_its_entire_hook_surface(tmp_path: Path) -> None:
    for plugin in (SECRETS, RETRO):
        installed = tmp_path / plugin.name
        shutil.copytree(plugin, installed)
        assert (installed / "hooks/hooks.json").is_file()
        shutil.rmtree(installed)
        assert not installed.exists()
    assert not list(tmp_path.rglob("hooks.json"))
