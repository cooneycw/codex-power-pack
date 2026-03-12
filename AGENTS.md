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

- CI/CD slash trigger parity is mapped in `docs/skills/cicd-command-skill-map.md`.
- Flow slash trigger parity is mapped in `docs/skills/flow-command-skill-map.md`.
- GitHub slash trigger parity is mapped in `docs/skills/github-command-skill-map.md`.
- Project slash trigger parity is mapped in `docs/skills/project-command-skill-map.md`.
- AGENTS.md governance trigger parity is mapped in `docs/skills/agents-md-command-skill-map.md`.
