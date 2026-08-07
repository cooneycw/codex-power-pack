# Skill Activation and Outcome Evaluation

Issue #161 adds a versioned evaluation harness for the priority Codex skills.
It distinguishes whether a failure came from routing to the wrong skill,
missing workflow steps, an unavailable or broken runtime, or an incomplete
output. Project composition cases additionally name artifact, parser, grouping,
issue-body, and mapping failures.

## Contracts and commands

- `.agents/skill-evaluation-cases.json` preserves the historical Stage 0
  capture and owns the runnable Stage 4 suite.
- `.agents/skill-evaluation-cases.schema.json` validates cases, thresholds, and
  bounded-live defaults.
- `.agents/skill-evaluation-output.schema.json` constrains live model output.
- `make skill-eval-check` runs all deterministic adapters and emits JSON.
- `make skill-eval-live` runs at most the configured live cases. Use direct CLI
  filters such as `--skill`, `--case`, `--category`, or `--tag` for smaller
  investigations.

Deterministic evaluation reads checked-in skill text, executes the real
`project-next` engine against versioned fixtures, and checks the isolated
project-init/Spec Sync composition corpus. It runs on every push and pull
request through Woodpecker and is part of `make verify`.

## Live safety boundary

The live lane refuses to start without `--allow-live`. Each case runs through
`codex exec --json` in a new temporary directory with `--ephemeral` and a
read-only sandbox. The harness passes only a small environment allowlist,
enforces case, timeout, total-token, and event-output limits, and deletes the
temporary directory after the constrained response is parsed.

Raw prompts, event streams, and final responses are not retained. Persisted
artifacts contain only case identifiers, classifications, contract layers,
latency, token counts when the CLI reports them, and redacted short reasons.
Live summary files named `skill-eval-live-*.json` are pruned after 14 days.
An unavailable CLI or model is reported as `unavailable`; it is never promoted
to a passing result.

The current `codex exec` surface accepts prompt text but cannot attach the
separate skill input item used for host-level selection of an explicit-only
plugin skill. Direct `project-init` cases remain in the suite but report
`unavailable` when that host input cannot be supplied; deterministic procedure
checks still cover them, and unavailable cases do not contribute to recall.

## Outcome taxonomy

| Outcome | Contract layer | Meaning |
|---|---|---|
| `unavailable` | `unavailable` | The live evaluator could not run |
| `activation_failure` | `routing` | Codex selected the wrong skill or selected one for a negative prompt |
| `procedure_failure` | `procedure`, `artifact`, `parser`, `grouping`, or `mapping` | A required safety or workflow step failed |
| `runtime_failure` | `runtime` | The bounded command timed out, errored, or exceeded a limit |
| `output_failure` | `output` or `issue-body` | The promised result fields or body contract were absent |
| `pass` | none | Every checked contract passed |

Deterministic checks deliberately set `activation_checked=false`; they prove
procedure and output contracts but cannot claim model recall or precision.
Only live results contribute to direct recall, indirect recall, and negative
precision.

## Cadence and release policy

- Deterministic suite: every pull request and push, blocking.
- Live suite: manually before a plugin release and weekly while Wave 7 is under
  active rollout; the release owner runs and reviews it.
- Thresholds: 100% direct recall, at least 90% indirect recall for implicit
  priority skills, and at least 95% negative precision.
- A measured failure blocks the affected skill release. An exception must name
  an owner, reason, affected cases, and an expiry date.
- An unavailable live lane is “not checked,” not green. Releases need a recent
  successful live summary or a documented time-bounded exception.

The v0.2.0 release lane selects 20 live cases with a 320,000-token ceiling.
Release results and the implicit-entrypoint decision are recorded in
`docs/wave-7-release-validation.md`; raw prompts and event streams remain
ephemeral.
