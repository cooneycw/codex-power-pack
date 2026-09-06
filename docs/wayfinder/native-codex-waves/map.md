---
wayfinder:
  kind: map
  version: 1
  title: Native Codex wave orchestration
  status: proposed
  tracker: local-markdown
  destination_status: proposed
  tickets_dir: tickets
---

# Native Codex wave orchestration

## Destination

**Proposed; human confirmation pending.** Produce an agreed, implementation-ready
specification for the chosen first milestone of native Codex wave orchestration,
including its ownership boundaries, session identity and communication contract,
and observable acceptance evidence. The specification should be ready for a
separate implementation-ticket handoff; this map does not implement the port.

## Notes

- No first-milestone preference has been selected. The opening discussion must
  let the human choose among native Codex waves in CxPP first, Kyle-native Codex
  formations from the first milestone, or a standalone native Codex workflow.
- The source assessment is
  `/home/cooneycw/Projects/codex-power-pack/docs/cpp-wave-comparison.md`, reviewed
  on 2026-09-06. It is coordinator-owned and intentionally remains outside this
  map's tracked files. Issue
  [Add native codex-wayfinder skill and starter map for Codex wave orchestration](https://github.com/cooneycw/codex-power-pack/issues/185)
  preserves the source links and constraints.
- The comparison's staged delivery sequence is a recommendation, not a human
  decision. Do not copy it into **Decisions so far** unless the human selects it.
- Preserve CxPP's current `$spec-sync` preparation role and `$project-next`
  contract unless a later human decision explicitly changes the destination.
- Planning and local-map edits are in scope. This note does not authorize source
  import, live message testing, global plugin changes, production implementation,
  merge, or deployment.
- Apply the finished `$codex-wayfinder` skill from its explicit path if the
  current Codex session predates plugin discovery of the skill.

## Decisions so far

None yet.

## Not yet specified

- The exact CPP Flow source snapshot, helper set, and CxPP runtime overlays needed
  by the chosen milestone.
- The detailed gate-authority, assignment-recovery, Spec Kit input, and PR-watch
  contracts. Their shape depends on the first-milestone boundary and session
  communication decisions.
- Whether Kyle's launch, boot, model, resume, and process-generation seams enter
  this map. This depends on when the human wants Kyle-native formations.
- The end-to-end acceptance matrix, including worker count, gate holds, failed
  CI, compaction/restart, stale listeners, replay, and multi-host boundaries.

## Out of scope

- Implementing or deploying the wave port while working this decision map.
- Treating CPP's `codex:auto` driver policy as the capability model for native
  Codex sessions.
- Replacing CxPP's existing `$project-next` decision contract or silently
  introducing a second Spec Kit issue compiler.
