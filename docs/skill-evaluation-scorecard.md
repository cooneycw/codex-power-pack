# Skill Evaluation Scorecard

> Stage 4 implementation baseline. This file contains aggregate, non-secret
> results only; raw live prompts and Codex event streams are not retained.

| Metric | Stage 0 baseline | Current deterministic | Current live | Required |
|---|---:|---:|---:|---:|
| Direct activation recall | Not measured | Not checked | 100% | 100% |
| Indirect activation recall | Not measured | Not checked | 100% | 90% |
| Negative precision | Not measured | Not checked | 100% | 95% |
| Procedure/output cases | Not available | 23/23 pass | 13 pass, 2 unavailable | 100% checked cases |

Deterministic activation is intentionally reported as **not checked** because a
fixture or static contract cannot measure model selection.

The live result was captured at `2026-08-07T00:05:25Z` using Codex CLI `0.146.1`,
plugin payload `0.1.1+codex.20260806203405`, and source commit
`5961546c5e0164879348122134ccdd7b76d24cec`. All 15 selected cases completed in
218,405 tokens under the 240,000-token ceiling. Two explicit-only
`project-init` cases were `unavailable` because `codex exec` cannot attach the
host skill input; they did not contribute to activation metrics. No checked
case had an activation, procedure, runtime, or output failure.
