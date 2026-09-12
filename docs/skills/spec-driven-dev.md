# Proportional Issue and Spec-Driven Development

Use the [canonical issue contract](../agents/issue-contract.md). Start with the
outcome, motivation, binding constraints and observable acceptance. A proposed
approach is a revisable hypothesis inside those boundaries; constraints without
written rationale remain binding while their purpose is investigated.

## Choose the route that fits the work

A routine fix can stay in a short GitHub issue. It does not need spec.md, plan.md
or tasks.md, and older issues need no migration. A feature can also start with an
issue; add a fuller spec when uncertainty or coordination warrants it. Architectural
boundaries and multi-issue efforts benefit from an authoritative specification,
with each issue linking its governing sections rather than copying them.

Use `$evaluate-issue` when a consequential uncertainty merits evaluation. Its
models advise; repository evidence and user/project decisions govern. Choose an
issue-ready or spec-ready recommendation according to the work. Replacing a
proposal inside agreed outcomes and constraints needs an explanation, not another
permission round. Changing a promised behavior or constraint needs the agreement
required by the existing authority model before acting.

`$project-init` is an explicitly selected local Python scaffold, with destination,
Git/commit and publication consent kept separate. Its result remains valid when
Spec Kit adoption is declined. Use `$github-issue-create` for lightweight issue
authoring and `$flow-auto` for delivery with its existing judged Step-3 plan.

## The fuller official Spec Kit route

Install the `spec` family plugin and explicitly select `$spec-adopt` when the
project needs official Spec Kit authoring. It presents the pinned `v0.16.0`
installation for approval, records the reviewed release/commit, and initializes
with `specify init --here --integration codex`. Force initialization requires the
exact affected paths and explicit approval. An already authorized action does not
need the same consent requested again.

The packaged `cxpp-issue-sync` official extension is a separate optional handoff.
Declining it leaves official authoring unchanged. Its optional `after_tasks` hook
previews readiness and groups; it does not grant issue-write authority.

Use official constitution, specify, clarify, plan, tasks and analysis steps.
`$spec-sync` then previews label-free stage/story issues using the reviewed
artifact SHA, artifacts, clean-analysis assertion, exact paths, checkpoints and
valid dependencies. Task granularity remains explicit. The compiler's existing
preview/approval, full-identity, body-ownership and recovery rules remain in force;
small work belongs on the separate issue-first route, not through relaxed compiler
checks. No GitHub MCP or label adapter is required.

Rich issues carry immutable artifact links, scoped tasks, dependencies, acceptance
and quality commands. Exact open/closed mappings are reused and successful writes
update the task ledger. Commit/path existence is not working-byte content
attestation; the existing #223 limitation remains separately tracked.

## Review the contract and evidence

Review the routine bug, export/responsiveness, architecture and binding-constraint
examples in the canonical contract. Test observable outcomes and failure modes;
use experiments when assumptions need evidence. Preserve substantive requirements
while improving a proposed design. Record agreed revisions in the existing plan,
PR or completion evidence rather than maintaining a second specification store.

Routing and form checks establish structural consistency, not live model
compliance. Use reviewer judgment for the distinction between a proposal and an
explicitly constrained mechanism.
