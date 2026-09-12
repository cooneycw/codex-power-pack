# Issue Contract

This is the canonical proportional issue contract for Codex Power Pack. An issue
should make the intended result clear without turning every suggestion into an
order or making a small fix carry a full specification. These distinctions are
useful inside existing project instructions and delegated authority; they do not
replace either.

## Five distinctions, not five required fields

| Distinction | Meaning | How to treat it |
|---|---|---|
| Outcome | The observable result and why it matters | Preserve it. |
| Constraint | A boundary, including a required implementation choice | Binding; record its rationale and challenge it with evidence when appropriate. |
| Acceptance | Observable examples showing the result was reached | Use it as the evidence standard. |
| Proposed approach | A hypothesis about how to deliver the result | Revisable within the outcome, constraints and existing authority; explain substitutions. |
| Assumption | A belief that still needs investigation | Check it; do not treat it as a requirement. |

A short issue can express all relevant distinctions in a few sentences. Do not
invent proposals or assumptions to fill slots. A bug's observed behavior, expected
behavior and reproduction can be enough. Existing issues remain usable: infer the
distinctions from their context, surface material ambiguity, and do not require a
schema migration or reformat old issues before working on them.

## Outcomes, proposals and binding constraints

“Remain responsive while processing continues” describes an outcome. “Use a
background queue,” when offered as a proposed solution, names one possible
mechanism. Substituting another mechanism helps identify a proposal, but this
heuristic never overrides an explicit requirement. “Use PostgreSQL because we
must integrate with the database already deployed and supported” is a binding
constraint even though it names a mechanism.

A rationale explains why a constraint exists; it does not create the obligation.
A legacy constraint with no written rationale remains provisionally binding while
the implementer investigates. Do not silently downgrade it to a suggestion.
Changing a constraint requires evidence and agreement from the authority that
owns the decision, recorded in the reviewed plan, PR or completion evidence.

A better implementation of a proposal needs an explanation, not repeated
permission, while it preserves the agreed outcome and every constraint and stays
within existing delegated authority and tool permissions. Crossing a security,
cost, compatibility or promised-behavior boundary is consequential: get the
required agreement before acting. This policy does not waive judged flow Step-3
plans, granted file lanes or scope-change decisions.

## Choose the amount of specification

| Work | Appropriate contract |
|---|---|
| Routine bug or well-understood small change | Short issue body; no mandatory spec.md, plan.md or tasks.md. |
| Feature with uncertainty or coordination needs | Issue first; use a fuller spec when resolving that uncertainty or coordinating delivery warrants it. |
| Architectural boundary or coordinated multi-issue effort | Authoritative spec with scoped issues pointing to the governing sections. |

Size is a clue, not a file-count rule or an approval bypass. For larger work, link
the authoritative spec and relevant acceptance sections instead of copying the
whole document into every issue. A copied specification becomes another version
to keep synchronized.

`$project-init` remains an explicitly selected, destination-bound local scaffold.
It is not an issue compiler, a publication command or an automatic Spec Kit
installer. `$github-issue-create` can author a lightweight issue;
`$evaluate-issue` can resolve material uncertainty and produce an issue-ready or
spec-ready recommendation. Use the existing `$flow-auto` process for delivery.

Choose `$spec-adopt` explicitly when the fuller official Spec Kit workflow is
wanted. Its installation, force and optional-extension boundaries remain intact.
After adoption, use official constitution/specify/clarify/plan/tasks/analysis
steps. `$spec-sync` compiles that deliberately selected full-spec route and still
requires the artifacts, clean-analysis assertion, reviewed immutable source objects,
exact paths, valid dependencies/checkpoints and preview/approval. Choosing an
issue-first route does not mean making incomplete full-spec input pass the
compiler. Frozen raw object hashes and working-byte checks now bind generated
context; only a validated task-ledger successor may differ locally. Derivative
context does not prove official analysis, approval or native-wave admission.

## Worked examples

### Routine bug: short issue, no artifact ceremony

> Expired sessions cause a redirect loop. Send the user to /login with the
> original destination preserved; reopening the destination after login should
> succeed. handle_login() looks like the likely location.

The redirect behavior and observable example govern the fix. The guessed function
is a proposal. If the defect is in the router, fix it there and explain the
finding. No spec files, invented assumptions or prescribed implementation are
needed for this issue.

### Feature: responsiveness is the outcome

> Exports block the UI. Remain responsive while processing continues and show
> progress. Proposed approach: use a background queue. Do not add an infrastructure
> service, because deployment must remain a single container.

An in-process worker with a progress endpoint can replace the proposed queue if
it meets the outcome and all constraints. Explain that substitution in the plan
or PR. Adding a broker crosses the explicit deployment constraint and needs
agreement before implementation; calling it a better queue does not authorize it.

### Architecture: reference the governing spec

> Implement the query-layer half of tenant isolation. Authoritative spec:
> .specify/specs/tenant-isolation/spec.md, sections “Trust boundary” and “Migration
> order”; acceptance is US2. The storage half is tracked separately.

The issue points to the spec and narrows scope. It does not copy the spec into a
second source of requirements. The chosen full-spec workflow keeps its provenance
and readiness checks.

### Binding mechanism and undocumented legacy constraint

> Use PostgreSQL because the service must share our existing supported database.

An implementer may challenge this with evidence, but cannot silently substitute
another database just because mechanisms are sometimes proposals.

> Add pagination. Do not use the ORM's .count() here.

Even without a recorded reason, the prohibition is provisionally binding. Preserve
it while investigating whether it protects a lock-sensitive table, for example.
If evidence shows its rationale no longer applies, seek the agreement required by
the current authority model and record the reclassification where it is reviewed.
Missing rationale alone is not permission to ignore it.

## Canonical location and validation limits

The maintained definition is this file. Repository guidance links here; native
skills and independently installed plugins use the canonical CxPP URL so they do
not accidentally read a different project's similarly named document:

[Canonical CxPP issue contract](https://github.com/cooneycw/codex-power-pack/blob/main/docs/agents/issue-contract.md)

Prefer this checkout's copy when working in CxPP. If the reference is unavailable,
report that fact, preserve known project/user constraints and existing authority,
and continue otherwise authorized routine work without inventing missing policy.
No independently authored policy copy or network availability gate is required.

The routing tests check named routes, form structure, actual scaffold output and
source/package reproduction. They cannot prove that a live agent respected a
constraint or read this document. The worked cases and review judgment supply
that semantic assessment; passing a link or keyword check is not model compliance.

## Source adoption

Adapted from the shared contract delivered by CPP #856 / PR #862 at
`8ebef00ce1424f713f61150eac214a1612589604`. CxPP owns this native definition and its
native authoring routes. The generated github-issue-create reference uses the
existing global CPP PIN `f64a654f76ea8d26a33eb33f785f6e1065a823b6` plus a reviewed,
bounded #862-derived backport in `scripts/codex_skills_sync.py`.

That recipe checks the exact raw before/after CPP blob and SHA-256 witnesses
before normal Codex repository/invocation adaptations. Exact old input reproduces
the upstream addition; exact new input passes through once; other relevant source
shapes fail before publication. The global PIN does not claim to contain #856.
The #196 adoption policy and retained deferrals remain unchanged. A future pin
containing the exact new source avoids double application; changed upstream
wording requires review and retirement/update of the bounded recipe, not a silent
fallback or a general source-policy bypass.

## Bounded generated context

A generated Spec Sync issue may cache a focused extract of its authoritative source
so a receiving worker can reconstruct governing outcomes, acceptance and constraints.
This narrow cache exception does not require ordinary issues to acquire spec structure.
Read named omitted/capped source before planning when material; missing mappings mean
incomplete evidence, not no constraints. Checksums and revision references establish
neither approval nor a new authority. Material changes return to the existing judge,
then update actual text and evidence while preserving old decisions/receipts.
See [the native governing-context contract](../spec-sync-governing-context.md).
