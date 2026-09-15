# ADR 1002: The negative-control register is written natively, not vendored

> **Why this number.** 1002 is in CxPP's **local** ADR range, not a mirror of a
> CPP number. [ADR 0008](0008-instrument-negative-control-bound.md) fixes the
> rule: a decision adopted from CPP keeps CPP's number, a decision original to
> CxPP takes 1001 and up. This one is original - CPP cannot hold a counterpart,
> because the decision is *whether to vendor from CPP*, and CPP has nothing to
> vendor from. Verified before choosing: CPP `main`'s `docs/decisions/` is
> 0001-0006 and 0008, with no register ADR at any number.

- Status: Accepted
- Date: 2026-09-15
- Issue: #244
- Related: #240 / [ADR 0008](0008-instrument-negative-control-bound.md) (the
  bound this machinery checks compliance with), #242 (the oscillation rule),
  #245 (which produced the anchor this register runs against),
  claude-power-pack#924 (the design adopted here),
  claude-power-pack#964 (why the register's own control is a test suite),
  claude-power-pack#986 (the discovery defect this implementation does not
  inherit, filed from this work)

## TL;DR

The register's **scoring logic is written natively in CxPP**, not vendored from
claude-power-pack. The issue recommended vendoring; that recommendation rested
on a premise this work measured and found false. The **controls are native**
too, which was never in doubt - they are cases about CxPP's own gates.

One control ships: `harness-lint`'s vacuity property, anchored on the real
pre-#245 script. That is not a coverage map, and this document says why it
cannot yet be one.

## Context

ADR 0008 says a load-bearing instrument must ship a committed input that makes
it report the other verdict. Nothing in this repository could check that. `scripts/`
carried **zero** `check-*` gates and there was no `controls/` tree.

The gap is not theoretical, and #244's evidence for it is a near-miss rather
than an accident: the first hand-built red case for `harness-lint` contained
`SendMessage`, `~/.claude/scripts/` and `/flow:auto`. It **passed**, and a
working gate was nearly reported as blind. None of those three is one of the
gate's seven rules. Without a committed control, every future reader re-derives
the red case by hand and can get it wrong **in either direction**.

## Decision 1: native, not vendored

**The issue's recommendation was rejected on a measured premise.** It reads:
"vendor the register (the scoring logic is generic and stays in sync through
the existing pin/refresh bridge)". There is no such bridge for this file:

```
scripts/codex_skills_sync.py:87   PIN_PULL_SOURCE      = "codex/skills/"
scripts/codex_skills_sync.py:88   PIN_PULL_DESTINATION = ".codex/skills/"
```

The pull is refused unless it is exactly that mapping. `vendor/claude-power-pack/`
holds a `PIN`, an adoption policy, a skills manifest and skill overlays - and
nothing for `scripts/`. Vendoring the register would mean **building a second
sync path by hand**, which is the drift that vendoring exists to prevent.
Recorded explicitly so the recommendation is not re-adopted later from the issue
text: it was not declined on taste.

**What would move this back (#242).** Not "CPP changed the file" - that is
expected and harmless while the two agree. The observation that would move this
back is **the two registers returning different verdicts for the same control
manifest**. That is measurable, and it is the actual cost of divergence. If it
happens, the repair is to reconcile the scoring rules, and only then to ask
whether a shared artifact is worth a purpose-built bridge.

**The split paid off on day one.** CPP's `discover()` compiles its registration
pattern with `re.MULTILINE` - anticipating several registrations per file - and
then calls `.search`, taking the first (claude-power-pack#986, filed from this
work). Because `.search` takes the first match in **file order**, moving two
comment lines changes what a gate is certified against, with no diff to any
control and no change to the tool's output. CxPP uses `finditer`. Had the
register been vendored, that defect would have arrived with it and the local fix
would have been a hand-edit to a vendored file - a behavioural fork, which is
exactly #242's tell.

## Decision 2: the register's own control is a test suite

`check-negative-controls.py` is itself an instrument under the bound. Its
control is `tests/test_negative_control_register.py`, not a `controls/` entry -
a control directory whose gate is the register would have the register scoring
its own scoring.

**CPP's answer is both, and that difference is recorded rather than smoothed
over.** At CPP `459f3c2` there is a `controls/check-negative-controls/` entry
*as well as* `tests/test_negative_controls.py`, and its manifest carries a
`limits` field saying the self-registered row "CANNOT detect a breakage in the
harness's own verdict assignment: a harness mutated to emit PASS unconditionally
reports PASS about itself", naming the test suite as what does. So both repos
agree on the load-bearing half - the suite - and CPP additionally ships a
declared-weaker demonstration. CxPP ships only the suite for now. Checked
against CPP's tree rather than inferred from CPP#964, which predates that entry:
when this document was drafted, #964 was the whole of CPP's position, and it had
moved by the time the document was reviewed.

**Its failure modes are symmetric, and both are covered:**

| direction | the mistake | verdict required |
|---|---|---|
| calls a WORKING gate blind | the bad case never exercised the rule | `UNRESOLVED`, naming both readings |
| calls a BLIND gate proven | the anchor also catches the bad case, so the case does not test the fix | `INERT` |

The first is the harder one and is the reason this suite exists. "The gate is
blind to this input" and "this input never exercised the rule" **produce the
same bytes** - the gate says GOOD either way. The register is not entitled to
pick a culprit from that, so it consults the anchor and, when the anchor agrees,
declines to accuse the gate.

**Measured, not asserted.** With that branch removed, the suite goes red:

```
FAILED test_inadequate_bad_case_is_not_blamed_on_the_gate
FAILED test_gate_that_reports_less_than_its_anchor_is_blind
2 failed, 16 passed
```

Two cases, not one, and the second is the more interesting: the pre-fix register
*did* return BLIND for a genuine regression, so its verdict was right - but it
reached it without consulting the anchor, and returned the identical verdict for
an unexercised case. Same output, two different situations.

### The schema converged independently, which makes the trigger checkable

CxPP's manifest format was designed here, from the bound, without sight of CPP's
second control. CPP then shipped `controls/shellcheck-gate/control.json` at
`459f3c2` with the same shape: `gate`, `invocation`, `good_exit`,
`detect_signal`, `cases[{name, input, expect}]`,
`anchors[{kind, sha, origin, path, sha256}]`. Verified field-by-field against
that file.

Independent convergence is worth more than agreement, because neither side could
have copied. It also turns the oscillation trigger above from a hypothetical into
something testable: there is now a real CPP manifest to run through this register
and compare verdicts against. Two known divergences to test first - CxPP adds
`property` and `why` as documentation fields, and CPP added `limits` - the best
idea of the three, and **adopted here** from CPP `459f3c2` rather than merely
admired. The register prints it beside the verdict, so a PASS can never be read
as wider than the control's own author claimed. The shipped control uses it to
say that it proves one rule of seven.

## What shipped, and what the coverage actually is

One control: `controls/harness-lint-vacuity/`, for the property "an empty or
missing skills root must not report success". Its anchor is the real pre-#245
`harness_lint.py` at `0f0491d`, sha256-pinned, and its blindness is measured on
every run rather than asserted here:

| run | result |
|---|---|
| gate on `cases/vacuous-root` | exit 3, "refusing a vacuous pass" - **BAD**, as required |
| gate on `cases/populated-root` | exit 0, "1 markdown file(s) passed" - **GOOD**, as required |
| anchor on `cases/vacuous-root` | exit 0, "0 markdown file(s) passed" - **missed it**, as required |
| anchor on `cases/populated-root` | exit 0 - agrees, so the demonstration is isolated |

### Why only one ships, and what it would take to have more

Controllability is **three-tiered**, not binary. An earlier draft of this
document said only `harness_lint.py` could be aimed at a fixture and concluded
that everything else was blocked on source changes. That was wrong twice, and
the counter-model review caught both: it omitted `skill-eval.py` from its own
table, and it treated "no CLI flag" as "cannot be controlled".

| gate | how a case can be aimed at it |
|---|---|
| `harness_lint.py` | **directly** - `--skills-root` |
| `skill-eval.py deterministic` | **directly** - `--cases` takes a fixture suite |
| `project_next_sync.py` | **through a committed adapter**. It has only `--check` / `--write`, but its roots are module constants, and `tests/test_verify_gate_vacuity.py` already rebinds `REPO_ROOT` and `SOURCE_PACKAGE` at a scratch tree. A small committed adapter can do the same and be invoked as a subprocess through this register's configurable `invocation` |
| `codex_skills_sync.py --check` | **not yet** - `--cpp-root` steers the *comparison source*, not the tree under test |
| `skill_contract_lint.py`, `skill_contract_baseline.py` | **not yet** - `--check` / `--json` / `--write` only, roots from `Path(__file__).resolve().parent.parent` |

The tiers matter because they have different costs and different honesty. A
direct flag puts only the gate under test. **An adapter puts the adapter under
test too** - if the adapter rebinds the wrong constant, the control certifies
the adapter's idea of the gate rather than the gate. That is a real cost and the
reason an adapter is not simply the answer everywhere; it is still far cheaper
than changing five gates' interfaces, and it is available today.

So the honest statement is not "the bound is unachievable here". It is: two
gates are directly controllable, one more is reachable through an adapter, and
the remaining ones need a root argument in their own source - which is a change
to those gates, outside this issue's lane. Only one control ships in this change
because the machinery had to exist first; the ceiling is lower than #244's "one
per load-bearing instrument" but it is not one.

### This register is not a coverage map

A registered control proves **one property of one gate**. `harness-lint` refuses
a vacuous pass *and* reports unadapted constructs; this control covers the
first. The second cannot reuse the same anchor - measured: the `0f0491d` script
**catches** an `Agent tool` construct (exit 1, identical to the current gate)
while **missing** the vacuous root - and the anchor must miss every bad case in
its control. A second property needs a second control with its own anchor, which
is why one gate may register several.

Read `--list` as "what has been proven", never as "what is covered". ADR 0008's
32-row enumeration is the population; this register's one row is the progress
against it. Stating the denominator matters: claude-power-pack#964's argument is
that the register *is* the coverage map, and a register that silently proves one
property per gate reads wider than it measures.

## Consequences

- A gate registers its control in its own source (`#: NEGATIVE-CONTROL: <dir>`),
  so the registration sits next to the thing it describes.
- The register refuses a vacuous pass of its own: a run that discovered no
  registration exits 3 rather than reporting success. It enforces ADR 0008's
  bound, so it does not get to be the one instrument exempt from it.
- A crash is not a detection. A BAD verdict requires the gate's own reporting
  language (`detect_signal`), not merely a non-zero exit.
- Adding a fixture-controllable gate means adding its control in the same change.

## What this does not solve

- **Coverage.** One of 32 enumerated contracts has a committed control. The
  binding constraint is gate interfaces, not effort.
- **The gates that cannot be aimed.** `codex_skills_sync.py --check`,
  `skill_contract_lint.py` and `skill_contract_baseline.py` each need a root
  argument in their own source. Tracked separately as an interface issue, not a
  residual of this one - a structural ceiling on the whole negative-control
  programme does not belong inside a document about one register.
- **The controls that are now possible and not yet written.**
  `skill-eval.py deterministic` is directly controllable and unclaimed;
  `project_next_sync.py` is reachable through an adapter and its blindness is
  already measured by #245's battery. Neither is blocked on anything.
- **`make verify` wiring.** The register is not yet a `make` target - `Makefile`
  was held by another worker for #251 during this work. Until it is wired, the
  register is a command someone runs, not a gate that runs itself, and its
  verdict is not consumed by anything. That is the remaining half of #244's
  outcome.
