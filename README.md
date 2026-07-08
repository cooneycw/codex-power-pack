# Codex Power Pack

Codex Power Pack is a Codex-first automation toolkit.
It preserves CI/CD helpers, security tooling, secrets management, templates,
generated command skills, and tests for Codex-centric workflows.

## What Is Included

- `.codex/skills/` - Codex skill packages generated from claude-power-pack (pull model, #75); see `.codex/skills/README.md`
- `vendor/claude-power-pack/` - pin + drift manifest for the generated skills
- `.codex/cicd.yml` and `.codex/cicd_tasks.yml` - Codex-local CI/CD manifests
- `AGENTS.md` - the canonical repo instructions for Codex
- `lib/creds/`, `lib/security/`, `lib/cicd/` - reusable Python libraries
- `templates/`, `scripts/`, `docs/skills/`, `tests/` - supporting workflow assets
- `templates/config.toml.example` and `docs/HOST_MANAGED.md` - client-side
  pointers for externally managed MCP services
- `docs/security/threat-model.md` - Phase 0 guard design for plugin marketplace modernization

## Quick Start

```bash
git clone https://github.com/cooneycw/codex-power-pack.git
cd codex-power-pack
uv sync --extra dev
make verify
```

Distribution is handled by native Codex plugins. For project bootstrapping from
the plugin, use the thin `cxpp:init` fallback rather than copying skills out of
this checkout.

For host-managed MCP tools, merge `templates/config.toml.example` into your
Codex config or run:

```bash
codex mcp add second-opinion --url http://127.0.0.1:8080/mcp
codex mcp add playwright -- npx -y @playwright/mcp@latest
```

`mcp-second-opinion` is an external host service; this repo only documents the
pointer. See `docs/HOST_MANAGED.md` for owners and health checks.

## Runtime Boundary

This repo does not own MCP server code, Docker Compose runtime, or deployment
entrypoints. Configure external MCP servers and native Codex plugins outside
this checkout. The checked-in MCP config is a pointer template, not lifecycle
management.

## Codex Architecture

- Codex instructions live in `AGENTS.md`
- Skill packages live in `.codex/skills/`, generated from claude-power-pack (see `.codex/skills/README.md`)
- Runtime config targets `.codex/` paths and host-managed pointers in
  `templates/config.toml.example`
- Secrets storage uses `~/.config/codex-power-pack/`

## Distribution

Codex command discovery is delivered through native Codex plugins. This
repository keeps source prompts, skills, docs, and tests, but it does not install
or link global skill packages from this checkout.

The `/project:*` namespace in this repository currently includes:
- `/project:help`
- `/project:init`

## Command Skills

The shared command families are **generated** Codex skills under
`.codex/skills/<family>-<command>/`, pulled byte-for-byte from claude-power-pack's
`.claude/commands/` single source (the pull side of the source-of-truth bridge, #75)
and pinned by commit SHA in `vendor/claude-power-pack/PIN`. The skill dir name is the
trigger: `/flow:auto` maps to `.codex/skills/flow-auto/`.

Families carried: `browser`, `cicd`, `cpp`, `documentation`, `evaluate`, `flow`,
`github`, `project`, `qa`, `second-opinion`, `secrets`, `security`,
`self-improvement`. `claude-md` is not carried - the Codex-native `agents-md` family
covers the AGENTS.md world (epic #64/#66).

**Do not hand-edit `.codex/skills/`.** The drift gate (`make codex-skills-check`)
fails CI on any divergence from the pinned copy. To change a skill, edit
`.claude/commands/<family>/` in claude-power-pack, regenerate there
(`make codex-skills`), then re-pull here (`make codex-skills-refresh`). See
`.codex/skills/README.md`.

## Verification

```bash
make lint
make test
make typecheck
make verify
```

## Security Design

The plugin marketplace modernization wave is gated by
`docs/security/threat-model.md`. Epics C, D, and E must not merge implementation
PRs until the owner records sign-off on issue #69.

## Status

This repo is a first-pass Codex replication, not a full semantic rewrite of
every historical document. The core code paths, manifests, prompts, and top-level
instructions are adapted for Codex use. Runtime MCP servers and compose/deploy
entrypoints are intentionally external to this repository.
