# ADR 0008: What an instrument is, and when it needs a negative control

> **Why this directory starts at 0008.** CxPP mirrors claude-power-pack's ADR
> numbers so that "ADR 0008" names the same decision in both repositories. This
> is the first decision recorded here and it adopts CPP's 0008, so it keeps that
> number. 0001-0007 are not missing; they are CPP numbers CxPP has not adopted.
> The scheme and what would change it are recorded under "ADR numbering" below.

- Status: Accepted
- Date: 2026-09-15
- Issue: #240
- Adopts: claude-power-pack ADR 0008, as written at CPP commit
  `24da854007c01595c13b5bd8e6e866dec64af48d` (CPP #932 / PR #942, 2026-09-14)
- Supersedes: nothing
- Related: #244 (the executable negative-control machinery; blocked on this
  document for the word it scopes itself to), #241 (the counter-model stage,
  which adopts CPP ADR 0007 and takes that number here), #242 (the oscillation
  rule), #251 (a live instance of the adoption-drift residual recorded below),
  #245 (the vacuity audit whose measurements are this document's primary local
  evidence), [the glossary](../agents/glossary.md).

## TL;DR

**An instrument needs a committed negative control when its verdict is consumed
by a decision that will not independently re-derive the fact.** A unit test the
surrounding suite would catch does not; a gate that lets work through does; a
check whose green is read by another session or another repo always does.

Enumerated against **this** tree on 2026-09-15, the bound captures
**32 distinct verdict contracts** - order tens, not hundreds - which is below
the rejection threshold #240 set. CPP's own enumeration returned 61 against a
much larger tree; that number is not inherited here and no part of CPP's table
is copied. This document defines vocabulary and records a bound. It adds no
tier, no process and no checker.

## Context

CxPP had no home for a decision at all: no `docs/decisions/`, and no defined
sense of "instrument", "harness" or "counter-model" for issues and reviews to
use precisely. Meanwhile the host's global Negative Control directive applies to
every session working in this repo, and its unbounded reading - every test
function, every script, every CI step ships a committed control - is
unaffordable here for the same reason it was unaffordable in CPP. An
unaffordable rule is not debated; it is applied to whatever is in front of you
and skipped everywhere else, which produces precisely the population the rule
exists to prevent: some instruments with controls, some without, and no way to
tell which from the outside.

Issue #245 supplied the local evidence that this is not hypothetical. Two of the
five non-standard `make verify` sub-gates reported success having examined
nothing: `harness-lint` passed on an empty or missing skills root, and
`project-next-check` printed "runtime bundle is current" at exit 0 with no
source modules to compare. Both are gates that let work through, and nothing
downstream re-derived what they asserted. The 29 skill directories in
`LOCAL_SKILL_DIRS` are excluded from the generated manifest, so their content is
never hashed. Two other checks read those bytes, and neither covers the whole
surface: `skill_contract_lint.py` compares the source copy against the packaged
copy, so it reports a DIFFERENCE between two copies and stays green when a
regeneration writes the same content into both; and, via
`skill_contract_baseline.py`, it rejects unexplained references for the tokens
that extractor knows - `AskUserQuestion`, `/plugin` and `.claude/` paths - but
only for skills that are packaged. What is left to `harness-lint` alone is the
rest of its rule set on those skills: `Agent tool`, `Skill tool`, the `!`
command prefix and `CLAUDE.md`, plus every rule on a local skill that is not
packaged at all. That residue is an instrument whose verdict is consumed by a
decision that will not independently re-derive the fact, which is this bound's
definition exactly.

## Decision

### The bound

> An instrument needs a committed negative control when its verdict is consumed
> by a decision that will not independently re-derive the fact.

"Committed negative control" means a case checked into the repository - an input
and the verdict it must produce - that fails when the instrument stops
discriminating. "Will not independently re-derive" is the whole test: if the
consumer of a verdict re-establishes the fact itself before acting, that
instrument's green is not load-bearing. Re-deriving means establishing the
*same fact*; a later step that catches a different consequence of the same error
is a backstop, not a re-derivation, and does not exclude the earlier instrument.

### The carve-out

A unit test whose failure the surrounding suite would catch does not need a
committed control. Its green is not individually load-bearing; the suite's is.
Whether the suite as a whole discriminates is a mutation-testing question, and
answering it per test would spend the entire budget on the population least
likely to be blind. The suite is counted as ONE instrument below.

### The escalation

A check whose green is read by a **different session or a different repo** always
needs one, because the consumer cannot see the conditions that produced it. This
clause bites harder in CxPP than in CPP: this repository's skills are *generated
upstream*, and its drift, pin and currency checks are the only thing standing
between a CPP change and a silently divergent Codex payload. A wave orchestrator
reading a worker's verdict, or CI reading `codex-skills-check`, cannot tell a
green produced by a working instrument from one produced by a blind one.

### What this does not change

- **The regression-test rule is untouched.** "A regression test must FAIL on the
  code before the fix" costs one run on the pre-fix tree, not a committed case.
- **"Outside the bound" does not mean "may be blind".** It means the proof that
  it is not blind belongs to the suite, not to a per-instrument case.
- **Nothing is renamed.** See the `harness` note in
  [the glossary](../agents/glossary.md).

## ADR numbering

**CxPP mirrors CPP's ADR numbers.** A decision adopted from CPP keeps the number
it has there, so a cross-repo citation needs no repo prefix to be unambiguous.
The cost is real and is accepted: this directory has gaps, it starts at 0008,
and a newcomer cannot read the numbering as a sequence. The header block at the
top of this file is the mitigation.

The alternative - numbering CxPP's own from 0001 - is cleaner locally and was
rejected because CxPP is a *derived* repository whose skills are generated from
CPP: the cross-repo citation is the common case here, not the exception. The
scheme pays off immediately at #241, which adopts CPP's counter-model ADR and
lands at 0007 in both repositories rather than 0002-here/0007-there.

**What would move this back, and what the wrong repair would be (#242).** The
signal is CxPP authoring an **original** decision that has no CPP counterpart:
mirrored numbering has no slot for it. The answer then is a separate CxPP-local
range - not renumbering. Renumbering would break every cross-repo citation the
scheme exists to enable, which is the property being bought; a session tidying
this directory into a contiguous sequence would be destroying the decision, not
maintaining it.

## The enumeration

### How the number was obtained, and what it cannot see

The universe is hardcoded so the enumeration cannot silently narrow itself:
`scripts/` (17 files), Makefile targets (24), CI steps in `.woodpecker.yml` (5),
the documented Codex hooks (3), and the `lib/` entry points. Members were then
derived **by hand**, applying the bound to each entry: *name the decision that
acts on its verdict, and say whether that decision re-derives the fact.* One row
per distinct verdict contract; wrappers of one verdict collapse to one row
(`make lint` and the CI `validate` step both run `ruff`), while two modes of one
script that answer different questions to different consumers are separate rows.
Classes: **G** = a gate that lets work through a lifecycle path; **X** = its
green is read by another session or another repo.

**A scripted cross-check was run and is NOT the source of this number.** It keys
on *printed* verdict markers, so it is structurally blind to instruments that
signal only by exit code. That blindness is confirmed, not suspected:
`flow-worktree-guard.sh` exits 0 with no output at all on the clean path and
carries two executable `exit 3` sites the flow spec treats as a STOP, and the
scripted pass did not see it. (An earlier draft said five. That number came from
`grep -c 'exit 3'` without printing the lines: three of the five matches are
comments. A second reader reached five independently by the same method, which
looked like confirmation and was not - agreement between two runs of the same
broken extractor is one measurement, not two.) It is row 24 below, admitted by the manual pass. So are
`worktree-remove.sh` and `hook-validate-command.sh`, which print prose but
carry their verdict in the exit status rather than in any parseable marker -
which is what the scripted pass keys on.

The manual pass can miss too, and did: the counter-model review of this very
document moved the number twice - up by eleven omitted contracts, then down by
two that turned out to have no consumer. Both are recorded in "What the count
says" below. The count should be read as an enumeration rather than a census.
**The verdict is robust to that, and that robustness has now been tested rather
than asserted.** #240's rejection threshold is hundreds versus tens; the number
moved from ~20 to 34 to 32 under review and never left tens. Doubling 32
outright to cover a further under-count lands at 64 - the same order as CPP's
61, against a tree with a quarter of CPP's scripts. The bound would have to be
wrong by an order of magnitude, not by a dozen rows, for this conclusion to
change.

### Captured

| # | instrument | verdict | consumed by, without re-derivation | class |
|---|---|---|---|---|
| 1 | `make verify` as an aggregate | the AND of its eight prerequisites | the operator, under the AGENTS.md directive "after code changes, run `make verify`"; its own failure mode is a sub-gate dropped from the list, which no member row can see | G |
| 2 | `ruff` via `make lint` / CI `validate` | exit code | `make verify`; CI | G |
| 3 | the test suite, as one instrument (`pytest` via `make test` / CI) | exit code, and the zero-collected case | `make verify`; CI | G |
| 4 | `mypy` via `make typecheck` | exit code | `make verify` | G |
| 5 | `codex_skills_sync.py --check` (`make codex-skills-check`) | `DRIFT` / `MISSING` / `STALE` | `make verify`; CI `validate`; the gate on hand-edits to generated skills, against the pinned manifest - which excludes the 29 `LOCAL_SKILL_DIRS` | G, X |
| 6 | `harness_lint.py --check` (`make harness-lint`) | unadapted Claude-only constructs, or a pass | `make verify`; for the 29 `LOCAL_SKILL_DIRS` skills, whose content the generated manifest never hashes, the only gate covering `Agent tool`, `Skill tool`, the `!` prefix and `CLAUDE.md` - row 8 catches the tokens its extractor knows, and only on packaged skills (#245) | G |
| 7 | `skill_contract_baseline.py --check` | inventory reconciliation verdict | `make verify` via `make skill-contract-lint` | G |
| 8 | `skill_contract_lint.py --check` | semantic-incompatibility verdict | `make verify` via `make skill-contract-lint` | G |
| 9 | `project_next_sync.py --check` (`make project-next-check`) | mirrored runtime bundle current / drifted | `make verify` | G |
| 10 | `skill-eval.py deterministic` (`make skill-eval-check`) | deterministic activation/procedure/output verdict | `make verify` | G |
| 11 | `codex_skills_sync.py --pin-check` | payload reproduces from the exact clean source in `PIN` | CI `codex-skills-pin-integrity` | G, X |
| 12 | `codex_skills_sync.py --source-check` (`make codex-skills-currency-check`) | adopted payload vs a current CPP checkout | the refresh decision | G, X |
| 13 | `codex_skills_sync.py --source-report` | canonical JSON + digest for one validated immutable CPP ref; complete drift is *successful reporting*, resolution/provenance/adaptation failures are errors | the revendor decision; CI cron / manual. Live instance: #251 | G, X |
| 14 | `gitleaks` with `.gitleaks.toml` | findings or none | CI `secret-scan` and `make secret-scan`, which run the identical history-scanning invocation; they can differ only by checkout history, not by design | G |
| 15 | `dep-audit` (`pip-audit` + `bandit`) | findings by severity | CI `dependency-audit` | G |
| 16 | `release_validate.py` (`make release-validate`) | plugin install/list, upgrade and rollback transitions between two supplied refs, under a temporary `CODEX_HOME` | whether a release ships (`docs/release-process.md`). It does NOT establish that the supplied refs are immutable, nor run a skill in a clean project; those release requirements are documented, not measured here | G, X |
| 17 | `worktree-remove.sh`, as generated into the flow skills | exit 4 refuses a checkout another live session claims (#597); every other refusal is exit 1. It has no distinct occupancy or unpushed-commit code | whether a checkout is destroyed; invoked from `flow-auto` / `flow-merge` / `flow-start` / `flow-doctor`, routinely in another session. Eight byte-identical generated copies (md5 `de48c234`), collapsed to one contract; #253 removed the unguarded `scripts/` orphan | X |
| 18 | `hook-validate-command.sh` | non-zero blocks the command | whether a dangerous Bash command runs at all | G |
| 19 | `project-next.py` + `lib/project_next/` | startable / safe classification | `project-next`, whose contract declares the deterministic output authoritative and forbids rebuilding the decision in a prompt | G, X |
| 20 | `native-wave-delivery.py permit` / `pending` | delivery permitted; what is outstanding | a different session acting on whether a message was received - the docstring's own point, that detached notify cannot confirm receipt | X |
| 21 | `skill-eval.py live --allow-live` | bounded-live activation verdict | the release/cadence policy in `docs/skill-evaluation.md`; a different question from row 10, against a different population | G |
| 22 | `cxpp-hook-transition.py` | which already-reviewed hook roots stay usable across a plugin upgrade or rollback | whether a reviewed hook root survives the transition | G |
| 23 | `cxpp-influence.py status` | whether the optional AGENTS.md routing block is present and current | the apply / remove / decline decision | G |
| 24 | `flow-worktree-guard.sh --strict`, as generated into the flow skills | exit 3 on a leak; silent, with no output at all, on the clean path | the Step-4 first edit and the Step-6 commit in `flow-auto` / `flow-auto_codex` / `flow-start`, routinely driven by another session | G, X |
| 25 | `bash-prep.sh --check` | threshold judgments, not raw values - "All values are optimal. No changes needed." | whether an operator applies the tuning. The judgment is what is acted on; reading it is not re-measuring the system | G |
| 26 | `lib.security scan` / `quick` / `deep` | findings by severity | `/security:*` in any repo that installs CxPP | X |
| 27 | `lib.security gate` | two policies (`lib/security/config.py`): `flow_finish` blocks CRITICAL and warns HIGH; `flow_deploy` blocks CRITICAL and HIGH | the finish and deploy paths in any repo; a control has to cover the HIGH case that passes finish and blocks deploy | G, X |
| 28 | `lib.cicd run` / `resume` | the quality-gate verdict | the commit, push and PR in any repo whose flow skills select the CxPP runner | G, X |
| 29 | `lib.cicd check` | Makefile-standards verdict | `/cicd:check` in any repo | X |
| 30 | `lib.cicd detect` | framework and package-manager classification | `/cicd:init` selects the Makefile template from it | X |
| 31 | `lib.cicd health` | probe verdicts | `/cicd:health` in any repo | X |
| 32 | `lib.cicd smoke` | smoke verdicts | `/cicd:smoke` in any repo | X |

### Excluded, with the reason

| population | reason under the bound |
|---|---|
| the individual test functions | the carve-out: the suite catches an individual test's failure; the suite is row 3 |
| `codex-friction-hook.py` and `lib/friction` | a recorder, and deliberately fail-open telemetry; nothing decides on a friction event without reading it |
| `hook-mask-output.sh`, `secrets-mask.sh` | filters, not verdicts; nobody is entitled to rely on masking as a permission to read credentials |
| `prompt-context.sh` | renders a shell prompt string; no decision consumes it |
| `lib.creds` (9 subcommands) | `get`, `set`, `delete`, `list`, `rotate`, `run` and the UI are actions, not verdicts. `validate` reports a credential usable and the use that follows re-derives it loudly - the one entry excluded by the re-derivation clause rather than by kind |
| `lib.cicd status`, `container`, `pipeline`, `infra-init`, `infra-discover`, `infra-pipeline`, `init-manifest`; `lib.security explain` | recorders, generators and explainers; their output is a file or a narrative the caller reviews, not a verdict something acts on |
| `lib.cicd validate`, `validate-manifest` | real CLI entry points with **no evidenced consumer in this tree**: no skill procedure invokes either. The bound asks for a decision that acts on a verdict, and command existence is capability, not consumption. They become rows the day something calls them |
| `codex_skills_sync.py --write` / `--refresh`, `project_next_sync.py --write`, `skill_contract_baseline.py` in write mode, `cxpp-influence.py preview\|apply\|remove\|decline`, `native-wave-delivery.py journal-create` and the ledger writes | generators, renderers and ledger operations; the state they produce is re-derived by rows 5, 9, 11, 12 and 23 |
| `make format`, `build`, `clean`, `help`, `update_docs`, `codex-skills`, `codex-skills-refresh`, `project-next-sync` | actions and informative no-ops |

### What the count says

32 verdict contracts. That is "tens" by #240's own threshold, so the bound is
not falsified by this tree and stands. Three things it does **not** say, stated
so they are not inferred:

- **It is a count of rows, not a measure of effort.** What it costs to write,
  keep and re-confirm 32 controls is unmeasured here.
- **It does not say how many have a control today.** #244's register is the
  living list and owns that denominator; this table is a dated snapshot and is
  not maintained here. A new instrument is added *there*, next to its control.
- **It corrects the "~20" reported at #240's approval gate, in both
  directions.** A closer manual pass admitted rows 20-23 (`skill-contract-lint`
  is two distinct scripts, not one). The counter-model review then found a whole
  declared population enumerated nowhere - this document named `lib/` in its
  universe and listed none of its entry points - plus `flow-worktree-guard.sh`,
  which appears above as the proof that the scripted pass is blind and was then
  left uncaptured; those became rows 24-32. A second counter-model pass removed
  two of them again, `lib.cicd validate` and `validate-manifest`, for having no
  consumer in this tree. The verdict is unchanged, which is the point of having
  stated the threshold in orders of magnitude.

The escalation clause carries more weight here than the row count suggests:
**16 of the 32 are class X**. Four of them (rows 5, 11, 12, 13) exist solely
because this repository's skills are generated somewhere else. Seven more (rows
26-32) are library entry points other repositories consume; five of those seven
are captured by the escalation clause alone, while rows 27 and 28 are class G as
well and would be captured without it. CxPP cannot see another repo's run, so
that repo cannot see whether CxPP's verdict was blind.

## Residual: this document can drift from CPP's

Adopting by copying creates two texts that can diverge. If CPP amends its ADR
0008, this file goes stale silently and a reader has no way to tell. That is the
same defect class as #251, which is red on `main` right now because an upstream
source moved to a state its recorded identities did not anticipate - a named,
live instance rather than an argument that it could happen.

**This document arrived carrying that defect, and it was measured rather than
predicted.** The counter-model review of this change (Codex, `/flow:auto_codex`
Step 5) found two claims copied from CPP's ADR that are false of this tree:
row 17's refusal codes were CPP's `worktree-remove.sh` exit set (4/5/6/7), where
the copy generated into CxPP's flow skills has only exit 4 and exit 1; and row
14 asserted that CI and `make secret-scan` scan different input populations,
which holds in CPP - whose `make` target passes `--no-git` - and not here, where
both run the identical command. Neither was caught by adopting carefully. Both
were caught by a model that went and read this tree.

The mitigation taken here is the cheapest one that makes staleness
**human-checkable**: the header cites CPP's originating commit SHA, so anyone
can diff this text against that exact upstream revision. The mitigation NOT
taken is a checker, deliberately: that is #244's scope, and #240 explicitly
forbids adding a governance layer. **The drift is declared as a residual against
#244.**

## Consequences

- `instrument`, `harness` and `counter-model` are defined terms
  ([glossary](../agents/glossary.md)); issues and reviews use them rather than
  "gate", "check" or "the tooling" when the distinction matters.
- #244 can scope itself: "every instrument the bound captures" replaces an
  ad-hoc list, with a denominator of 32 to start from.
- Adding an instrument the bound captures means adding its committed control in
  the same change. Adding a unit test does not.
- No new check enforces this document, by design.

## What this does not solve

- **It registers no control.** 32 instruments are named; how many have one today
  is #244's measurement, not this document's.
- **It does not make the suite discriminate.** The carve-out moves that question
  to mutation testing and answers nothing about it.
- **It does not close #245's declared residual**: the 29 `LOCAL_SKILL_DIRS`
  skills remain outside the generated manifest, leaving part of row 6's rule set
  uncovered by anything else. That stays deferred and is not folded in here.
