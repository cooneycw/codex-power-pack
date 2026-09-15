# Glossary

Three defined terms, each with the one-line test for whether something is one.
This file exists so that issues, ADRs and review surfaces can use the words
precisely; it defines vocabulary and nothing else. It is not a tier system, not
a process, and not a checker (issue #240; the bound is recorded in
[ADR 0008](../decisions/0008-instrument-negative-control-bound.md)).

These definitions are adopted from claude-power-pack's glossary as written at
CPP commit `24da854007c01595c13b5bd8e6e866dec64af48d`, with the `harness`
section rewritten for this repository's own collisions.

## instrument

**Anything whose output is read as evidence.** A test, a gate, a check, a probe,
a preflight, a drift check, a monitor, a report - the kind does not matter; what
matters is that some decision treats its output as a fact about the world rather
than re-establishing that fact itself.

The test: *is there a decision that acts on this thing's verdict?* If nothing
acts on it, it is a record, a filter, an installer or a renderer, not an
instrument. `codex-friction-hook.py` writes fail-open telemetry nobody decides
on without reading it - not an instrument. `harness_lint.py` prints a pass and
the commit proceeds - an instrument.

An instrument that cannot report the other verdict is not evidence; a green from
a blind instrument and a green from a working one are the same bytes. #245
measured two of them in this repository: `harness-lint` and `project-next-check`
each reported success having examined nothing. The global Negative Control
directive requires a committed case that makes an instrument report the other
verdict. **That requirement is bounded**, because applied to every test function
in the tree it is unaffordable, and an unaffordable rule is applied to whatever
is in front of you and skipped everywhere else:

> An instrument needs a committed negative control when its verdict is consumed
> by a decision that will not independently re-derive the fact.

- A unit test whose failure the surrounding suite would catch does not need one.
  Its green is not individually load-bearing; the suite's is.
- A gate that lets work *through* - a finish gate, a preflight, a drift check,
  `make verify` itself - does need one. Nothing downstream re-derives what it
  asserted; that is the entire reason it exists.
- A check whose green is read by a **different session or a different repo**
  always needs one, because the reader cannot see the conditions that produced
  it. In a repository whose skills are generated upstream, this is the common
  case rather than the exception.

The bound narrows *which instruments need a committed case*. It does not touch
the regression-test rule (a regression test must fail on the pre-fix code; that
costs one run, not a committed case), and it does not say an instrument outside
the bound may be blind - only that proving it is not blind is the suite's job
rather than a per-instrument obligation. The enumeration of what the bound
captures in this repository, with its count and the known blind spot of the
method that produced it, is in ADR 0008.

## harness

**The system of controls around the model**: context files, tools, permissions,
sandboxes, gates, feedback loops, delegation lanes, the CI pipeline. In this
sense CxPP *is* a harness; a skill, a contract or a single gate is one control
inside it.

The test: *does it name the whole apparatus, or one artifact in it?* If the
sentence still makes sense with "the CxPP tooling as a whole" substituted, it
means the harness. If it names a document, a script or a check, it means a
control, and should say which.

**This word is already taken in this repository, twice, in two different
narrower senses. Both stay; neither is renamed.**

- **A provenance label.** `lib/friction/models.py` fixes a friction event's
  `harness` to `codex` - "caller-provided values are ignored so every ledger
  sighting can be attributed reliably". This is the inherited CPP ledger tag
  (CPP #557 / #562), where it can also be `claude` or `shell`. It names *which
  agent CLI produced a signal*, not a system, and it is a stable write contract.
- **Someone else's harness, in a gate name.** `make harness-lint` and
  `scripts/harness_lint.py` mean **Claude**-harness constructs - the `Agent`
  tool, `AskUserQuestion`, `.claude/worktrees`, `CLAUDE.md` - that a generated
  skill carries over and that would break under Codex. This is the more visible
  of the two, because it is a `make verify` target contributors type, and it is
  the one most likely to be misread: "the harness lint" sounds like it lints
  *this* harness, and it does the opposite.

A sentence that could be read any of these ways must say which it means - "the
friction ledger's harness tag", "the `harness-lint` gate", or "the harness" -
rather than overload the word silently. Renaming a `make` target contributors
type is out of scope for a vocabulary document, and has no red case: no input
makes a rename report "this was a mistake".

## counter-model

**The model that did not implement the change under review.** Stated as a
property of the review, not as a tool name, so that whichever lane implemented -
Codex, Claude, Qwen, Gemma - the counter-model is whichever other one reviews,
and a new lane inherits the term without an edit here.

The test: *did this model write the diff it is reviewing?* If yes, it is the
implementer reviewing itself, whatever it is called. If no, it is the
counter-model. In this repository a Codex review of a Claude-written diff
(`/flow:auto_codex` Step 5) is the counter-model, and a Claude review of a
Codex-written diff is equally one.

Making the counter-model stage a routine stage rather than an escalation, and
giving it its own red case, is issue #241 (which adopts CPP ADR 0007 and takes
that number here), not this glossary.

## Surfaces that route here

- [ADR 0008](../decisions/0008-instrument-negative-control-bound.md) - the
  bound, the carve-out, the escalation, and the enumeration that tests them.
- The Negative Control section of the host's global directive
  (`~/.claude/CLAUDE.md`) carries the bound in the same words. It is
  host-managed and outside this repository.
