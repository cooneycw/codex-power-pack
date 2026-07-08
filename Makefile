.PHONY: test lint format typecheck verify build update_docs clean help secret-scan dep-audit

## Quality gates (used by /flow:finish)

lint:
	uv run --extra dev ruff check .

format:
	uv run --extra dev ruff format .

test:
	uv run --extra dev pytest

typecheck:
	uv run --extra dev mypy .

build:
	uv build

## Verification gate (runs all quality checks)

verify: lint test typecheck

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
	@echo "  make build       - Build distribution packages"
	@echo "  make verify      - Run all quality checks"
	@echo ""
	@echo "  make clean       - Remove build artifacts"
