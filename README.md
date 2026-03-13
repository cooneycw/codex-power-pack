# Codex Power Pack

Codex Power Pack is a Codex-first automation toolkit.
It preserves the reusable MCP servers, CI/CD helpers, security tooling, secrets
management, templates, and tests for Codex-centric workflows.

## What Is Included

- `.codex/prompts/` - Codex prompt files ported from the original slash-command set
- `.codex/skills/` - Codex skill packages that back slash-style trigger workflows
- `.codex/cicd.yml` and `.codex/cicd_tasks.yml` - Codex-local CI/CD manifests
- `AGENTS.md` - the canonical repo instructions for Codex
- `codex-second-opinion/` - external LLM code review server
- `codex-playwright/` - browser automation server
- `codex-nano-banana/` - diagram and PowerPoint generation server
- `codex-woodpecker/` - Woodpecker CI monitoring and control server
- `lib/creds/`, `lib/security/`, `lib/cicd/`, `lib/spec_bridge/` - reusable Python libraries
- `templates/`, `scripts/`, `docs/skills/`, `tests/` - supporting workflow assets

## Quick Start

```bash
git clone https://github.com/cooneycw/codex-power-pack.git
cd codex-power-pack
uv sync --extra dev
make skills-install-codex
make verify
make docker-up PROFILE=core
make mcp-smoke PROFILE=core
```

Confirm skill registration health:

```bash
make skills-doctor
```

The default Docker profile starts:

- `codex-second-opinion` on `127.0.0.1:9100`
- `codex-nano-banana` on `127.0.0.1:9102`

Add the browser profile for Playwright:

```bash
make docker-up PROFILE="core browser"
```

## Codex MCP Setup

Install deterministic Codex MCP registrations from this repository path:

```bash
make mcp-install-codex
```

Validate local config drift and live endpoint health:

```bash
make mcp-doctor PROFILE="core browser cicd"
```

`mcp-install-codex` automatically replaces legacy Woodpecker entries such as
`voice-bot-acs/codex-power-pack/mcp-woodpecker-ci` with repo-local paths.

Canonical transport matrix:

| Server | Profile | Canonical endpoint | Alternate transport |
|--------|---------|--------------------|---------------------|
| `codex-second-opinion` | `core` | `http://127.0.0.1:9100/sse` | `uv run --directory .../codex-second-opinion python src/server.py --stdio` |
| `codex-playwright` | `browser` | `http://127.0.0.1:9101/sse` | `uv run --directory .../codex-playwright python src/server.py --stdio` |
| `codex-nano-banana` | `core` | `http://127.0.0.1:9102/sse` | `uv run --directory .../codex-nano-banana python src/server.py --stdio` |
| `codex-woodpecker` | `cicd` | `http://127.0.0.1:9103/sse` | `uv run --directory .../codex-woodpecker python src/server.py --stdio` |

The Woodpecker Docker container remains available only as a legacy profile:
`make docker-up PROFILE=legacy-cicd`. Primary usage is stdio transport.

## Codex Architecture

- Codex instructions live in `AGENTS.md`
- Prompt entrypoints live in `.codex/prompts/`
- Skill packages live in `.codex/skills/`
- Runtime config targets `.codex/` paths
- Secrets storage uses `~/.config/codex-power-pack/`

## Workspace-Wide Skill Discovery

Codex command discovery is driven by installed skill packages under
`~/.codex/skills`, not by walking parent `.claude/commands` symlinks.

Use the deterministic installer to register this repository's skills globally:

```bash
make skills-install-codex
make skills-doctor
```

If `skills-doctor` reports drift, replace conflicting registrations:

```bash
make skills-install-codex SKILLS_OVERWRITE=1
```

The `/project:*` namespace in this repository currently includes:
- `/project:help`
- `/project:init`

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

## GitHub Trigger Parity

The `/github:*` namespace is available through:

- `.claude/commands/github/*.md` - source command inventory
- `.codex/prompts/github/*.md` - slash-compatible entrypoints
- `.codex/skills/github-*/` - backing Codex skill packages
- `docs/skills/github-command-skill-map.md` - trigger-to-skill inventory

## Documentation Trigger Parity

The `/documentation:*` namespace is available through:

- `.claude/commands/documentation/*.md` - source command inventory
- `.codex/prompts/documentation/*.md` - slash-compatible entrypoints
- `.codex/skills/documentation-*/` - backing Codex skill packages
- `docs/skills/documentation-command-skill-map.md` - trigger-to-skill inventory

## Second-Opinion Trigger Parity

The `/second-opinion:*` namespace is available through:

- `.claude/commands/second-opinion/*.md` - source command inventory
- `.codex/prompts/second-opinion/*.md` - slash-compatible entrypoints
- `.codex/skills/second-opinion-*/` - backing Codex skill packages
- `docs/skills/second-opinion-command-skill-map.md` - trigger-to-skill inventory

## QA Trigger Parity

The `/qa:*` namespace is available through:

- `.claude/commands/qa/*.md` - source command inventory
- `.codex/prompts/qa/*.md` - slash-compatible entrypoints
- `.codex/skills/qa-*/` - backing Codex skill packages
- `docs/skills/qa-command-skill-map.md` - trigger-to-skill inventory

## Project Trigger Parity

The `/project:*` namespace is available through:

- `.claude/commands/project/*.md` - source command inventory
- `.codex/prompts/project/*.md` - slash-compatible entrypoints
- `.codex/skills/project-*/` - backing Codex skill packages
- `docs/skills/project-command-skill-map.md` - trigger-to-skill inventory

## Spec Trigger Parity

The `/spec:*` namespace is available through:

- `.claude/commands/spec/*.md` - source command inventory
- `.codex/prompts/spec/*.md` - slash-compatible entrypoints
- `.codex/skills/spec-*/` - backing Codex skill packages
- `docs/skills/spec-command-skill-map.md` - trigger-to-skill inventory

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
