"""Regression checks for the post-demolition Woodpecker pipeline."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gitleaks_is_the_first_blocking_ci_step() -> None:
    """Issue #97: scan credentials before dependency installation or validation."""
    pipeline = yaml.safe_load((REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))

    steps = pipeline["steps"]
    assert next(iter(steps)) == "secret-scan"
    assert steps["secret-scan"]["image"] == "zricethezav/gitleaks:v8.18.4"
    assert steps["secret-scan"]["commands"] == [
        "gitleaks detect --source . --config .gitleaks.toml --verbose"
    ]


def test_pipeline_contains_no_deleted_runtime_image_gates() -> None:
    """The repository no longer owns runtime images after demolition."""
    text = (REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8")

    assert "image-security" not in text
    assert "runtime-smoke" not in text
