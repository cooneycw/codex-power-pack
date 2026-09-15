# ADR 1001: Retire one backport recipe, scope the other's review gate by operation

> **Why this file starts a new number range.** ADR 0008 established that CxPP
> mirrors CPP's ADR numbers so a cross-repo citation needs no repo prefix, and it
> pre-committed the signal that would move that scheme: *"CxPP authoring an
> original decision that has no CPP counterpart: mirrored numbering has no slot
> for it. The answer then is a separate CxPP-local range - not renumbering."*
> This is the first such decision. Both recipes it rules on exist only in CxPP's
> generator - CPP has nothing to vendor FROM, so it cannot have a counterpart -
> which means there is no CPP ADR to mirror and no CPP number to keep. The
> CxPP-local range therefore opens at **1001**, chosen to sit far above any
> plausible CPP number so the two can never collide and a reader can tell at a
> glance which repository authored a decision. Mirrored decisions keep using
> CPP's numbers in the 0001-0999 range; nothing is renumbered.

- Status: Accepted
- Date: 2026-09-15
- Issue: #251
- Supersedes: nothing
- Related: [ADR 0008](0008-instrument-negative-control-bound.md) (which names
  #251 as a live instance of its own adoption-drift residual, and whose
  numbering trigger this file is the first to fire), #254 (the pin bump this
  unblocks), #242 (the oscillation rule this decision records itself under),
  #257 (`make verify` cannot see a broken pin reproduction - found while
  measuring this change)

## The decision, in one line

Of CxPP's two byte-identity backport recipes, **#858's is deleted** because
nothing it produced reached the artifact, and **#856's identity table is kept but
scoped to publication**, because it was doing a second job nobody had named. The
class was enumerated and is closed at two.

## Decision 1: retire the #858 recipe

`_backport_flow_context`, the bounded CPP #858 backport recipe, is **deleted
outright**, along with the two source identities it recognised
(`_FLOW_CONTEXT_BEFORE`, `_FLOW_CONTEXT_AFTER`) and the delta it applied
(`_FLOW_CONTEXT_DELTA`). `_adapt_flow_context` becomes era-tolerant in its place.

The alternative the issue offered - review the third upstream state and re-record
its identity - is **rejected**. It buys one cycle. The recipe had already failed
against four distinct upstream tips (#451 98aa47a, #452 60f7242, #455 3d95fcd,
and a8a7402 measured while fixing this), each time for the same reason, and
re-recording an identity against a moving upstream re-arms the same failure for
the next commit that touches the file.

## Why deletion was available, and why that was not obvious

The recipe inserted two deltas. **Neither reached the published artifact.**

| delta | size | where it landed | what removed it |
|---|---|---|---|
| `[1]` | 3767 B | inside the region `_adapt_flow_context` replaces wholesale | `_adapt_flow_context` itself |
| `[0]` | 118 B | inside `## Capability contract (issue #783)` | `_adapt_deferred_native_boundaries`, which rewrites that section for the native surface |

delta[1] existed only to manufacture a start marker that the very next overlay
deleted. delta[0] is real text in CPP, but CxPP does not publish the capability
table it belongs to. Measured: applying both, one, or neither produces
byte-identical output, and a pre-#858 source and a post-#858 source converge on
the same published bytes.

That convergence is the property that made deletion safe rather than merely
tidy, so it is pinned by
`test_both_upstream_eras_generate_the_identical_artifact`. If a future overlay
stops replacing one of those regions, the two eras begin producing different
skills - the failure this recipe was nominally guarding against, then actually
detected.

## What is load-bearing, and the mistake that nearly shipped

The consumer overlay IS load-bearing, and it must serve both eras. The pinned
source `f64a654` predates #858 and carries no speckit-context block at all -
producing it was the recipe's entire job. **Retiring the recipe without an insert
branch breaks reproduction from the current pin**, and it was approved in that
form before anyone checked: the verification behind the approval had exercised
CPP `main`, which has the block, and not the pin, which does not. One of two
sources, called two-armed.

`_adapt_flow_context` now replaces the block where upstream ships it and inserts
the consumer at the same anchor where it does not - one branch, not a second
identity table.

The end marker `2. **Explore the codebase:**` is consequently the single point of
failure, and it says so: a bare `str.index` raised a `ValueError` naming neither
the file, the property, nor the remedy, and `main()` handles `IntegrityError`
only, so it escaped as an unhandled traceback rather than the module's own
diagnostic.

## Evidence

- **Controlling case.** `codex-skills-pin-check` against the **unchanged** pin:
  `ok`, exit 0, `ADOPTION_POLICY_SHA256 89b2006262367534c3a4bdcbef03915910899f381b2e220ef3839ab4d3268a72`
  - byte-identical to the pre-change control, so reproduction is preserved rather
  than merely passing. This is the arm whose absence let a broken retirement be
  approved, so it is the one that had to be committed.
- **Both verdicts committed**, and both are real upstream states rather than
  synthetic ones: `tests/fixtures/flow-context-source.json` `before` = `f64a654`
  = block genuinely absent = the insert path; `after` = `cb16600` = #858's
  closing commit = block present = the replace path.
- **Red run** against a true clone of the base at `4c629f0`: pristine 65 passed
  / 0 failed; with the new tests 4 failed / 64 passed.

## What would move this back (#242)

**Upstream removing or renaming the end marker.** The correct response then is to
**re-anchor the insertion point, not to widen the guard** - widening is what
turns a precise refusal into a check that cannot fail. A `git archive` extract
will not tell you this, because it has no `.git`; use a clone.

The wrong repair, explicitly: restoring a byte-exact identity table. That is the
defect being removed, and it would fail again on the next upstream commit.

## Decision 2: scope the #856 recipe's identity gate by operation

`_backport_github_issue_contract` has the identical two-identity shape and
blocked the same cron - it was **masked** by #858's recipe, which failed forty
lines earlier. The issue's "3 of 3 cron runs on **one** unowned cause" is
therefore wrong; there were two, in sequence.

It **cannot** be retired: measured by disabling the function itself, 1281 bytes
of its output reach the published artifact. The first measurement said "inert"
and was wrong, because `_adapted_source_payloads` calls the recipe internally, so
both arms of that comparison had it applied exactly once - a test supplying the
thing it was measuring.

The identity table here was doing **two jobs**, and only one of them is the
defect:

| job | what it does | disposition |
|---|---|---|
| transformation | two edits, both already anchored on TEXT, not on the identities | kept, made idempotent |
| review control | refuses an unreviewed upstream source **before** any CxPP transformation, so an altered source cannot launder itself into looking equivalent afterwards (#195/#204) | kept, scoped to publication |

Dropping both - the obvious reading of "retire the identity gate" - would have
removed the review control silently. Three committed tests are what caught it,
one of them saying so in its own name:
`test_issue_contract_unknown_source_fails_refresh_before_any_publication`.
**A test whose name states the property you are about to remove is a stop signal,
not an obstacle.** They keep their subject and assertions here; only the entry
point that exercises them changed.

So the gate is split by operation, because reporting and publication are
different acts that happened to share `_prepare_source_payloads`:

- **reporting READS** arbitrary upstream and publishes nothing -> no review gate.
  Blocking the drift report on an unreviewed source is what failed the cron every
  run while leaving the drift state *unknown rather than clean*.
- **refresh and pin-check PUBLISH** -> review gate unchanged.

The transformation is idempotent in both directions, so no era double-applies:
the #856 addition inserts only when absent (still absent upstream), the expanded
bullets replace the old pair only when present (upstream has adopted them).

## The class, and why it is closed

Enumerated by MECHANISM rather than by name, because a third instance need not be
called `_backport_anything`:

- whole-file identity comparison via `_github_contract_source_identity` - two
  call sites, both inside the one remaining recipe
- identity-tuple constants `(git blob sha1, sha256, length)` - exactly
  `_GITHUB_CONTRACT_BEFORE`/`_AFTER`, now that `_FLOW_CONTEXT_*` is gone

**The class is two, both known, one retired and one scoped.** Two near-members
are deliberately excluded:

- `_native_context_payload` pins sha256 + mode and raises on mismatch - same
  shape, but over a **CxPP-native** file, so a CPP pin bump cannot trip it.
- `ADOPTION_CHANGE_SET_SHA256`, `ADOPTION_DECISIONS_SHA256`,
  `ADOPTION_RETAINED_PAYLOADS_SHA256` pin CxPP's own
  `vendor/claude-power-pack/adoption-policy.json`, not CPP source.

That second group is **pin-conditional rather than pin-coupled**, which is a
different and more interesting property than the one being enumerated: a bump
does not break them, and `_validate_policy_source` raises at any ref other than
the recorded one, so refresh fails loudly rather than silently. The residual
there belongs to #254, not here: `ADOPTION_TARGET_COMMIT`, the policy file and
its tree hashes are coupled and must move together.

## Residual

`_backport_github_issue_contract`, the sibling CPP #856 recipe forty lines above,
has the **identical** two-identity defect and blocks the same cron run - it was
masked by this one. Unlike #858's it is genuinely load-bearing: 1281 bytes reach
the artifact. So it cannot be retired, though the same content-anchored remedy
applies, both its replacements already being text-anchored. The issue's "3 of 3
cron runs on **one** unowned cause" is therefore wrong: there were two, in
sequence.
