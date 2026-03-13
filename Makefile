.PHONY: test lint format typecheck verify build update_docs clean help \
       mcp-install-codex mcp-doctor mcp-smoke \
       docker-build docker-check-env docker-up docker-down docker-logs docker-ps deploy

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

## Pre-deploy gate (runs all quality checks)

verify: lint test typecheck

## Documentation (used by /flow:auto and /flow:finish)

update_docs:
	@echo "Run /documentation:c4 to regenerate C4 architecture diagrams"
	@echo "Review AGENTS.md and README.md for accuracy"

## MCP operations

CODEX_CONFIG ?= $(HOME)/.codex/config.toml

mcp-install-codex:
	python3 scripts/mcp_install_codex.py --codex-config "$(CODEX_CONFIG)"

mcp-doctor:
	python3 scripts/mcp_doctor.py --codex-config "$(CODEX_CONFIG)" --profiles "$(PROFILE)"

mcp-smoke:
	python3 scripts/mcp_smoke.py --profiles "$(PROFILE)"

## Docker (MCP server containers)
## Usage: make docker-up PROFILE=core
##        make docker-up PROFILE="core browser"
## Profiles: core (codex-second-opinion + codex-nano-banana), browser, cicd

PROFILE ?= core

docker-build:
	$(foreach p,$(PROFILE),docker compose --profile $(p) build;)

docker-check-env:
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "WARNING: .env file not found in $$(pwd)"; \
		echo "Docker containers will start WITHOUT API keys."; \
		echo "MCP Second Opinion will report 'no_api_keys' status."; \
		echo ""; \
		echo "Create .env with at least one key:"; \
		echo "  echo 'GEMINI_API_KEY=your-key' > .env"; \
		echo ""; \
		echo "Or run /cpp:init to configure interactively."; \
		echo ""; \
	elif ! grep -qE '^(GEMINI|OPENAI|ANTHROPIC)_API_KEY=.+' .env 2>/dev/null; then \
		echo ""; \
		echo "WARNING: .env exists but contains no API keys."; \
		echo "Add at least one: GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"; \
		echo ""; \
	fi

docker-up: docker-check-env
	$(foreach p,$(PROFILE),docker compose --profile $(p) up -d;)

docker-down:
	docker compose --profile core --profile browser --profile cicd down

docker-logs:
	docker compose --profile core --profile browser --profile cicd logs -f

docker-ps:
	docker compose --profile core --profile browser --profile cicd ps

## Deploy (used by Woodpecker CI and /flow:deploy)

deploy: docker-build docker-up mcp-smoke
	@sleep 5
	@$(MAKE) docker-ps

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
	@echo "MCP:"
	@echo "  make mcp-install-codex - Install/update Codex MCP registrations"
	@echo "  make mcp-doctor        - Validate Codex MCP config and endpoint health"
	@echo "  make mcp-smoke         - Run MCP initialize smoke tests for active PROFILE"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   - Start containers (PROFILE=core)"
	@echo "  make docker-down - Stop all containers"
	@echo "  make docker-ps   - Show container status"
	@echo "  make docker-logs - Tail container logs"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy      - Build and start containers"
	@echo "  make clean       - Remove build artifacts"
