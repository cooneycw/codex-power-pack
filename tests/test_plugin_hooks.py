"""Security and lifecycle contracts for reviewed persistent plugin hooks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "plugins/secrets"
RETRO = ROOT / "plugins/self-improvement"


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
    assert "warn before approval" in update
    assert "must be restarted" in update


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
