# Codex Power Pack

## Core Directives

- Never print secrets, tokens, passwords, connection strings, or raw `.env` contents.
- Use `make` targets as the canonical interface for lint, test, verify, deploy, and Docker operations.
- Prefer `.codex/` assets over legacy `.claude/` assets.
- Read topic-specific docs from `docs/skills/` only when they are relevant.
- After code changes, run `make verify` unless the environment blocks it.

## Project Map

- `AGENTS.md` - canonical Codex instructions
- `.codex/prompts/` - Codex prompt entrypoints ported from the source repo
- `.codex/cicd.yml` - CI/CD config
- `.codex/cicd_tasks.yml` - deterministic CI/CD task manifest
- `mcp-second-opinion/` - external review server
- `mcp-playwright-persistent/` - browser automation server
- `mcp-nano-banana/` - diagram and PowerPoint server
- `mcp-woodpecker-ci/` - Woodpecker CI server
- `lib/` - reusable Python libraries for creds, security, CI/CD, and spec sync
- `templates/` - starter Makefiles and workflow templates
- `scripts/` - shell helpers
- `docs/skills/` - focused reference docs

## Conventions

- Python 3.11+
- `uv` for dependency management
- `make lint`, `make test`, `make typecheck`, `make verify` for quality gates
- Docker entrypoints go through `make docker-*`
- prefer `rg` for repo search

## Notes

- `CLAUDE.md` is retained only as a migrated source artifact.
- If both `.codex/` and `.claude/` variants exist, treat `.codex/` as authoritative.
