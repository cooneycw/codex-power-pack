---
name: "cxpp-init"
description: "Bootstrap Codex Power Pack host wiring with explicit consent for every global change"
---

# CxPP Init

Use this skill for `/cxpp:init` or when setting up Codex Power Pack on a new
machine after installing family plugins from the pinned marketplace.

## Safety Contract

- Present the selected setup components before making changes.
- Ask for explicit approval before writing `~/.codex/config.toml`, hooks, rules,
  shell configuration, or any other global path.
- Never request, print, read, or persist secret values. The `secrets` family
  configures providers; it does not import credentials through this skill.
- Never start, stop, deploy, update, or otherwise manage `mcp-second-opinion`
  or Playwright. Missing host services are reported as prerequisites.
- Use additive updates only. Preserve existing configuration and rules.

Selecting a plugin suite consents only to the marketplace and family-plugin
actions shown in that suite's preview. It never consents to MCP pointers,
credentials, hooks, exec-policy rules, or external-service lifecycle changes;
each of those remains a separate setup component with its own approval.

## Plugin Suite Profiles

Offer these choices when the CxPP marketplace is missing or one or more
published family plugins are missing:

- **Minimal**: `cxpp` only.
- **Recommended**: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
  `security`, `agents-md`, `documentation`, `qa`, `self-improvement`, and
  `cxpp`. This is the documented default for common development workflows.
- **Full suite**: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
  `woodpecker`, `security`, `agents-md`, `documentation`, `qa`, `evaluate`,
  `second-opinion`, `self-improvement`, and `cxpp`.
- **Custom**: one or more individually selected names from the full-suite list.
  Reject unknown names, de-duplicate selections in full-suite order, and treat
  an empty selection as `skipped by user`.

## Procedure

1. Confirm Codex is available with `codex --version`, then ask which components
   to configure: CxPP marketplace/plugins, host-managed MCP pointers, spec-kit,
   secrets-provider guidance, and reviewed hooks/rules. Do not assume all are
   wanted.
2. For marketplace/plugins, run the read-only `/cxpp:status` checks first. If
   the marketplace is missing or family plugins are absent, offer Minimal,
   Recommended, Full suite, and Custom; otherwise report the suite as
   `already current` without prompting for a reinstall.
3. Require the requested marketplace ref to be either a confirmed signed
   release tag or an immutable commit SHA. Resolve a signed tag to its commit
   SHA and reject floating branch refs. Before installation, show one approval
   preview containing:
   - the chosen profile and selected plugins;
   - every sparse path, exactly `.agents` plus `plugins/<family>` for each
     selected family in full-suite order;
   - the previous marketplace ref (`none` on a fresh setup);
   - the requested signed tag or immutable commit SHA and its resolved SHA; and
   - the exact additive `codex plugin marketplace add ... --ref ... --sparse
     ...` and `codex plugin add <family>@codex-power-pack` actions.
4. After explicit approval, add the pinned marketplace snapshot and install
   only selected plugins that are missing. Do not use a floating ref, install an
   unselected family, or change host configuration as a side effect. Re-run
   `/cxpp:status` to verify the result.
5. For MCP pointers, show the two entries from the CxPP config pointer template
   (`templates/config.toml.example` in a checkout or `config.toml.example` in
   the installed plugin): `second-opinion` at
   `http://127.0.0.1:8080/mcp` and `playwright` via
   `npx -y @playwright/mcp@latest`. After approval, use the matching `codex mcp
   add` commands. Do not edit TOML by string replacement.
6. For spec-kit, ask whether the official tool should be installed for the
   current user. Confirm its documented install command and version before
   executing it; do not install it as a side effect of another component.
7. For secrets, install or enable the requested `secrets` family plugin and
   point to its provider setup. Do not ask for credentials or echo environment
   values.
8. For hooks/rules, show every proposed file and destination. Run
   `codex execpolicy check` against a proposed rule before writing it. Install
   only reviewed, additive entries and wait for Codex's normal hook-trust review.
9. Run only non-secret checks: `codex mcp get second-opinion`,
   `codex mcp get playwright`, and, when the service is expected locally,
   `curl -sf http://127.0.0.1:8080/readyz`. A failed health check is a report,
   not a reason to start the service.

## Report

Separate every result into `updated`, `already current`, `skipped by user`, or
`needs host prerequisite`. Preserve the previous ref, requested ref, and
resolved SHA in the plugin report so rollback is possible. Include the exact
non-secret follow-up needed and state that a new Codex session is required after
plugin or MCP configuration changes. Re-running the same approved profile at
the same ref must produce `already current`, not another marketplace or plugin
write.
