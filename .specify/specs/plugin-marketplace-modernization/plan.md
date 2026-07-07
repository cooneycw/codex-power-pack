# Implementation Plan: Plugin Marketplace Modernization

> **Spec:** `.specify/specs/plugin-marketplace-modernization/spec.md`
> **Delivery model:** Codex builds all tasks (issues are self-contained for
> `codex:auto`-style delegation). Claude reviews at the end (Epic F) and tunes
> gaps. Cross-repo companion issues are filed in claude-power-pack.

## Sequencing

```
Epic 0 (threat model, exit bar)        <- blocks C, D, E scaffolding
   |
Epic A (demolition/externalize)        <- independent of B, unblocks clean tree
   |
Epic B (SoT sync bridge, CPP-side)     <- feeds generated skills into C/D
   |
Epic C (plugin packaging)              <- distribution rails for D
   |
Epic D (family ports, per-family dogfood gates)
   |
Epic E (friction telemetry)            <- can start after 0; informs D7 woodpecker verdict
   |
Epic F (quality bar, E2E acceptance, Claude review)
```

## Epic 0: Threat Model and Guard Design (Phase 0, explicit exit bar)

Security-first standing rule: the guard is designed before the scaffolding.

- **0.1** Threat model: AWS secret-key exposure paths in Codex sessions
  (env, `config.toml`, `history.jsonl`, session logs, CI logs); plugin
  supply chain (git-backed source pinning policy); hooks are non-managed and
  user-reviewed; friction telemetry egress (what leaves the box, masking
  before write). Deliverable: `docs/security/threat-model.md`.
- **0.2** Borrow-vs-build spike: evaluate Secret Guard (pre-commit
  pattern+entropy scanner) and Agent Guard (real-time secret-leak guardrails
  for Codex/Claude Code) for the secrets-masking layer. Deliverable: adopt or
  build decision recorded in the threat model.

**Exit bar:** guard designs for (a) secrets masking in Codex sessions,
(b) ledger write path, (c) plugin pinning policy are documented and
owner-approved before any Epic C/D/E implementation PR merges.

## Epic A: Demolition - Externalize MCP, Retire Runtime (mirror CPP #469)

- **A1** Delete bundled servers and runtime: `codex-second-opinion/`,
  `codex-playwright/`, `codex-nano-banana/`, `codex-woodpecker/`,
  `mcp-evaluate/`, `aws-secretsmanager-agent/`, `docker-compose.yml`,
  `scripts/deploy_mcp.sh`, `scripts/deploy_doctor.py`, all `make docker-*`
  and `deploy*` targets.
- **A2** Wire shared external MCP: `config.toml` pointer template for the
  shared `mcp-second-opinion` server (localhost HTTP), native
  `@playwright/mcp` registration; write the host-managed-services doc
  (what runs where, who owns it - the CPP HOST_MANAGED analog).
- **A3** Purge legacy strays: root Reddit scripts, reference PDF,
  `INSTALLATION_ISSUES.md`, stale docs; retire `lib/spec_bridge/`
  (CPP #420 parity); delete legacy `CLAUDE.md` breadcrumb.
- **A4** Retire `scripts/skills_install_codex.py`,
  `scripts/mcp_install_codex.py`, and their make targets/doctor checks.

## Epic B: Single-SoT Sync Bridge (hybrid model)

- **B1** *(claude-power-pack issue)* Evolve `codex-prompt-sync.py` into a
  SKILL.md generator: per-command Codex skills with progressive-disclosure
  layout, harness transforms, trigger-word-front-loaded descriptions.
- **B2** *(claude-power-pack issue)* Cross-repo publish: generator emits into
  codex-power-pack via PR (eli5-gate vendoring pattern, reversed direction);
  `--check` drift gates wired into both repos' CI.
- **B3** Delete the frozen `.claude/commands/` fork from this repo; generated
  skills land under `plugins/<family>/skills/` carrying GENERATED markers.
- **B4** Harness-lint CI gate: fail any skill referencing Claude-only
  constructs (Agent tool, native worktrees, `!` prefix, `/plugin` refs,
  CLAUDE.md paths).

## Epic C: Native Plugin Packaging and Distribution

- **C1** Marketplace scaffold: `.agents/plugins/marketplace.json` + first
  plugin (project family) with `.codex-plugin/plugin.json`; prove E2E with
  `/plugins` install from the repo as a git-backed source.
- **C2** Package all families as per-family plugins; per-skill
  `agents/openai.yaml` (default `allow_implicit_invocation: false`,
  display metadata).
- **C3** Version pinning and release process: tagged releases, marketplace
  entries pin ref/sha, upgrade documented.
- **C4** `cxpp:init/update/status` thin fallback for non-plugin infra:
  `config.toml` MCP pointers, secrets bootstrap, spec-kit install,
  hooks/rules install.
- **C5** Docs cutover: rewrite `README.md` + `AGENTS.md` for the new
  architecture; quick start becomes marketplace add + `/plugins` install.

## Epic D: Family Ports (each story ends with a Codex dogfood gate)

- **D1** project: `$project-init` zero-to-repo orchestration (primary
  objective); absorb #55 (project-next / project-lite inventory gap).
- **D2** spec: official spec-kit adoption for Codex + gh-CLI issue sync;
  no label adapter (CPP #418 decisions).
- **D3** flow: issue lifecycle (start/finish/merge/status) adapted to Codex;
  port layout-aware merge logic (CPP gh-pr-merge.sh lineage).
- **D4** github: issue management family (gh CLI).
- **D5** cicd: Makefile validation + pipeline generation; absorb #53
  (mandatory gitleaks step in generated Woodpecker pipelines).
- **D6** secrets: AWS Secrets Manager family with masking guardrails per the
  Phase 0 spike outcome (borrowed guard or built hooks/rules).
- **D7** woodpecker: skills driving Woodpecker CLI/API directly (replaces the
  deleted MCP server); secrets strictly via D6; absorb #57 (deploy
  guardrails). Telemetry from Epic E decides if this ever becomes an external
  shared server.
- **D8** security: deterministic half only (gitleaks, git-history, pip-audit,
  gate); semantic review defers to Codex native review.
- **D9** agents-md: lint + help (generated from CPP's agents-md family).
- **D10** documentation: c4 diagrams + pptx (no nano-banana path).
- **D11** qa: qa-test web testing family.
- **D12** evaluate + second-opinion client commands against the shared server.

## Epic E: Codex Friction Telemetry (shared ledger)

- **E1** Spike: Codex hooks.json event surface - which lifecycle events can
  observe approval prompts / command failures; rules interplay; design the
  masking-before-write guard (Phase 0 dependency).
- **E2** Capture implementation: fail-open writer to the shared Postgres
  fleet ledger (connection via secrets, never hardcoded), rows tagged
  `harness=codex`.
- **E3** *(claude-power-pack issue)* Ledger feathering: harness tag in
  schema/consumers so retros compare harnesses.
- **E4** Retro loop: self-improvement retro skill for Codex consuming the
  ledger; absorb #58 (propose validation gates after repeated failures) and
  #59 (blocking reminder for admin-only bootstrap deps).

## Epic F: Quality Bar and Close-Out (the 9/10)

- **F1** Woodpecker CI refresh: gitleaks first, validate, image gates;
  git-less container guard on tests.
- **F2** Test suite + drift gates green; `make verify` meaningful
  post-demolition.
- **F3** E2E acceptance: Codex, from a fresh install via `/plugins`,
  scaffolds a throwaway project AND authors+syncs a gh spec end to end.
- **F4** Claude review-and-tune: gap analysis pass over the whole wave,
  fixes filed/applied (owner-decided delivery model D7).
