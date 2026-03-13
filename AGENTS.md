# Codex Power Pack

## Core Directives

- Never print secrets, tokens, passwords, connection strings, or raw `.env` contents.
- Use `make` targets as the canonical interface for lint, test, verify, deploy, and Docker operations.
- Use `.codex/` assets as the canonical workflow surface.
- Read topic-specific docs from `docs/skills/` only when they are relevant.
- After code changes, run `make verify` unless the environment blocks it.

## Project Map

- `AGENTS.md` - canonical Codex instructions
- `.codex/prompts/` - Codex prompt entrypoints ported from the source repo
- `.codex/skills/` - Codex skill packages backing slash-style command workflows
- `.codex/cicd.yml` - CI/CD config
- `.codex/cicd_tasks.yml` - deterministic CI/CD task manifest
- `codex-second-opinion/` - external review server
- `codex-playwright/` - browser automation server
- `codex-nano-banana/` - diagram and PowerPoint server
- `codex-woodpecker/` - Woodpecker CI server
- `lib/` - reusable Python libraries for creds, security, CI/CD, and spec sync
- `templates/` - starter Makefiles and workflow templates
- `scripts/` - shell helpers
- `docs/skills/` - focused reference docs

## MCP Server Ports

All MCP servers bind to the `9100-9199` range to avoid conflicts with application ports (8000-8100).

| Service | Port | Profile |
|---------|------|---------|
| `codex-second-opinion` | 9100 | core |
| `codex-playwright` | 9101 | browser |
| `codex-nano-banana` | 9102 | core |
| `codex-woodpecker` | 9103 | cicd |

Defaults are set in each service's `src/config.py` and can be overridden via `MCP_SERVER_PORT` env var.

## Conventions

- Python 3.11+
- `uv` for dependency management
- `make lint`, `make test`, `make typecheck`, `make verify` for quality gates
- Docker entrypoints go through `make docker-*`
- prefer `rg` for repo search

## Notes

- CI/CD slash trigger parity is mapped in `docs/skills/cicd-command-skill-map.md`.
- Flow slash trigger parity is mapped in `docs/skills/flow-command-skill-map.md`.
- GitHub slash trigger parity is mapped in `docs/skills/github-command-skill-map.md`.
- Second-opinion slash trigger parity is mapped in `docs/skills/second-opinion-command-skill-map.md`.
- QA slash trigger parity is mapped in `docs/skills/qa-command-skill-map.md`.
- Project slash trigger parity is mapped in `docs/skills/project-command-skill-map.md`.
- Spec slash trigger parity is mapped in `docs/skills/spec-command-skill-map.md`.
- AGENTS.md governance trigger parity is mapped in `docs/skills/agents-md-command-skill-map.md`.
