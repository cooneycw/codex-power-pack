---
name: "evaluate-issue"
description: "Evaluate an issue with host-managed multi-model consultation and explicit checkpoints"
---

# Evaluate an Issue

Use this workflow for architecture, concept, algorithm, UI, or process decisions
that merit an independent multi-model evaluation before choosing a delivery plan.
Use the [canonical CxPP issue contract](https://github.com/cooneycw/codex-power-pack/blob/main/docs/agents/issue-contract.md)
for issue-ready versus fuller-spec output. If unavailable, report the missing
reference and continue otherwise authorized work using known project/user
instructions; do not invent missing policy or require a new approval round.

1. Gather the intended outcome, motivation, observable acceptance, domain,
   binding constraints and their rationale, supporting artifacts, and desired
   output. Separate proposed approaches from assumptions worth investigating.
   Preserve legacy constraints without recorded rationale while investigating.
   Remove secrets and unrelated private material before sending context to the service.
2. Verify the second-opinion service. If unavailable, state the standard
   graceful-degradation message, perform structured Codex reasoning locally,
   and label the result `single-model fallback` rather than implying consensus.
3. With the service available, ask two or more selected models for a divergence
   scan. Synthesize agreements, disagreements, risks, and unanswered questions.
4. Present those tensions to the user, then perform a structured local
   trade-off analysis. Obtain authorization for multi-model validation of the
   recommendation when it has not already been granted under the active authority.
5. Produce an issue-ready recommendation for small work, or a spec-ready one
   when uncertainty, architecture or coordination warrants it: recommendation,
   alternatives rejected, evidence, binding constraints, and open questions.
   Reference governing spec sections rather than copying an authoritative spec.
   Proposed techniques can change with explanation inside agreed outcomes,
   constraints and delegated authority; consequential boundary changes need
   evidence and the required agreement before acting. Do not
   create files or GitHub issues unless the user authorizes that follow-on work.

The service is advisory. Repository tests, source, and user decisions remain
authoritative over any model response.
