---
name: "evaluate-issue"
description: "Evaluate an issue with host-managed multi-model consultation and explicit checkpoints"
---

# Evaluate an Issue

Use this workflow for architecture, concept, algorithm, UI, or process decisions
that merit an independent multi-model evaluation before specification.

1. Gather an explicit problem statement, domain, constraints, supporting
   artifacts, and desired output name. Remove secrets and unrelated private
   material before sending context to the service.
2. Verify the second-opinion service. If unavailable, state the standard
   graceful-degradation message, perform structured Codex reasoning locally,
   and label the result `single-model fallback` rather than implying consensus.
3. With the service available, ask two or more selected models for a divergence
   scan. Synthesize agreements, disagreements, risks, and unanswered questions.
4. Present those tensions to the user, then perform a structured local
   trade-off analysis. Ask again before running multi-model validation of the
   recommendation.
5. Produce a spec-ready outcome: recommendation, alternatives rejected,
   evidence, risks, implementation constraints, and open questions. Do not
   create files or GitHub issues unless the user authorizes that follow-on work.

The service is advisory. Repository tests, source, and user decisions remain
authoritative over any model response.
