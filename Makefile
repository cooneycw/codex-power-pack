.PHONY: test lint format typecheck verify build update_docs clean help secret-scan dep-audit \
	codex-skills codex-skills-check codex-skills-refresh harness-lint

# claude-power-pack checkout the generated Codex skills are pulled from (codex-power-pack#75).
CPP_ROOT ?= ../claude-power-pack
CPP_REF ?=

## Quality gates (used by /flow:finish)

lint:
	uv run --extra dev ruff check .

format:
	uv run --extra dev ruff format .

test:
	uv run --extra dev pytest

typecheck:
	uv run --extra dev mypy .

harness-lint:
	@python3 scripts/harness_lint.py --check

build:
	uv build

## Codex skills sync (generated from claude-power-pack, pull model - codex-power-pack#75)

# Drift gate: fail if .codex/skills/ diverges from the pinned CPP-generated copy.
# Git-free and dependency-free, so it runs unchanged in the CI validate container.
codex-skills-check:
	@python3 scripts/codex_skills_sync.py --check

# Re-snapshot the drift manifest from the current .codex/skills/ tree.
codex-skills:
	@python3 scripts/codex_skills_sync.py --write

# Maintainer: re-pull the generated skills from a claude-power-pack checkout.
# Usage: make codex-skills-refresh CPP_ROOT=../claude-power-pack CPP_REF=<sha>
codex-skills-refresh:
	@python3 scripts/codex_skills_sync.py --refresh --cpp-root "$(CPP_ROOT)" --ref "$(CPP_REF)"

## Verification gate (runs all quality checks)

verify: lint test typecheck codex-skills-check harness-lint

## Documentation (used by /flow:auto and /flow:finish)

update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review AGENTS.md and README.md for accuracy"

## Security scanning

secret-scan:
	gitleaks detect --source . --config .gitleaks.toml --verbose

dep-audit:
	uv export --format requirements-txt --no-hashes > /tmp/requirements.txt
	pip-audit -r /tmp/requirements.txt
	bandit -r lib scripts -ll --quiet --skip B104,B108,B310,B602

## Utilities

clean:
	rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache dist build *.egg-info

## Help

help:
	@echo "Quality gates:"
	@echo "  make lint        - Run ruff linter"
	@echo "  make format      - Run ruff formatter"
	@echo "  make test        - Run pytest"
	@echo "  make typecheck   - Run mypy"
	@echo "  make harness-lint - Check skills for unadapted Claude-only constructs"
	@echo "  make build       - Build distribution packages"
	@echo "  make verify      - Run all quality checks"
	@echo ""
	@echo "Codex skills (generated from claude-power-pack):"
	@echo "  make codex-skills-check   - Drift gate for .codex/skills/"
	@echo "  make codex-skills         - Re-snapshot the drift manifest"
	@echo "  make codex-skills-refresh - Re-pull skills from a CPP checkout (CPP_ROOT=, CPP_REF=)"
	@echo ""
	@echo "  make clean       - Remove build artifacts"
