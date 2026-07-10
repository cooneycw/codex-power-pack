"""Codex-native deterministic security skill contracts (#89)."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / ".codex" / "skills"


def test_seeded_finding_is_reported_without_revealing_the_value(tmp_path: Path) -> None:
    secret = "fixture" + "-password" + "-value"
    (tmp_path / "settings.py").write_text(f'password = "{secret}"\n', encoding="utf-8")

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
