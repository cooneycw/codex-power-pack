# Codex Power Pack

## Core Directives

- Never print secrets, tokens, passwords, connection strings, or raw `.env` contents.
- Use `make` targets as the canonical interface for lint, test, verify, and audit operations.
- Use `.codex/` assets as the canonical workflow surface.
- Read topic-specific docs from `docs/skills/` only when they are relevant.
- After code changes, run `make verify` unless the environment blocks it.

## Project Map

- `AGENTS.md` - canonical Codex instructions
- `.codex/skills/` - Codex skill packages. Shared families are generated from claude-power-pack and pinned by commit SHA (pull model, codex-power-pack#75), with narrow CxPP-owned runtime adaptations; CxPP-owned native skills such as `agents-md-*` and `project-lite` are authored here. `project-next` is a thin native adapter over the deterministic `lib/project_next/` contract. See `.codex/skills/README.md`.
- `.agents/plugins/marketplace.json` - repo-scoped native Codex marketplace catalog
- `.agents/skill-invocation-policy.json`, `.agents/skill-contracts.json`, and
  `.agents/skill-evaluation-cases.json` - versioned invocation policy,
  source/package/reference inventory, and dated prompt/evaluation captures;
  schemas live beside them
- `.codex/cicd.yml` - CI/CD config
- `.codex/cicd_tasks.yml` - deterministic CI/CD task manifest
- `plugins/<family>/` - native Codex plugin packages for per-family marketplace install
- `extensions/cxpp-issue-sync/` - official Spec Kit extension manifest and preview command; the packaged mirror lives under `plugins/spec/extensions/`
- `lib/` - reusable Python libraries for creds, security, and CI/CD
- `lib/skill_eval/` and `scripts/skill-eval.py` - deterministic and explicitly
  enabled bounded-live skill activation, procedure, runtime, and output evaluation
- `vendor/claude-power-pack/` - pin (`PIN`) + drift manifest (`codex-skills.sha256`) for generated `.codex/skills/` copies
- `templates/` - starter Makefiles and workflow templates
- `templates/config.toml.example` - Codex MCP pointers for host-managed services
- `docs/HOST_MANAGED.md` - host-owned MCP service inventory and health checks
- `scripts/` - shell + Python helpers, incl. `codex_skills_sync.py` (pulls + drift-gates `.codex/skills/`), `skill_contract_baseline.py` (reconciles inventory), `skill_contract_lint.py` (blocks semantic incompatibility), and `cxpp-hook-transition.py` (retains reviewed hook roots across plugin upgrade and rollback)
- `docs/skills/` - focused reference docs
- `docs/skill-contract-baseline.md` - measured Wave 7 source, package, prompt, reference, and gap baseline
- `docs/skill-evaluation.md` and `docs/skill-evaluation-scorecard.md` - evaluation safety, cadence, release policy, and aggregate results
- `docs/wave-7-release-validation.md` and `scripts/release_validate.py` - immutable release, profile-install, upgrade, rollback, and clean-project acceptance evidence
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
  `cxpp:init` fallback for checkout-based project bootstrapping once the cxpp
  family skills land.
- Keep marketplace entries pinned for release use. Repo marketplace entries under
  `.agents/plugins/marketplace.json` should declare pinning policy and be
  installed with `codex plugin marketplace add --ref <tag-or-sha>`.
- Use `docs/release-process.md` for release PRs, signed tag or SHA installs,
  upgrade transcripts, rollback refs, and changelog discipline.
- prefer `rg` for repo search
- When credential-shaped repository fixtures must be inspected, use
  `python -m lib.creds masked-read PATH [PATH...]`; never print the raw file as
  an intermediate step.

## Notes

- The shared command families live as generated Codex skills under `.codex/skills/<family>-<command>/`,
  pulled from claude-power-pack's `.claude/commands/` single source (codex-power-pack#75).
  The skill dir name is the explicit selector: `$flow-auto` ->
  `.codex/skills/flow-auto/`; `/skills` discovers installed skills. Historical
  CPP `/family:command` and faux `/skill-name` spellings are unsupported.
  CxPP applies narrow runtime-state path adaptations where Codex-owned workflow
  state must live under `.codex/` instead of `.claude/`.
- Plugin-packaged copies of generated skills under `plugins/<family>/skills/`
  keep their skill payload files byte-identical to `.codex/skills/`. The only
  package-local overlay is `agents/openai.yaml`, which supplies Codex plugin UI
  metadata. Implicit invocation is restricted to the entrypoints in
  `.agents/skill-invocation-policy.json`; secondary, help, administrative, and
  state-changing skills remain explicitly selectable.
- Reconcile by editing the upstream source, never the generated copy: edit
  `.claude/commands/<family>/` in claude-power-pack, regenerate there (`make codex-skills`),
  then re-pull here (`make codex-skills-refresh`). The drift gate `make codex-skills-check`
  fails CI on any hand-edit.
- Exception: CxPP-owned runtime adaptations, including Codex workflow-state paths
  and selection of the CxPP `lib/cicd` runner, are maintained here, mirrored into
  plugin payloads, covered by tests, and blessed by re-snapshotting
  `vendor/claude-power-pack/codex-skills.sha256`.
- `agents-md-*` is the CxPP-owned native family for the AGENTS.md world, and
  `project-lite` is a CxPP-owned native orientation skill. `project-next` is a
  CxPP-owned Codex adapter, but its decisions come exclusively from
  `lib/project_next/` and `docs/project-next-contract.md`; refreshes keep the
  adapter outside the vendored manifest without preserving a second prompt-only
  ranking policy.
- `claude-md` is not carried here (Out-of-Scope; `agents-md` covers the AGENTS.md
  world, epic #64/#66). The hand-port fork is retired.
