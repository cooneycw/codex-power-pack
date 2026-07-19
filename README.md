# Codex Power Pack

Codex Power Pack is a Codex-first automation toolkit.
It preserves CI/CD helpers, security tooling, secrets management, templates,
generated command skills, and tests for Codex-centric workflows.

## What Is Included

- `.codex/skills/` - Codex skill packages: generated shared families from claude-power-pack plus CxPP-owned native skills; see `.codex/skills/README.md`
- `.agents/plugins/marketplace.json` and `plugins/<family>/` - native Codex marketplace catalog and per-family plugin packages
- `vendor/claude-power-pack/` - pin + drift manifest for the generated skills
- `.codex/cicd.yml` and `.codex/cicd_tasks.yml` - Codex-local CI/CD manifests
- `AGENTS.md` - the canonical repo instructions for Codex
- `lib/creds/`, `lib/security/`, `lib/cicd/` - reusable Python libraries
- `templates/`, `scripts/`, `docs/skills/`, `tests/` - supporting workflow assets
- `templates/config.toml.example` and `docs/HOST_MANAGED.md` - client-side
  pointers for externally managed MCP services
- `docs/security/threat-model.md` - Phase 0 guard design for plugin marketplace modernization

## Quick Start

Install the marketplace at a signed release tag or immutable commit SHA, then
install just the plugins you need. Add `cxpp` when you also want the
consent-first host-infrastructure bootstrap.

```bash
codex plugin marketplace add cooneycw/codex-power-pack \
  --ref <release-tag-or-commit-sha> \
  --sparse .agents \
  --sparse plugins/project \
  --sparse plugins/github \
  --sparse plugins/cxpp
codex plugin add project@codex-power-pack
codex plugin add github@codex-power-pack
codex plugin add cxpp@codex-power-pack
```

Run `/cxpp:init` to review and selectively configure host-managed pointers.
It asks before changing global Codex configuration.

Install only the family plugins you need from the repo marketplace with a
pinned Git ref. Include `.agents` plus the selected `plugins/<family>` paths in
the sparse checkout:

```bash
codex plugin marketplace add cooneycw/codex-power-pack \
  --ref <release-tag-or-commit-sha> \
  --sparse .agents \
  --sparse plugins/project \
  --sparse plugins/github
codex plugin add project@codex-power-pack
codex plugin add github@codex-power-pack
```

The catalog currently exposes per-family packages for `project`, `spec`,
`flow`, `github`, `cicd`, `secrets`, `woodpecker`, `security`, `agents-md`,
`documentation`, `qa`, `evaluate`, `second-opinion`, `self-improvement`, and
`cxpp`. Install `spec` for consent-first `$spec-adopt` setup of official
spec-kit and `$spec-sync` task-to-issue previews. Install `cxpp` when a fresh
machine needs the consent-first `/cxpp:init`, `/cxpp:update`, and
`/cxpp:status` fallback skills.

When the marketplace or family plugins are missing, `/cxpp:init` and
`/cxpp:update` offer four suite profiles:

- **Minimal** installs only `cxpp`.
- **Recommended** installs `project`, `spec`, `flow`, `github`, `cicd`,
  `secrets`, `security`, `agents-md`, `documentation`, `qa`,
  `self-improvement`, and `cxpp` for common development workflows.
- **Full suite** installs every published family listed above.
- **Custom** installs only the individually selected families.

Before writing, the workflow shows the exact sparse paths and plugins plus the
previous, requested, and resolved immutable refs. Suite approval covers only
marketplace and plugin installation; MCP pointers, credentials, hooks/rules,
and external services retain separate consent prompts. `/cxpp:status` reports
every family as installed or missing without changing the machine.

Release installs and upgrades follow `docs/release-process.md`: use a signed
release tag or immutable commit SHA, record the resolved SHA, and preserve
rollback refs in the release notes.

See `docs/plugin-marketplace-project-e2e.md` and
`docs/plugin-marketplace-spec-e2e.md` for the project and spec-plugin E2E
transcripts.

For host-managed MCP tools, `/cxpp:init` applies the selected pointers. Manual
setup remains available:

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
- Skill packages live in `.codex/skills/`; shared families are generated from claude-power-pack, while Codex-native families are authored here (see `.codex/skills/README.md`)
- Runtime config targets `.codex/` paths and host-managed pointers in
  `templates/config.toml.example`
- Secrets storage uses `~/.config/codex-power-pack/`

## Distribution

Codex command discovery is delivered through native Codex plugins. This
repository keeps source prompts, generated skills, plugin-packaged family copies,
docs, and tests, but it does not install or link global skill packages from this
checkout.

Each plugin packages one workflow family so users can install and remove them
independently. Packaged skill payloads stay byte-identical to `.codex/skills/`;
the package-local `agents/openai.yaml` files supply display metadata and set
`allow_implicit_invocation: false` by default.

## Command Skills

The shared command families are **generated** Codex skills under
`.codex/skills/<family>-<command>/`, pulled from claude-power-pack's
`.claude/commands/` single source (the pull side of the source-of-truth bridge, #75)
and pinned by commit SHA in `vendor/claude-power-pack/PIN`. CxPP carries narrow
runtime-state adaptations where Codex-owned workflow state must live under
`.codex/` instead of `.claude/`. Installed flow helpers resolve from the loaded
skill package rather than the user's checkout or `~/.claude/scripts/`. The skill
dir name is the trigger: `/flow:auto` maps to `.codex/skills/flow-auto/`.

Families carried: `browser`, `cicd`, `cpp`, `documentation`, `evaluate`, `flow`,
`github`, `project`, `qa`, `second-opinion`, `secrets`, `security`,
`self-improvement`. `claude-md` is not carried - the CxPP-owned `agents-md` family
covers the AGENTS.md world with native `.codex/skills/agents-md-*` packages.
`project-next` and `project-lite` are CxPP-owned native project skills because
their Codex-first repository inventory behavior remains locally owned; refreshes
explicitly preserve them even when CPP generates skills with the same names.

**Do not hand-edit generated skill dirs.** The drift gate (`make codex-skills-check`)
fails CI on any divergence from the manifest. To change shared generated skill
behavior, edit `.claude/commands/<family>/` in claude-power-pack, regenerate
there (`make codex-skills`), then re-pull here (`make codex-skills-refresh`).
CxPP-owned runtime-state adaptations and native skill dirs are edited directly in
this repo; see `.codex/skills/README.md`. `make codex-skills-currency-check`
compares the adapted snapshot with a current CPP checkout, and CI runs the same
comparison against CPP `main` so upstream feature drift cannot remain silent.

## Verification

```bash
make lint
make test
make typecheck
make verify
```

## Development Checkout

Clone the repository only when contributing to Codex Power Pack itself:

```bash
git clone https://github.com/cooneycw/codex-power-pack.git
cd codex-power-pack
uv sync --extra dev
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
