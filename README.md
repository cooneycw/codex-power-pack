# Codex Power Pack

Codex Power Pack is a Codex-oriented port of `cooneycw/claude-power-pack`.
It preserves the reusable MCP servers, CI/CD helpers, security tooling, secrets
management, templates, and tests, while switching the agent-facing surface from
Claude conventions to Codex conventions.

## What Is Included

- `.codex/prompts/` - Codex prompt files ported from the original slash-command set
- `.codex/cicd.yml` and `.codex/cicd_tasks.yml` - Codex-local CI/CD manifests
- `AGENTS.md` - the canonical repo instructions for Codex
- `mcp-second-opinion/` - external LLM code review server
- `mcp-playwright-persistent/` - persistent browser automation server
- `mcp-nano-banana/` - diagram and PowerPoint generation server
- `mcp-woodpecker-ci/` - Woodpecker CI monitoring and control server
- `lib/creds/`, `lib/security/`, `lib/cicd/`, `lib/spec_bridge/` - reusable Python libraries
- `templates/`, `scripts/`, `docs/skills/`, `tests/` - supporting workflow assets

## Quick Start

```bash
git clone https://github.com/cooneycw/codex-power-pack.git
cd codex-power-pack
uv sync --extra dev
make verify
make docker-up PROFILE=core
```

The default Docker profile starts:

- `mcp-second-opinion` on `127.0.0.1:8080`
- `mcp-nano-banana` on `127.0.0.1:8084`

Add the browser profile for Playwright:

```bash
make docker-up PROFILE="core browser"
```

## Codex Adaptation

The port makes these opinionated changes:

- Codex instructions live in `AGENTS.md`
- Codex prompt files live in `.codex/prompts/`
- runtime config now targets `.codex/` paths
- secrets storage uses `~/.config/codex-power-pack/`
- package and repo naming use `codex-power-pack`

Some imported materials still mention Claude-specific workflows or command names.
Those are source-derived reference artifacts and can be cleaned up incrementally
without affecting the core libraries or tests.

## Verification

```bash
make lint
make test
make typecheck
make verify
```

## Status

This repo is a first-pass Codex replication, not a full semantic rewrite of
every historical document. The core code paths, manifests, prompts, and top-level
instructions are adapted for Codex use; legacy docs remain as reference material
where they do not control runtime behavior.
