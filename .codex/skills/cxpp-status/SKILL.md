---
name: "cxpp-status"
description: "Report installed Codex Power Pack plugins, host pointers, health, and drift without changing the machine"
---

# CxPP Status

Use this skill for `/cxpp:status` to inspect Codex Power Pack host wiring. This
skill is read-only: it must not install, update, write, restart, or delete
anything.

## Published Plugin Families

Treat the repo marketplace as authoritative for these published families, in
this order: `project`, `spec`, `flow`, `github`, `cicd`, `secrets`,
`woodpecker`, `security`, `agents-md`, `documentation`, `qa`, `evaluate`,
`second-opinion`, `self-improvement`, and `cxpp`.

## Procedure

1. Run `codex plugin marketplace list` and `codex plugin list --available
   --json`. For every published family, report `installed` or `missing`, plus
   enabled state, marketplace source, and pinned ref when Codex exposes them.
   A missing marketplace means every family not otherwise visible is `missing`;
   it is not permission to add the marketplace. Do not expose authentication
   data.
2. Flag a marketplace source without an immutable commit SHA or confirmed
   signed release tag as a pinning/drift `warning`. A warning is informational
   and must not trigger an update.
3. Run `codex mcp get second-opinion` and `codex mcp get playwright`. Report
   each pointer as configured or missing without reading global TOML directly.
4. When `second-opinion` is configured for localhost, run
   `curl -sf http://127.0.0.1:8080/readyz`; otherwise label its health as not
   checked. Run no process-management command.
5. Check whether optional spec-kit and reviewed hooks/rules are present using
   their documented status commands or file existence only. Never print rule,
   hook, or configuration contents that might contain secrets.

## Report

Start with one row per published plugin family so installed and missing families
are explicit. Then use one row per host component: `second-opinion`,
`playwright`, `spec-kit`, `secrets guidance`, and `hooks/rules`. Give host
components a status of `healthy`, `configured`, `missing`, `unhealthy`,
`not checked`, or `warning`, followed by the smallest safe follow-up. Keep this
inventory read-only and do not turn a missing row into an implicit install.
