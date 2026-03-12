# Codex Power Pack

Codex Power Pack is a Codex-first automation toolkit.
It preserves the reusable MCP servers, CI/CD helpers, security tooling, secrets
management, templates, and tests for Codex-centric workflows.

## What Is Included

- `.codex/prompts/` - Codex prompt files ported from the original slash-command set
- `.codex/skills/` - Codex skill packages that back slash-style trigger workflows
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

## Codex Architecture

- Codex instructions live in `AGENTS.md`
- Prompt entrypoints live in `.codex/prompts/`
- Skill packages live in `.codex/skills/`
- Runtime config targets `.codex/` paths
- Secrets storage uses `~/.config/codex-power-pack/`

## CI/CD Trigger Parity

The `/cicd:*` namespace is available through:

- `.codex/prompts/cicd/*.md` - slash-compatible entrypoints
- `.codex/skills/cicd-*/` - backing Codex skill packages
- `docs/skills/cicd-command-skill-map.md` - trigger-to-skill inventory

## Flow Trigger Parity

The `/flow:*` namespace is available through:

- `.claude/commands/flow/*.md` - source command inventory
- `.codex/prompts/flow/*.md` - slash-compatible entrypoints
- `.codex/skills/flow-*/` - backing Codex skill packages
- `docs/skills/flow-command-skill-map.md` - trigger-to-skill inventory

## AGENTS.md Trigger Parity

The `/agents-md:*` namespace is available through:

- `.codex/prompts/agents-md/*.md` - slash-compatible entrypoints
- `.codex/skills/agents-md-*/` - backing Codex skill packages
- `docs/skills/agents-md-command-skill-map.md` - trigger-to-skill inventory

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
