"""Tests for lib/cicd/pipeline.py - Woodpecker CI pipeline generation."""

from __future__ import annotations

from pathlib import Path

from lib.cicd.config import CICDConfig
from lib.cicd.models import Framework, FrameworkInfo, PackageManager
from lib.cicd.pipeline import (
    generate_pipeline,
    generate_woodpecker,
)


def _make_info(
    framework: Framework = Framework.PYTHON,
    package_manager: PackageManager = PackageManager.UV,
) -> FrameworkInfo:
    """Helper to build a FrameworkInfo for tests."""
    return FrameworkInfo(
        framework=framework,
        package_manager=package_manager,
        detected_files=[],
        recommended_targets=["lint", "test"],
        runner_commands={},
        secondary_frameworks=[],
    )


def _make_config(**overrides: object) -> CICDConfig:
    """Build a CICDConfig with optional pipeline overrides."""
    config = CICDConfig()
    for key, value in overrides.items():
        if key == "aws_secrets" and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                setattr(config.pipeline.aws_secrets, nested_key, nested_value)
            continue
        setattr(config.pipeline, key, value)
    return config


# ---------------------------------------------------------------------------
# generate_pipeline - orchestrator
# ---------------------------------------------------------------------------


class TestGeneratePipeline:
    """Tests for the top-level generate_pipeline() orchestrator."""

    def test_default_provider_is_woodpecker(self) -> None:
        info = _make_info()
        config = _make_config()
        files = generate_pipeline(info, config)
        assert ".woodpecker.yml" in files

    def test_woodpecker_provider(self) -> None:
        info = _make_info()
        config = _make_config(provider="woodpecker")
        files = generate_pipeline(info, config)
        assert ".woodpecker.yml" in files

    def test_write_to_disk(self, tmp_path: Path) -> None:
        info = _make_info()
        config = _make_config(provider="woodpecker")
        files = generate_pipeline(info, config, output_dir=str(tmp_path))
        assert (tmp_path / ".woodpecker.yml").exists()
        content = (tmp_path / ".woodpecker.yml").read_text()
        assert "steps:" in content
        assert ".woodpecker.yml" in files


# ---------------------------------------------------------------------------
# generate_woodpecker - various frameworks
# ---------------------------------------------------------------------------


class TestWoodpecker:
    """Test Woodpecker CI pipeline generation."""

    def test_python_woodpecker(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: python:3.12" in output
        assert "pip install uv" in output
        assert "uv sync" in output
        assert "make lint" in output

    def test_node_woodpecker(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.NPM)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: node:22" in output
        assert "npm ci" in output
        assert "make lint" in output

    def test_go_woodpecker(self) -> None:
        info = _make_info(Framework.GO, PackageManager.GO)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: golang:1.23" in output
        assert "go mod download" in output

    def test_rust_woodpecker(self) -> None:
        info = _make_info(Framework.RUST, PackageManager.CARGO)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: rust:1.82" in output

    def test_powershell_woodpecker(self) -> None:
        info = _make_info(Framework.POWERSHELL, PackageManager.PSRESOURCEGET)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "mcr.microsoft.com/powershell" in output
        assert "Pester" in output
        assert "PSScriptAnalyzer" in output
        assert "make lint" in output

    def test_woodpecker_deploy_requires_aws_secrets_manager(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(
            branches={"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]},
            aws_secrets={"project_id": "codex-power-pack", "region": "ca-central-1"},
            secrets_needed=["DEPLOY_KEY"],
        )
        output = generate_woodpecker(info, config)
        assert "aws-secretsmanager-preflight" in output
        assert "- name: deploy" in output
        assert 'CPP_SECRETS_PROVIDER: "aws-secrets-manager"' in output
        assert 'CPP_AWS_SECRET_ID: "codex-power-pack/codex-power-pack"' in output
        assert 'AWS_REGION: "ca-central-1"' in output
        assert 'CPP_AWS_REQUIRED_KEYS: "DEPLOY_KEY"' in output
        assert "event: push" in output
        assert "aws secretsmanager describe-secret" in output
        assert "Expected AWS keys" in output
        assert "    secrets:" not in output

    def test_woodpecker_branch_filtering(self) -> None:
        info = _make_info()
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "branch: [main]" in output
        assert "event: [push, pull_request]" in output

    def test_woodpecker_default_deploy_secret_ref_uses_placeholder(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(branches={"main": ["deploy"], "pr": []})
        output = generate_woodpecker(info, config)
        assert 'CPP_AWS_SECRET_ID: "codex-power-pack/${CI_REPO_NAME:-change-me}"' in output

    def test_woodpecker_uses_makefile_targets(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(branches={"pr": ["lint", "test", "typecheck"]})
        output = generate_woodpecker(info, config)
        assert "make lint" in output
        assert "make test" in output
        assert "make typecheck" in output


# ---------------------------------------------------------------------------
# Template validation - static workflow templates
# ---------------------------------------------------------------------------


class TestWorkflowTemplates:
    """Validate static Woodpecker workflow templates in templates/workflows/."""

    TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "workflows"

    def test_woodpecker_templates_exist(self) -> None:
        expected = [
            "woodpecker-python.yml",
            "woodpecker-node.yml",
            "woodpecker-go.yml",
            "woodpecker-rust.yml",
            "woodpecker-powershell.yml",
        ]
        for name in expected:
            path = self.TEMPLATE_DIR / name
            assert path.exists(), f"Missing template: {name}"

    def test_templates_are_valid_yaml(self) -> None:
        import yaml

        for yml_file in sorted(self.TEMPLATE_DIR.glob("*.yml")):
            content = yml_file.read_text()
            parsed = yaml.safe_load(content)
            assert parsed is not None, f"{yml_file.name} parsed as None"
            assert isinstance(parsed, dict), f"{yml_file.name} is not a mapping"

    def test_woodpecker_templates_have_steps(self) -> None:
        import yaml

        for name in [
            "woodpecker-python.yml",
            "woodpecker-node.yml",
            "woodpecker-go.yml",
            "woodpecker-rust.yml",
            "woodpecker-powershell.yml",
        ]:
            path = self.TEMPLATE_DIR / name
            parsed = yaml.safe_load(path.read_text())
            assert "steps" in parsed, f"{name} missing 'steps'"

    def test_woodpecker_templates_use_makefile_targets(self) -> None:
        for name in [
            "woodpecker-python.yml",
            "woodpecker-node.yml",
            "woodpecker-go.yml",
            "woodpecker-rust.yml",
            "woodpecker-powershell.yml",
        ]:
            content = (self.TEMPLATE_DIR / name).read_text()
            assert "make lint" in content, f"{name} missing 'make lint'"
            assert "make test" in content, f"{name} missing 'make test'"

    def test_no_github_actions_templates_remain(self) -> None:
        """Ensure no GitHub Actions templates exist."""
        for yml_file in self.TEMPLATE_DIR.glob("*.yml"):
            content = yml_file.read_text()
            assert "actions/checkout" not in content, (
                f"{yml_file.name} contains GitHub Actions references"
            )
