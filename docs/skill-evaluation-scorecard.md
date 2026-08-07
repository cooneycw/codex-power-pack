# Skill Evaluation Scorecard

> Stage 4 implementation baseline. This file contains aggregate, non-secret
> results only; raw live prompts and Codex event streams are not retained.

| Metric | Stage 0 baseline | Current deterministic | Current live | Required |
|---|---:|---:|---:|---:|
| Direct activation recall | Not measured | Not checked | 100% | 100% |
| Indirect activation recall | Not measured | Not checked | 100% | 90% |
| Negative precision | Not measured | Not checked | 100% | 95% |
| Procedure/output cases | Not available | 26/26 pass | 18 pass, 2 unavailable | 100% checked cases |

Deterministic activation is intentionally reported as **not checked** because a
fixture or static contract cannot measure model selection.

The release result was captured at `2026-08-07T01:37:53Z` using Codex CLI
`0.146.1`, plugin payload `0.2.0+codex.20260807012317`, and source commit
`7c1a5c256dbab40623803a160558eba18a9f9722`. All 20 selected cases completed in
289,189 tokens under the 320,000-token ceiling. Two explicit-only
`project-init` cases were `unavailable` because `codex exec` cannot attach the
host skill input; they did not contribute to activation metrics. No checked
case had an activation, procedure, runtime, or output failure.

The release retains `$flow-auto` and `$project-next` as the only implicit
entrypoints. Three additional negative sessions confirmed that persistent
routing, hook trust, and removal requests do not implicitly activate the
explicit-only CxPP administration skills. See
`docs/wave-7-release-validation.md` for the full aggregate acceptance record.
