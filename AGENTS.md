# Codex Power Pack

## Core Directives

- Never print secrets, tokens, passwords, connection strings, or raw `.env` contents.
- Use `make` targets as the canonical interface for lint, test, verify, and audit operations.
- Use `.codex/` assets as the canonical workflow surface.
- Read topic-specific docs from `docs/skills/` only when they are relevant.
- After code changes, run `make verify` unless the environment blocks it.

## Project Map

- `AGENTS.md` - canonical Codex instructions
- `.codex/prompts/` - Codex prompt entrypoints ported from the source repo
- `.codex/skills/` - Codex skill packages backing slash-style command workflows
- `.codex/cicd.yml` - CI/CD config
- `.codex/cicd_tasks.yml` - deterministic CI/CD task manifest
- `lib/` - reusable Python libraries for creds, security, and CI/CD
- `templates/` - starter Makefiles and workflow templates
- `templates/config.toml.example` - Codex MCP pointers for host-managed services
- `docs/HOST_MANAGED.md` - host-owned MCP service inventory and health checks
- `scripts/` - shell helpers
- `docs/skills/` - focused reference docs
- `docs/security/` - security threat models and guard designs

## Runtime Boundary

Codex Power Pack no longer owns MCP server code, Docker Compose runtime, or
deployment entrypoints. Use external MCP servers and native Codex plugins for
tool integrations, with client-side pointers documented in `docs/HOST_MANAGED.md`.

## Conventions

- Python 3.11+
- `uv` for dependency management
- `make lint`, `make test`, `make typecheck`, `make verify` for quality gates
- Native Codex plugins are the supported distribution path; use the thin
  `cxpp:init` fallback for checkout-based project bootstrapping.
- prefer `rg` for repo search

## Notes

- CI/CD slash trigger parity is mapped in `docs/skills/cicd-command-skill-map.md`.
- Flow slash trigger parity is mapped in `docs/skills/flow-command-skill-map.md`.
- GitHub slash trigger parity is mapped in `docs/skills/github-command-skill-map.md`.
- Documentation slash trigger parity is mapped in `docs/skills/documentation-command-skill-map.md`.
- Second-opinion slash trigger parity is mapped in `docs/skills/second-opinion-command-skill-map.md`.
- QA slash trigger parity is mapped in `docs/skills/qa-command-skill-map.md`.
- Project slash trigger parity is mapped in `docs/skills/project-command-skill-map.md`.
- Spec slash trigger parity is mapped in `docs/skills/spec-command-skill-map.md`.
- AGENTS.md governance trigger parity is mapped in `docs/skills/agents-md-command-skill-map.md`.
