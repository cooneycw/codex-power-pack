"""Codex-native deterministic security skill contracts (#89)."""

import subprocess
import sys
from pathlib import Path

from lib.security.modules import secrets

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".codex" / "skills"


def test_repository_native_baseline_has_only_exact_reviewed_fixtures() -> None:
    result = secrets.scan(str(REPO_ROOT))
    assert not result.findings, [(f.id, f.location) for f in result.findings]
    assert "14 reviewed fixture match(es) excepted" in result.passed[0]


def test_finish_gate_accepts_fixture_but_blocks_same_file_neighbour(tmp_path: Path) -> None:
    import shutil

    cases = REPO_ROOT / "controls/native-secret-fixture-scope/cases"
    for case, expected in (("known-fixture", 0), ("extra-secret", 1)):
        target = tmp_path / case
        shutil.copytree(cases / case, target)
        result = subprocess.run(
            [sys.executable, "-m", "lib.security", "gate", "flow_finish", "--path", str(target)],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=30,
        )
        assert result.returncode == expected, result.stdout + result.stderr
        assert "1 reviewed fixture match(es) excepted" in result.stdout
        if expected:
            assert "BLOCKED" in result.stdout


def test_finish_gate_blocks_malformed_policy_without_other_findings(tmp_path: Path) -> None:
    config = tmp_path / ".codex"
    config.mkdir()
    (config / "security-fixtures.toml").write_text("version = false\nfixtures = []\n")
    result = subprocess.run(
        [sys.executable, "-m", "lib.security", "gate", "flow_finish", "--path", str(tmp_path)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == 1
    assert "fixture policy is invalid" in result.stdout


def test_legacy_suppression_cannot_remove_invalid_policy_blocker(tmp_path: Path) -> None:
    config = tmp_path / ".codex"
    config.mkdir()
    (config / "security-fixtures.toml").write_text("version = false\nfixtures = []\n")
    (config / "security.yml").write_text(
        "suppressions:\n  - id: INVALID_FIXTURE_POLICY\n    path: '.*'\n    reason: attempted bypass\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "lib.security", "gate", "flow_finish", "--path", str(tmp_path)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == 1
    assert "BLOCKED" in result.stdout


def test_legacy_ordinary_suppressions_remain_a_separate_verdict_policy(tmp_path: Path) -> None:
    import shutil

    target = tmp_path / "subject"
    shutil.copytree(REPO_ROOT / "controls/native-secret-fixture-scope/cases/extra-secret", target)
    (target / ".codex/security.yml").write_text(
        "suppressions:\n  - id: GITHUB_PAT\n    path: '^settings[.]cfg$'\n    reason: legacy policy test\n"
    )
    native = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/native-secret-scan.py"), "--root", str(target)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    general = subprocess.run(
        [sys.executable, "-m", "lib.security", "gate", "flow_finish", "--path", str(target)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    assert native.returncode == 1
    assert general.returncode == 0  # Existing explicit user policy, not an exact fixture exception.


def test_seeded_finding_is_reported_without_revealing_the_value(tmp_path: Path) -> None:
    secret = "fixture" + "-password" + "-value"
    key_name = "".join(("pass", "word"))
    (tmp_path / "settings.py").write_text(f'{key_name} = "{secret}"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "lib.security", "quick", "--path", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "Hardcoded password" in result.stdout
    assert secret not in result.stdout + result.stderr


def test_security_skill_text_is_codex_native_and_deterministic() -> None:
    text = "\n".join(
        (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        for name in ("security-help", "security-quick", "security-scan", "security-deep")
    )

    assert "python3 -m lib.security" in text
    assert "Codex native code review" in text
    assert "Claude Code" not in text
