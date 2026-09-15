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

*(Two controls as of #246; this section describes the first. The second is in
the amendment at the end of this document.)*

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

| tier | gates | how a case is aimed |
|---|---|---|
| **direct** | `harness_lint.py`, `skill-eval.py deterministic` | a CLI flag - `--skills-root`, `--cases`. Only the gate is under test |
| **adapter-reachable** | `project_next_sync.py`, `codex_skills_sync.py --check`, `skill_contract_lint.py`, `skill_contract_baseline.py` | their roots are module constants, so a committed adapter can rebind them and be invoked as a subprocess through this register's configurable `invocation` |

**No gate here is unreachable.** Two earlier drafts of this table said otherwise
- first that only `harness_lint.py` could be controlled, then that three gates
were blocked pending a root argument. Both were wrong, and in the same way: they
read "has no CLI flag" as "cannot be aimed", which is a claim about an interface
standing in for a claim about the code.

**An adapter puts the adapter inside the control's trust boundary.** If it
rebinds the wrong constants the control certifies the adapter's idea of the gate
rather than the gate, and the specific failure is *partial* rebinding: miss one
and the gate reads a MIXED tree, half scratch and half real repo, producing a
confident verdict about a state that exists nowhere. It does not fail loudly.
That is why the tier is named separately rather than folded into direct.

### The adapter cost is the READ SET, and it is not visible in the definitions

The obvious way to size an adapter is to count the module constants derived from
`Path(__file__)`. **That measurement is wrong in both directions at once**, and
`project_next_sync.py` shows both errors in one file:

| constant | root-derived? | read by `check()`? |
|---|---|---|
| `REPO_ROOT`, `SOURCE_PACKAGE`, `SOURCE_ENTRY` | yes | yes |
| `PLUGIN_ROOT` | yes | **no** - 0 reads after definition; it exists only to derive the two below |
| `TARGET_PACKAGE`, `TARGET_ENTRY` | **no** - they descend from `PLUGIN_ROOT` | **yes** - 8 reads between them |

So a root-derived scan over-counts one constant that never needs rebinding and
misses two that absolutely do. An adapter author working from that scan would
believe they were complete and would have built exactly the mixed tree described
above.

The figure that matters for an ADAPTER is the **read set** - the constants the
code path actually consults - and it is obtainable only by tracing each path.
**This document deliberately publishes no per-gate read-set numbers**, because
none has been measured that way. An honest gap beats a fourth revision.

**The definition scan was not an inaccurate measurement; it was an accurate one
mislabelled.** Counting constants derived from `Path(__file__)` yields the
*derivation graph*, and the graph is precisely what the other remedy needs. For
`project_next_sync.py` every read-set member descends from `REPO_ROOT`
transitively - `TARGET_PACKAGE` and `TARGET_ENTRY` through `PLUGIN_ROOT` - so a
single `--root` threaded into the derivation makes all of them correct **by
construction**, and no one needs to know which the code reads. `PLUGIN_ROOT`
being an unread intermediate stops mattering: it is a node in the graph, and the
graph is what a flag walks.

So the two remedies need two different measurements, and conflating them is what
produced three wrong tables: **write an adapter** needs the read set; **add a
root flag** needs the derivation graph. #259 pursues the flag, because it
removes the partial-rebind class outright rather than documenting it. Whether
every gate's graph is fully rooted the way `project_next_sync.py`'s is remains
unchecked for the other three - a cheap definition-scan question, and one for
#259's implementation rather than this document.

**Two adapters are already demonstrated, and both are correct** - which is what
makes the tier credible rather than hopeful.
`tests/test_verify_gate_vacuity.py:202-206` rebinds exactly the five names
`check()` reads and skips `PLUGIN_ROOT`, the unread intermediate.
`tests/test_codex_skills_provenance.py` does the same for `codex_skills_sync.py`,
rebinding eight constants - `REPO_ROOT`, `SKILLS_ROOT`, `VENDOR_DIR`,
`MANIFEST_PATH`, `PIN_PATH`, `ADOPTION_POLICY_PATH`, `RETAIN_OVERLAY_ROOT`,
`PLUGINS_ROOT`. Both authors worked from the read set rather than from the
definitions.

So the honest statement is not "the bound is unachievable here". It is: two
gates are directly controllable today, four more are reachable through adapters
whose cost has not yet been measured correctly, and giving those four a root
argument would remove the hazard entirely. Only one control ships in this change
because the machinery had to exist first.

**A note on denominators, so this and #259 are not read as contradicting.** ADR
0008 counts **verdict contracts** - `skill_contract_lint.py` and
`skill_contract_baseline.py` are its rows 7 and 8, two scripts answering
different questions. #259 counts **`make verify` members**, where
`skill-contract-lint` is one target invoking both. Neither is wrong; only
silence about which is being counted would be.

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
- **The adapter read sets.** Sizing the four adapter-reachable gates means
  tracing which constants each code path consults. Not done here, and
  deliberately not guessed. Tracked separately as an interface issue (#259), not
  a residual of this one - a structural constraint on the whole negative-control
  programme does not belong inside a document about one register.
- **The controls that are now possible and not yet written.**
  `skill-eval.py deterministic` is directly controllable and unclaimed;
  `project_next_sync.py` is reachable through an adapter and its blindness is
  already measured by #245's battery. Neither is blocked on anything.
- *(resolved during this change - `make verify` now has a `negative-controls`
  member, so the register's verdict is consumed by the gate that lets work
  through. It is therefore itself an instrument under the bound, which is why
  `tests/test_negative_control_register.py` exists.)*


---

## Amendment (#246): a configuration gate, and the verdict for "did not run"

Two changes to the register, both forced by the same control: the secret gate.

### The gate population is `scripts/` plus the repository root

`discover()` read `scripts/` only. The gate #263 got wrong is `.gitleaks.toml`,
and it is not a script - it is the **config half of a binary-plus-config gate**,
with gitleaks itself working correctly throughout. So the register could not
control the one gate in this repository that had actually gone blind.

The population is now `scripts/` and the root, non-recursively. It is **chosen,
not swept**, and the reason is in this file: the literal `#: NEGATIVE-CONTROL:`
directive appears in this document and in the register's own docstring. A
register that scanned the whole tree would read its own prose as a registration
and then report the control it had invented as missing.
`test_registrations_are_not_swept_out_of_documentation` guards the next widening.

### UNAVAILABLE: a control that did not run is not a control that passed

`controls/secret-scan-rules/` needs gitleaks. No image in this pipeline has both
gitleaks and Python - the gitleaks image is Alpine with no interpreter, and
`validate` runs `uv` with no scanner - so the control reports UNAVAILABLE in
every automatic context, and would have been UNRESOLVED (a finding against the
control) or a crash without a verdict for it.

UNAVAILABLE is deliberately **not** a failure and **never** counts as proven:

- the proven total is now counted rather than derived by subtracting failures,
  because subtraction folded "did not run" into "passed";
- it prints on stderr, naming the control, ending "UNKNOWN on this host, not
  clean";
- a run in which **every** control was UNAVAILABLE exits 3 under the same
  refusal as a run that discovered no registrations at all. Both produce the
  same evidence - none - and only one of them used to say so.

`--strict` does not convert UNAVAILABLE into a failure. The register cannot know
whether a tool *ought* to be present, and reddening `make verify` on every
machine without gitleaks would make the honest verdict the one people delete.

### What shipped: `controls/secret-scan-rules/`

The anchor is a **config**, which is new here and follows from what broke. The
blind artifact was `.gitleaks.toml` at `efde91f` - the state the moment before
#263 - committed byte-for-byte and sha256-pinned. Measured, against
`zricethezav/gitleaks:v8.18.4`:

| run | result |
|---|---|
| gate on `cases/planted-secret` | exit 1, "leaks found: 1" - **BAD**, as required |
| gate on `cases/no-secret` | exit 0 - **GOOD**, as required |
| anchor on `cases/planted-secret` | exit 0, "no leaks found" - **missed it**, as required |
| anchor on `cases/no-secret` | exit 0 - agrees, so the demonstration is isolated |

The fixture holds a fabricated AWS key, and therefore needs the one allowlist
entry in `.gitleaks.toml` that hides a repository path. That is not the circular
exclusion #246 refuses: **a path entry is matched relative to the scan root**,
and the control scans each case *as* the root, so the fixture is hidden from the
repository scan and fully visible to the control that needs to see it.

### What this control does NOT establish, and what does

It establishes that the config yields a **ruleset**. It cannot establish that
the scan **sees the repository** - every case is scanned as its own root, so the
allowlist's path entries cannot apply, and a `tests/.*` exclusion that unscans a
live directory leaves this control green. That property belongs to two other
instruments, in two languages because no image has both:

- `.woodpecker.yml`'s **coverage probe** scans the repository with the production
  config plus one marker rule, and requires every committed marker to be
  reported. It is the real measurement and runs only in the gitleaks image.
- `tests/test_gitleaks_allowlist.py` re-derives the same property without
  gitleaks - no declared allowlist entry may match a marker path - and runs in
  `make verify` on every host.

### Two decisions the counter-model forced, worth keeping

**The coverage probe runs `--no-git` while the repository scan runs git mode.**
That looks like an inconsistency and is not: it is a PAIRING. The expected set
comes from `git grep` - the working tree - and git mode reports findings from
the commits that ADDED them. A pure `git mv` of a marker emits a patch with no
added lines, so the scan keeps reporting the old path while the expectation
moves to the new one, and a harmless rename reads exactly like an allowlist
exclusion. Measured on a full clone. Nothing is lost, because the property under
test is whether an allowlist PATH entry unscans a path, and path entries are
matched identically in both modes - `tests/.*` suppresses the same three markers
either way.

**`[allowlist] stopwords` can only be caught by pinning the config's shape.**
Measured on the pinned image with one two-credential fixture:

| config | reported |
|---|---|
| no stopwords | `aws-access-token`, `github-pat` |
| `stopwords = ["ghp_"]` | `aws-access-token` only |
| a config **extending** that one | `aws-access-token`, `github-pat` |

The third row is the point. Stopwords are **not inherited through `[extend]`**,
so the coverage probe - which extends the production config - would go on
reporting everything while production quietly stopped. A suppression surface the
behavioural instrument is structurally blind to leaves only one place to catch
it, which is why `tests/test_gitleaks_allowlist.py` pins the `[allowlist]` key
set rather than only its `paths` and `regexes`.
