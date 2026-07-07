# Codex Power Pack Threat Model

> Issue: #69
> Scope: plugin marketplace modernization Phase 0
> Status: owner sign-off pending on issue #69
> Verified against: Codex manual sections for plugins, plugin build, hooks, and
> environment variables fetched on 2026-07-07

## Purpose

This document is the Phase 0 exit-bar design for the plugin marketplace
modernization wave. Epics C, D, and E must not merge implementation PRs until
the owner records sign-off on issue #69.

The model covers four risk areas:

- AWS secret-key exposure paths in Codex sessions.
- Git-backed plugin marketplace supply chain and pinning policy.
- Non-managed, user-reviewed lifecycle hooks.
- Friction telemetry egress to the shared fleet ledger.

## Assets

| Asset | Why it matters |
| --- | --- |
| AWS credentials and AWS Secrets Manager access | Used by secrets, Woodpecker, deployment, and bootstrap workflows. Exposure grants account access. |
| Codex config and state under `CODEX_HOME` | Stores config, auth/session state, logs, sessions, skills, package metadata, and plugin state. |
| Project `.codex/` config | May contain hooks, MCP pointers, and workflow defaults that run in the project context. |
| Plugin marketplace catalogs | Define installable plugin sources and versions. A poisoned catalog can redirect users to hostile code. |
| Hook command definitions | Execute local commands inside Codex lifecycle events and may observe prompts, tool input, and tool output. |
| Friction ledger rows | Operational telemetry used across the fleet. Rows can become sensitive if raw prompts, command output, or secret names are written. |

## Trust Boundaries

| Boundary | Trusted side | Untrusted or less-trusted side | Rule |
| --- | --- | --- | --- |
| User machine to Git source | Local trusted checkout | Remote marketplace repo and plugin refs | Install only pinned, reviewed refs. |
| Codex session to shell | User-approved command execution | Repo-controlled scripts, generated commands | Secrets must not be passed to repo-controlled commands unless required and masked first. |
| Project hooks to Codex | User-reviewed hook definitions | New or changed non-managed hooks | Changed hook hashes require review before trust. |
| Local telemetry buffer to shared ledger | Masked, structured telemetry | Raw prompts, raw outputs, env dumps | Mask before write; never send raw blobs. |
| CI runner to logs | CI step status and masked diagnostics | Raw environment, command traces, secrets | Disable secret echoing and scan logs/artifacts. |

## AWS Secret-Key Exposure Paths

Codex Power Pack treats AWS credentials as high-risk because the modernization
wave will drive AWS Secrets Manager access through Codex workflows, Woodpecker
skills, and project scaffolding.

Primary exposure paths:

- Environment variables in a shell spawned by Codex, including provider-specific
  variables and inline command prefixes.
- Durable `config.toml` values under global or project Codex config layers.
- `~/.codex/history.jsonl`, session stores, and other local Codex state under
  `CODEX_HOME`.
- Plaintext diagnostic logs, including opt-in Codex logs and any project-local
  `.codex-log` directory.
- Tool output shown to the model after commands such as env dumps, config reads,
  failed AWS CLI calls, or verbose SDK exceptions.
- CI logs and artifacts from generated Woodpecker pipelines.
- Plugin-bundled hooks or skills that request broad shell access and then read
  environment, config, or session files.

Required controls:

- Do not store AWS secret values in repo files, plugin manifests, marketplace
  catalogs, examples, docs, or issue comments.
- Prefer short-lived or scoped credentials over long-lived static keys whenever
  a workflow allows it.
- Load AWS values through the secrets family and register resolved secret values
  with the masking layer before any command can print them.
- Keep Codex API keys and AWS credentials shell-scoped for the command that
  needs them instead of exporting them job-wide.
- CI steps must run secret scanning before validation and must not enable shell
  tracing around secret resolution.

## Guard Design: Secrets Masking In Codex Sessions

Goal: prevent secrets from entering model context, persisted session history,
local logs, CI logs, issue comments, or the friction ledger.

Design:

1. Centralize masking in `lib.creds.masking.OutputMasker`.
2. Keep hook filters as thin adapters around the shared masking behavior instead
   of maintaining divergent regex sets in shell and Python.
3. On secret resolution, register exact secret values with the active masker
   before returning values to any workflow layer.
4. Apply masking before:
   - displaying tool output;
   - writing telemetry rows or local retry buffers;
   - writing CI summaries;
   - composing issue or PR comments;
   - persisting generated logs.
5. Run detector scans before commits and CI publication:
   - native high-confidence scanner for fast local feedback;
   - gitleaks or equivalent for full repository and history detection.
6. Use fixture-safe test construction. Tests must assemble representative
   patterns from pieces so scanners do not treat tests as leaked credentials.

Non-goals:

- Masking is not authorization. It does not make it safe to pass credentials to
  arbitrary plugin code or hooks.
- Pattern masking is not complete. Exact-value registration is required for
  values fetched from AWS Secrets Manager or other providers.

Open follow-up for issue #70:

- Evaluate whether an external real-time secret guard should replace or wrap
  this masking layer. Until that decision is recorded, this repo continues with
  the built-in deterministic masker plus gitleaks-style scanning.

## Plugin Supply Chain

Codex plugins can bundle skills, apps, MCP configuration, and lifecycle hooks.
The marketplace catalog is therefore executable supply-chain metadata, not just
documentation.

Risk scenarios:

- A marketplace entry tracks a moving branch and silently picks up hostile code.
- A plugin manifest points at broad hooks or MCP config that changes after
  review.
- An upgrade pulls a new ref without preserving a reviewed manifest diff.
- A plugin source is moved, renamed, or replaced by a repository with different
  ownership.
- Generated skills inherit Claude-only or unsafe constructs from the shared
  source of truth.

Required controls:

- Keep repo-scoped marketplace metadata under `.agents/plugins/marketplace.json`.
- Store first-party plugins under `plugins/<family>/`.
- Review plugin manifests, bundled hooks, bundled MCP config, and generated
  skills together.
- CI must lint generated skills for Claude-only constructs before publication.
- Treat plugin upgrades as dependency updates with reviewable diffs.

## Guard Design: Plugin Pinning Policy

Goal: make every installed plugin source reproducible and reviewable.

Policy:

1. Production marketplace entries must pin Git-backed plugin sources to an
   immutable commit SHA or a signed release tag plus the resolved commit SHA.
2. Branch refs are allowed only for local development marketplace entries and
   must be marked non-release in the marketplace metadata or PR description.
3. Every release PR must include:
   - marketplace entry diff;
   - plugin manifest diff;
   - generated skill diff, if any;
   - hook and MCP config diff, if bundled;
   - resolved source commit SHA.
4. Upgrades must be explicit. Do not auto-upgrade marketplace refs during
   unrelated workflow runs.
5. A plugin with hooks that have not been reviewed and trusted is not considered
   installed for dogfood or release acceptance.
6. The release process must preserve rollback information: previous plugin ref,
   new plugin ref, and a short reason for the upgrade.

Implementation notes:

- The native Codex CLI supports adding Git-backed marketplaces and pinning refs.
- The CxPP release process should prefer release tags plus resolved SHAs for
  readability and reproducibility.
- Local path marketplace entries are acceptable for tests and dogfood, but they
  do not satisfy production distribution acceptance.

## Hooks

Codex hooks are lifecycle scripts loaded from active config layers and installed
plugins. Non-managed command hooks are user-reviewed and trusted by hash before
they run. Changed hooks must be reviewed again.

Allowed hook responsibilities:

- Validate high-risk commands before execution.
- Mask or reject sensitive tool output before it leaves the local process.
- Capture minimal, structured friction events after masking.
- Enforce project quality gates that do not require secrets.
- Add project-local context that is safe to reveal to the model.

Disallowed hook behavior:

- Read raw secret stores or dump environment variables for telemetry.
- Write unmasked prompts, tool input, tool output, config files, or session logs
  to external systems.
- Modify `~/.codex`, shell profiles, Git config, cloud credentials, or plugin
  marketplace config without an explicit user action.
- Install or upgrade plugins, MCP servers, or hooks as a side effect of ordinary
  workflow execution.
- Disable, bypass, or downgrade security scanners.
- Block work because the shared telemetry ledger is unavailable.

Review rule:

- Any hook that can observe prompts, command input, command output, permissions,
  or session lifecycle is security-sensitive and must be reviewed as executable
  code.

## Friction Telemetry Egress

The modernization wave needs Codex friction signals in the shared fleet ledger
so retros can compare harnesses and drive borrow/build decisions. Telemetry is
allowed only after masking and minimization.

Allowed fields:

| Field | Notes |
| --- | --- |
| `harness` | Fixed value `codex`. |
| `repo` | Repository slug or configured project identifier. |
| `branch` | Current branch name, masked first. |
| `issue` | GitHub issue number when present. |
| `event_type` | Controlled enum such as `approval_prompt`, `command_failure`, `secret_mask_hit`, `ledger_write_failure`. |
| `event_source` | Hook, skill, command family, or CI step name. |
| `severity` | Controlled enum. |
| `summary` | Short masked text, never raw command output. |
| `fingerprint` | Hash of normalized masked event content for deduplication. |
| `created_at` | Local event timestamp. |

Forbidden fields:

- Raw prompts.
- Raw tool input or output.
- Raw environment variables.
- Raw config files.
- Raw session history paths or contents beyond coarse location labels.
- Secret names when the name itself identifies a sensitive production system.
- Full stack traces if they may include request headers, connection strings, or
  SDK debug payloads.

## Guard Design: Ledger Write Path

Goal: collect useful friction data without making the shared ledger a secret
sink or an availability dependency.

Design:

1. Hooks and skills emit events to a local writer interface, not directly to
   Postgres.
2. The writer validates the event schema against an allowlist.
3. The writer masks every string field with the shared masking layer.
4. The writer rejects forbidden fields and oversized payloads.
5. The writer computes a fingerprint after masking.
6. The writer writes to the shared Postgres ledger using credentials resolved by
   the secrets family.
7. If the ledger is unreachable, the writer fails open:
   - workflow continues;
   - a minimal masked local buffer may be written if configured;
   - no retry loop blocks user work.
8. The writer records its own failures as local masked events, not as raw
   exceptions.

Required tests for implementation stories:

- Raw secret-like values in event input are absent from serialized rows.
- Forbidden fields are rejected.
- Ledger outage returns success to the caller and records a masked local
  failure signal.
- Oversized summaries are truncated after masking.
- `harness=codex` is always present.

## Exit Bar

This issue is complete only when all of the following are true:

- `docs/security/threat-model.md` is merged.
- The secrets masking design above is accepted.
- The ledger write-path design above is accepted.
- The plugin pinning policy above is accepted.
- The owner records sign-off on GitHub issue #69.

Until then, Epics C, D, and E implementation PRs remain blocked.
