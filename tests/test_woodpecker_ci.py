"""Regression checks for the post-demolition Woodpecker pipeline."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_EVENTS = {"push", "pull_request"}


def _pipeline() -> dict:
    return yaml.safe_load((REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))


def _events(step: dict) -> set[str]:
    events: set[str] = set()
    for condition in step.get("when", []):
        value = condition.get("event", [])
        events.update(value if isinstance(value, list) else [value])
    return events


def test_gitleaks_is_the_first_blocking_ci_step() -> None:
    """Issue #97: scan credentials before dependency installation or validation."""
    pipeline = _pipeline()

    steps = pipeline["steps"]
    assert next(iter(steps)) == "secret-scan"
    assert steps["secret-scan"]["image"] == "zricethezav/gitleaks:v8.18.4"
    assert steps["secret-scan"]["commands"] == [
        "gitleaks detect --source . --config .gitleaks.toml --verbose"
    ]
    assert _events(steps["secret-scan"]) == REQUIRED_EVENTS


def test_required_ci_uses_complete_local_contract_and_exact_pin() -> None:
    steps = _pipeline()["steps"]

    assert _events(steps["validate"]) == REQUIRED_EVENTS
    assert steps["validate"]["commands"][-1] == "make verify"
    assert "git make" in "\n".join(steps["validate"]["commands"])

    pin_step = steps["codex-skills-pin-integrity"]
    assert _events(pin_step) == REQUIRED_EVENTS
    commands = "\n".join(pin_step["commands"])
    assert "--pin-ref" in commands
    assert commands.index("--pin-ref") < commands.index("git clone")
    assert "https://github.com/cooneycw/claude-power-pack.git" in commands
    assert "checkout --detach" in commands
    assert "make codex-skills-pin-check CPP_ROOT=/tmp/claude-power-pack-pinned" in commands
    assert "git make" in commands


def test_dependency_audit_is_required_and_precedes_advisory_currency() -> None:
    steps = _pipeline()["steps"]
    names = list(steps)

    assert _events(steps["dependency-audit"]) == REQUIRED_EVENTS
    assert steps["dependency-audit"]["commands"][-1] == "make dep-audit"
    tools = "\n".join(steps["dependency-audit"]["commands"])
    assert "make" in tools
    assert "uv pip-audit bandit" in tools
    assert names.index("dependency-audit") < names.index("codex-skills-currency")


def test_latest_upstream_currency_is_manual_or_cron_only() -> None:
    step = _pipeline()["steps"]["codex-skills-currency"]
    commands = "\n".join(step["commands"])

    assert _events(step) == {"manual", "cron"}
    assert "--depth=1 https://github.com/cooneycw/claude-power-pack.git" in commands
    assert "make codex-skills-currency-check" in commands


def test_single_workflow_preserves_aggregate_pr_and_push_context_shape() -> None:
    pipeline = _pipeline()
    workflow_events = set(pipeline["when"][0]["event"])

    assert workflow_events == {"push", "pull_request", "manual", "cron"}
    assert not (REPO_ROOT / ".woodpecker").exists()


def test_make_verify_dependency_bearing_scripts_use_the_uv_environment() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    for command in (
        "uv run --extra dev python scripts/skill_contract_baseline.py --check",
        "uv run --extra dev python scripts/skill_contract_lint.py --check",
        "uv run --extra dev python scripts/project_next_sync.py --check",
    ):
        assert command in makefile


def test_pipeline_contains_no_deleted_runtime_image_gates() -> None:
    """The repository no longer owns runtime images after demolition."""
    text = (REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8")

    assert "image-security" not in text
    assert "runtime-smoke" not in text
