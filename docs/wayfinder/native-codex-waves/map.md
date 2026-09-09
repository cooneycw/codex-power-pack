---
wayfinder:
  kind: map
  version: 1
  title: Native Codex wave orchestration
  status: active
  tracker: local-markdown
  destination_status: agreed
  tickets_dir: tickets
---

# Native Codex wave orchestration

## Destination

**Agreed; scope corrected 2026-09-07.** Produce an implementation-ready
specification for native Codex wave orchestration in CxPP, including its
ownership boundaries, session identity and communication contract, and
observable acceptance evidence. Kyle work is feasibility-only and no Kyle
integration or implementation belongs to this destination. The specification
should be ready for a separate CxPP implementation-ticket handoff; this map does
not implement the port.

## Notes

- The user selected native Codex waves in CxPP. On 2026-09-07, they explicitly
  corrected the scope: Kyle work was feasibility-only, not a later authorized
  delivery milestone.
- The source assessment is
  `/home/cooneycw/Projects/codex-power-pack/docs/cpp-wave-comparison.md`, reviewed
  on 2026-09-06. It is coordinator-owned and intentionally remains outside this
  map's tracked files. Issue
  [Add native codex-wayfinder skill and starter map for Codex wave orchestration](https://github.com/cooneycw/codex-power-pack/issues/185)
  preserves the source links and constraints.
- The comparison's CxPP-first recommendation became a human decision through the
  linked opening discussion. Its later Kyle integration stage did not: the
  ticket's dated correction is authoritative.
- Preserve CxPP's current `$spec-sync` preparation role and `$project-next`
  contract unless a later human decision explicitly changes the destination.
- Planning and local-map edits are in scope now. CxPP remains the delivery
  objective, pending its actual planning choices; do not begin implementation
  while resolving the map. No wording in this map grants live message tests,
  global plugin changes, or production deployment authority.
- For later authorized CxPP delivery, the coordinator alone judges implementation
  gates and authorizes and executes merges after reviewing the exact PR head and
  named required checks. Workers implement, verify, push, and open PRs; they do
  not independently merge.
- Kyle #749–#754 and existing Kyle issues are feasibility/planning records only.
  Those six issues have since moved, with history and redirects preserved, to
  the independent private `cooneycw/sage` repository as Sage #1–#6. They are
  planning candidates that require Sage-specific scope; neither their former
  wording nor their transfer authorizes assignment or any Kyle or Sage code,
  configuration, process, PR, merge, or deployment mutation.
- The original Kyle maintenance blocker links were removed. The former 65-edge
  issue graph is historical evidence only and cannot drive dispatch. The Sage
  name and private-repository boundary do not imply an application milestone or
  select a framework.
- Apply the finished `$codex-wayfinder` skill from its explicit path if the
  current Codex session predates plugin discovery of the skill.

## Decisions so far

- [Choose the first milestone for native Codex orchestration](tickets/01-choose-first-milestone.md): deliver native waves in CxPP; Kyle remains feasibility-only, while the six transferred candidates are Sage #1–#6 in the independent private `cooneycw/sage` repository and have no delivery scope yet.

## Not yet specified

- The exact CPP Flow source snapshot, helper set, and CxPP runtime overlays needed
  by the chosen milestone.
- The detailed assignment-recovery, Spec Kit input, and PR-watch contracts. Gate
  and merge authority are settled: the coordinator judges gates and performs
  exact-head merges; workers stop after pushing and opening their PRs.
- The end-to-end acceptance matrix, including worker count, gate holds, failed
  CI, compaction/restart, stale listeners, replay, and the CxPP host boundary.

## Out of scope

- Implementing or deploying the wave port while working this decision map.
- Treating CPP's `codex:auto` driver policy as the capability model for native
  Codex sessions.
- Replacing CxPP's existing `$project-next` decision contract or silently
  introducing a second Spec Kit issue compiler.
- All Kyle implementation or integration, including launch, boot, model, resume,
  process-generation, and existing Kyle issues. The user limited Kyle to
  feasibility analysis in the
  [corrected milestone decision](tickets/01-choose-first-milestone.md).
- Dispatching from the historical 65-edge graph, treating former Kyle #749–#754
  as active Kyle work, or treating their transfer to Sage #1–#6 as delivery
  authorization. Any future Sage work needs Sage-specific scope first.
