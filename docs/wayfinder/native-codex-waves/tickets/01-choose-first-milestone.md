---
wayfinder:
  kind: ticket
  version: 1
  id: choose-first-milestone
  title: Choose the first milestone for native Codex orchestration
  type: discussion
  interaction: human
  status: closed
  blocked_by: []
  claim:
    owner: null
    claimed_at: null
---

# Choose the first milestone for native Codex orchestration

## Question

Which shape should the first implementation milestone take: native Codex waves
in CxPP before Kyle support, Kyle-native Codex formations from the first
milestone, or a standalone native Codex workflow separated from CPP Flow?

## Context

The comparison recommends proving native Codex waves in CxPP before integrating
Kyle, but that sequence has not been approved. Starting with Kyle increases the
first milestone's lifecycle surface. A standalone workflow may reduce inherited
CPP coupling but gives up reuse of Flow's registry, policy, transition, and PR
watch contracts. Ask the human what outcome they need first and what they are
willing to defer; do not turn the recommendation into their answer.

## Resolution

The user selected the staged boundary: prove native Codex wave orchestration in
CxPP first, then integrate native Codex sessions with Kyle. The first milestone
therefore reuses and adapts CPP Flow's wave contracts inside CxPP while deferring
Kyle launch, boot, resume, model-selection, and process-generation integration.

After this planning map is complete, the user explicitly wants the resulting
wave and implementation issues created and orchestrated through completion.
That follow-on authorization does not move implementation or issue creation
inside this planning ticket.

### Scope correction — 2026-09-07

The user clarified that Kyle work was feasibility-only. No Kyle integration or
implementation is authorized. Do not implement, commit, push, open or merge PRs,
configure, deploy, or assign Kyle #749–#754 or any existing Kyle issue. Their
premature filing and earlier delivery-policy wording do not grant authority.

The current delivery objective is CxPP native wave orchestration, subject to its
remaining planning choices. This correction supersedes the earlier inference
that Kyle integration would follow as an authorized delivery milestone; the
historical wording above is retained only to make the correction visible.

### Project naming and transfer update — 2026-09-07

The user created Sage as an independent project in the private
`cooneycw/sage` repository. The six prematurely filed Kyle planning issues
#749–#754 were transferred, with their history and redirects preserved, to Sage
#1–#6. They are planning candidates only and require Sage-specific scope before
any delivery work.

The original Kyle maintenance blocker links were removed, and the former
65-edge graph is historical only; it cannot authorize or drive dispatch. Kyle
source or runtime integration remains unauthorized. This naming and transfer
decision does not establish a Sage application milestone or choose a framework.
