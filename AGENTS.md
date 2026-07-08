# Codex Power Pack

## Core Directives

- Never print secrets, tokens, passwords, connection strings, or raw `.env` contents.
- Use `make` targets as the canonical interface for lint, test, verify, and audit operations.
- Use `.codex/` assets as the canonical workflow surface.
- Read topic-specific docs from `docs/skills/` only when they are relevant.
- After code changes, run `make verify` unless the environment blocks it.

## Project Map

- `AGENTS.md` - canonical Codex instructions
- `.codex/skills/` - Codex skill packages, generated from claude-power-pack and pinned by commit SHA (pull model, codex-power-pack#75). Do not hand-edit - the drift gate `make codex-skills-check` enforces it. See `.codex/skills/README.md`.
- `.codex/cicd.yml` - CI/CD config
- `.codex/cicd_tasks.yml` - deterministic CI/CD task manifest
- `lib/` - reusable Python libraries for creds, security, and CI/CD
- `vendor/claude-power-pack/` - pin (`PIN`) + drift manifest (`codex-skills.sha256`) for the generated `.codex/skills/` copy
- `templates/` - starter Makefiles and workflow templates
- `templates/config.toml.example` - Codex MCP pointers for host-managed services
- `docs/HOST_MANAGED.md` - host-owned MCP service inventory and health checks
- `scripts/` - shell + Python helpers, incl. `codex_skills_sync.py` (pulls + drift-gates `.codex/skills/`)
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

- The shared command families live as generated Codex skills under `.codex/skills/<family>-<command>/`,
  pulled from claude-power-pack's `.claude/commands/` single source (codex-power-pack#75).
  The skill dir name is the trigger: `/flow:auto` -> `.codex/skills/flow-auto/`.
- Reconcile by editing the upstream source, never the generated copy: edit
  `.claude/commands/<family>/` in claude-power-pack, regenerate there (`make codex-skills`),
  then re-pull here (`make codex-skills-refresh`). The drift gate `make codex-skills-check`
  fails CI on any hand-edit.
- `claude-md` is not carried here (Out-of-Scope; the Codex-native `agents-md` family covers
  the AGENTS.md world, epic #64/#66). The former `.codex/prompts/` and per-family
  `docs/skills/*-command-skill-map.md` surfaces were retired with the hand-port fork.
