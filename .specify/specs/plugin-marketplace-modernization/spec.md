# Feature Specification: Plugin Marketplace Modernization

> **Branch:** `spec/plugin-marketplace-modernization`
> **Created:** 2026-07-07
> **Status:** In Review

---

## Overview

Codex Power Pack (CxPP) is a first-pass Codex replication of claude-power-pack
(CPP), frozen in early June 2026. Since then, two things changed underneath it:

1. **Codex shipped native plugins and a marketplace** (March 2026, matured
   since): `.codex-plugin/plugin.json` bundles skills + hooks + `.mcp.json`,
   catalogued via `.agents/plugins/marketplace.json`, installed with `/plugins`
   from git-backed sources. CxPP's custom installers
   (`skills_install_codex.py`, `mcp_install_codex.py`) predate all of this.
2. **CPP retired the architecture CxPP still embodies**: bundled MCP servers
   behind a docker-compose runtime (CPP #469 externalized second-opinion and
   the sidecar; CPP #420 retired spec_bridge; CPP epic #417 Phase B moved
   distribution to the native plugin marketplace).

This spec modernizes CxPP into a 9/10 repo whose core objective is
**scaffolding of GitHub specs and new projects from Codex**, with the same
native-first philosophy CPP applies to Claude Code: defer to what the harness
provides, ship only what adds value on top.

## Ratified Decisions (owner-grilled 2026-07-07)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Source of truth | **Hybrid.** Shared command families are authored once in CPP `.claude/commands/` and generated into CxPP via a cross-repo sync (evolution of CPP `codex-prompt-sync.py`). CxPP independently owns everything Codex-native: plugin manifests, hooks, rules, AGENTS.md tooling, marketplace catalog, `config.toml` wiring. The frozen `.claude/commands/` fork in this repo is deleted. |
| D2 | MCP servers | **None live in CxPP.** Externalize what does not fit the marketplace distribution model; extend what adds value. Second opinion comes from the shared external `mcp-second-opinion` server (localhost HTTP pointer, serves both harnesses). Playwright goes native (`@playwright/mcp`). nano-banana is deleted (already torn down fleet-wide). The docker-compose runtime, deploy scripts, and deploy doctor are removed. |
| D3 | Woodpecker | **Skills first.** No marketplace plugin for Woodpecker CI exists in the Codex ecosystem (verified 2026-07-07), so CxPP ships skills that drive the Woodpecker CLI/API directly, with AWS Secrets Manager access strictly through the secrets family. Friction telemetry (D6) measures whether Codex handles this reliably; promotion to an external shared MCP server is a data-driven follow-up, not a default. |
| D4 | Distribution | **Native per-family plugins** under `plugins/<family>/` with `.codex-plugin/plugin.json`, catalogued in `.agents/plugins/marketplace.json`, installable individually (respects the ~8k-char skill-list budget). One thin `cxpp:init/update/status` fallback survives for what plugins cannot carry: `config.toml` MCP pointers, secrets bootstrap, spec-kit install, hooks/rules install. Custom skill installers are retired. |
| D5 | Scope | **Full parity wave**, planned as epics/stories now and synced to GitHub issues in this repo. |
| D6 | Friction telemetry | Codex needs a friction-measurement equivalent of CPP's permission census and friction ledger, writing to the **same shared Postgres fleet ledger** (Tailscale-internal; connection via secrets, never hardcoded). Cross-repo issues are posted to claude-power-pack to feather shared functionality (generator, ledger schema). |
| D7 | Delivery | **Codex builds all tasks** (issues written self-contained for `codex:auto`-style delegation). **Claude reviews at the end and tunes gaps.** Every ported family's definition of done includes a dogfood gate: Codex itself runs the family's core skill end to end. |
| D8 | Security first | Phase 0 threat model with an explicit exit bar precedes scaffolding. Known weak spot: Codex fumbling AWS secret keys. Borrow-vs-build spike on existing Codex secret-guard plugins (Secret Guard, Agent Guard) to reduce surface area. |

## Target Architecture

```
codex-power-pack/
├── AGENTS.md                          # canonical Codex instructions (rewritten)
├── .agents/
│   └── plugins/marketplace.json       # repo marketplace catalog (git-backed source)
├── plugins/
│   └── <family>/
│       ├── .codex-plugin/plugin.json  # manifest: skills (+hooks/.mcp.json where needed)
│       └── skills/<skill>/SKILL.md    # GENERATED for shared families, authored for Codex-native
├── lib/                               # deterministic Python helpers (cicd, creds, security)
├── scripts/                           # generators, drift guards, harness lint
├── templates/                         # project scaffolding templates
├── .specify/                          # spec-kit authoring
├── .woodpecker.yml                    # CI: gitleaks -> validate -> gates
└── tests/
```

Removed entirely: `codex-second-opinion/`, `codex-playwright/`,
`codex-nano-banana/`, `codex-woodpecker/`, `mcp-evaluate/`,
`aws-secretsmanager-agent/`, `docker-compose.yml`, `lib/spec_bridge/`,
`scripts/deploy_mcp.sh`, `scripts/deploy_doctor.py`,
`scripts/skills_install_codex.py`, `scripts/mcp_install_codex.py`,
root-level stray scripts and reference PDFs, the frozen `.claude/commands/`
fork, and the legacy `CLAUDE.md` breadcrumb.

## User Stories

### US1: Scaffold a new project from Codex [P1]

**As a** Codex user,
**I want** `$project-init` to take me from zero to a GitHub repo with
Makefile, CI, secrets wiring, and AGENTS.md,
**So that** new projects start at the quality bar instead of climbing to it.

**Acceptance Criteria:**
- [ ] Fresh machine: `marketplace add` + `/plugins` install of the project family works with no repo clone
- [ ] Codex (not Claude) scaffolds a throwaway project end to end, including first commit and CI green
- [ ] Secrets never appear in Codex output, history, or logs during the run

### US2: Author and sync GitHub specs from Codex [P1]

**As a** Codex user,
**I want** spec-kit authoring plus gh-CLI issue sync as skills,
**So that** specs and their issue waves are produced the same way CPP does it.

**Acceptance Criteria:**
- [ ] `$spec-adopt` installs official spec-kit (which supports Codex) into a target repo
- [ ] Spec -> epics/stories sync to GitHub issues via gh CLI (no label adapter, mirroring CPP #418)

### US3: Daily-driver parity [P2]

**As a** CPP user working in Codex,
**I want** the flow, github, cicd, secrets, security (deterministic),
agents-md, documentation, qa, evaluate, and self-improvement families,
**So that** switching harnesses does not mean losing the workflow.

**Acceptance Criteria:**
- [ ] Each family installs as its own plugin and passes its dogfood gate
- [ ] Generated skills carry no Claude-only constructs (CI-linted)

### US4: Measured friction, shared ledger [P2]

**As the** fleet operator,
**I want** Codex friction signals (approval prompts, secret fumbles, repeated
infra failures) written to the same Postgres ledger CPP uses,
**So that** retros compare harnesses and drive borrow/build decisions with data.

**Acceptance Criteria:**
- [ ] Fail-open capture; a down ledger never blocks work
- [ ] Rows tagged by harness; masking guard applied before any write leaves the box
- [ ] Retro skill consumes the ledger and proposes codified fixes

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Shared MCP server down | Skills degrade with a clear message; nothing in CxPP starts/owns servers |
| CPP SoT edit uses Claude-only construct | CxPP harness-lint CI gate fails the sync PR, not the installed user |
| Skill-list budget exceeded | Per-family installs keep each user under budget; descriptions front-load trigger words |
| Ledger unreachable | Fail-open, local buffer if cheap, never a hard dependency |
| gitleaks CI gate vs skill fixtures | Path-allowlist fixtures in `.gitleaks.toml`, as CPP learned |

## Out of Scope

- Running or operating any MCP server from this repo (docker, compose, deploy targets)
- A `claude:*` delegation family inside Codex (mirror of CPP `codex:*`); revisit after the wave
- browser session lease-desk machinery (Claude-specific concurrency layer); native `@playwright/mcp` suffices
- claude-md family (AGENTS.md world; agents-md family covers it)
- Publishing to OpenAI's official public plugin directory (self-serve publishing not yet open; repo marketplace + git-backed source is the distribution path)

## Existing Open Issues Absorbed

| Issue | Absorbed into |
|-------|---------------|
| #53 mandatory gitleaks in Woodpecker pipelines | Epic D (cicd story) |
| #55 project-next/project-lite missing from inventory | Epic D (project story) |
| #57 Woodpecker deployment guardrails | Epic D (woodpecker story) |
| #58 propose validation gates after repeated infra failures | Epic E (retro story) |
| #59 blocking reminder for admin-only bootstrap deps | Epic E (retro story) |
