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

## Procedure

1. Confirm Codex is available with `codex --version`, then ask which components
   to configure: CxPP marketplace/plugins, host-managed MCP pointers, spec-kit,
   secrets-provider guidance, and reviewed hooks/rules. Do not assume all are
   wanted.
2. For marketplace/plugins, require a signed release tag or immutable commit
   SHA. Show the selected sparse paths, then, after approval, add the marketplace
   and install only requested family plugins. Do not use a floating branch ref.
3. For MCP pointers, show the two entries from the CxPP config pointer template
   (`templates/config.toml.example` in a checkout or `config.toml.example` in
   the installed plugin): `second-opinion` at
   `http://127.0.0.1:8080/mcp` and `playwright` via
   `npx -y @playwright/mcp@latest`. After approval, use the matching `codex mcp
   add` commands. Do not edit TOML by string replacement.
4. For spec-kit, ask whether the official tool should be installed for the
   current user. Confirm its documented install command and version before
   executing it; do not install it as a side effect of another component.
5. For secrets, install or enable the requested `secrets` family plugin and
   point to its provider setup. Do not ask for credentials or echo environment
   values.
6. For hooks/rules, show every proposed file and destination. Run
   `codex execpolicy check` against a proposed rule before writing it. Install
   only reviewed, additive entries and wait for Codex's normal hook-trust review.
7. Run only non-secret checks: `codex mcp get second-opinion`,
   `codex mcp get playwright`, and, when the service is expected locally,
   `curl -sf http://127.0.0.1:8080/readyz`. A failed health check is a report,
   not a reason to start the service.

## Report

Report each component as `configured`, `already configured`, `skipped`, or
`needs host prerequisite`. Include the exact non-secret follow-up needed and
state that a new Codex session is required after MCP configuration changes.
