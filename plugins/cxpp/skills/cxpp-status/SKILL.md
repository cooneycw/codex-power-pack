---
name: "cxpp-status"
description: "Report installed Codex Power Pack plugins, host pointers, health, and drift without changing the machine"
---

# CxPP Status

Use this skill for `/cxpp:status` to inspect Codex Power Pack host wiring. This
skill is read-only: it must not install, update, write, restart, or delete
anything.

## Procedure

1. Run `codex plugin list --json` and report installed CxPP family plugins,
   their enabled state, marketplace source, and pinned ref when Codex exposes
   it. Do not expose authentication data.
2. Run `codex mcp get second-opinion` and `codex mcp get playwright`. Report
   each pointer as configured or missing without reading global TOML directly.
3. When `second-opinion` is configured for localhost, run
   `curl -sf http://127.0.0.1:8080/readyz`; otherwise label its health as not
   checked. Run no process-management command.
4. Check whether optional spec-kit and reviewed hooks/rules are present using
   their documented status commands or file existence only. Never print rule,
   hook, or configuration contents that might contain secrets.
5. Flag a marketplace source without an immutable commit SHA or signed release
   tag as a pinning/drift warning. A warning is informational and must not
   trigger an update.

## Report

Use one row per component: `plugins`, `second-opinion`, `playwright`, `spec-kit`,
`secrets guidance`, and `hooks/rules`. Give each a status of `healthy`,
`configured`, `missing`, `unhealthy`, `not checked`, or `warning`, followed by
the smallest safe follow-up.
