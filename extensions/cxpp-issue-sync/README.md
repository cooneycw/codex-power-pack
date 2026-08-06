# Codex Power Pack Issue Sync Extension

This official Spec Kit extension adds one optional, read-only preview after
`speckit.tasks`. The preview delegates compilation to the separately installed
CxPP `$spec-sync` skill, which owns readiness, grouping, GitHub writes,
idempotency, and ledger mappings.

The extension targets the reviewed Spec Kit `v0.16.0` boundary. Add it only
after installing that pinned release and the CxPP `spec` plugin:

```bash
specify extension add --dev <codex-power-pack>/extensions/cxpp-issue-sync
```

Installation and later issue creation are separate consent boundaries.
