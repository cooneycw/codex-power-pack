"""The negative-control register's own negative control (issue #244).

`scripts/check-negative-controls.py` is an instrument under ADR 0008's bound: it
is a gate that lets work through, and nothing downstream re-derives its verdict.
So it needs a committed input that makes it report the other verdict - and by
the rule it enforces, it does not get to be the one instrument exempt from it.

claude-power-pack settled the shape for this in CPP #964: the register's control
is a TEST SUITE rather than a `controls/` entry, because a control directory
whose gate is the register itself is circular - the register would be scoring
its own scoring. This file is that suite.

---------------------------------------------------------------------------
THE PROPERTY THAT MATTERS MOST, AND WHY IT IS SYMMETRIC
---------------------------------------------------------------------------
The register can be wrong in TWO directions, and #244's own evidence is the
first one:

  (1) It can call a WORKING gate BLIND, from a case that never exercised the
      rule. This is not hypothetical. The first hand-built red case for
      `harness-lint` contained `SendMessage`, `~/.claude/scripts/` and
      `/flow:auto` - none of which is one of its seven rules. It PASSED, and a
      working gate was nearly reported as blind.

  (2) It can call a BLIND gate PROVEN, from a case its anchor also catches -
      the case tests something the fix did not change, so it would pass against
      a gate that never had the fix. That is INERT.

Direction (1) is the harder one, because "the gate is blind to this input" and
"this input never exercised the rule" produce THE SAME BYTES: the gate says
GOOD either way. The register is not entitled to pick a culprit from that, so
it consults the anchor and, when the anchor agrees, reports UNRESOLVED naming
both readings rather than accusing the gate. `test_inadequate_bad_case_is_not
_blamed_on_the_gate` is that case, and it is the one this suite exists for.

RED RUN, measured rather than asserted. The two-readings branch was removed from
the register (restored afterwards from a byte-verified snapshot) and this suite
re-run on the pre-fix code:

    FAILED test_inadequate_bad_case_is_not_blamed_on_the_gate
    FAILED test_gate_that_reports_less_than_its_anchor_is_blind
    2 failed, 16 passed

TWO cases are red there, not one, and the second is the more interesting: the
pre-fix register did return BLIND for a genuine regression, so its VERDICT was
right - but it reached that verdict without ever consulting the anchor, so it
could not say why, and it returned the identical verdict for an unexercised
case. Same output, two different situations, which is this repository's whole
subject. Recorded because a test that has never been red is a claim about
intent, not about behaviour.

SECOND RED RUN, for the three cases added after the Codex review. The register
was reverted to its pre-review state (again from a byte-verified snapshot) and
this suite re-run:

    FAILED test_a_gate_that_consumes_its_fixture_cannot_certify_an_inert_control
    FAILED test_detect_signal_matching_empty_output_is_refused
    FAILED test_anchor_crash_is_not_reported_as_a_caught_regression
    3 failed, 14 passed

All three are genuine regression tests: each fails on the code that shipped
before its fix, and passes after.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "scripts" / "check-negative-controls.py"

#: A gate that reports when - and only when - the case directory contains a file
#: named `trigger`. Small enough to be obviously correct, which matters: a
#: subtle fixture gate would make a failure here ambiguous between the register
#: and the fixture.
GATE_SIGHTED = """#!/usr/bin/env python3
import sys
from pathlib import Path
case = Path(sys.argv[sys.argv.index("--case") + 1])
if (case / "trigger").exists():
    print("fakegate: found something")
    sys.exit(1)
print("fakegate: clean")
sys.exit(0)
"""

#: The same gate before its fix: it never reports anything. This is the blind
#: artifact an anchor is supposed to be.
GATE_BLIND = """#!/usr/bin/env python3
import sys
print("fakegate: clean")
sys.exit(0)
"""

#: Exits non-zero WITHOUT any reporting language. A crash, not a detection.
GATE_CRASHER = """#!/usr/bin/env python3
import sys
print("Traceback (most recent call last):", file=sys.stderr)
sys.exit(1)
"""

#: Reports the trigger and then CONSUMES it. A formatter, a --fix mode or a
#: sweep behaves like this. If gate and anchor share one fixture, whoever runs
#: second sees a clean tree.
GATE_CONSUMING = """#!/usr/bin/env python3
import sys
from pathlib import Path
case = Path(sys.argv[sys.argv.index("--case") + 1])
trigger = case / "trigger"
if trigger.exists():
    trigger.unlink()
    print("fakegate: found something")
    sys.exit(1)
print("fakegate: clean")
sys.exit(0)
"""

#: Always reports, whatever it is given. The good case is what catches this.
GATE_WEDGED = """#!/usr/bin/env python3
print("fakegate: found something")
raise SystemExit(1)
"""


def _load_register():
    spec = importlib.util.spec_from_file_location("check_negative_controls", REGISTER)
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: the module defines dataclasses, which resolve
    # `cls.__module__` through sys.modules while the class body executes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build(
    tmp_path: Path,
    *,
    gate_src: str = GATE_SIGHTED,
    anchor_src: str = GATE_BLIND,
    bad_has_trigger: bool = True,
    include_good_case: bool = True,
    include_anchor: bool = True,
    anchor_sha_override: str | None = None,
    detect_signal: str = "^fakegate: found something",
) -> Path:
    """Lay out a repo-shaped tree: scripts/<gate> registering controls/<control>."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    gate = tmp_path / "scripts" / "fakegate.py"
    gate.write_text("#: NEGATIVE-CONTROL: fake-control\n" + gate_src)

    control = tmp_path / "controls" / "fake-control"
    (control / "cases" / "bad").mkdir(parents=True)
    (control / "cases" / "good").mkdir(parents=True)
    (control / "anchors").mkdir(parents=True)
    if bad_has_trigger:
        (control / "cases" / "bad" / "trigger").write_text("x")

    anchor_path = control / "anchors" / "blind.py"
    anchor_path.write_text(anchor_src)
    digest = anchor_sha_override or sha256(anchor_path.read_bytes()).hexdigest()

    cases = [{"name": "bad", "input": "cases/bad", "expect": "BAD"}]
    if include_good_case:
        cases.append({"name": "good", "input": "cases/good", "expect": "GOOD"})

    manifest = {
        "gate": "scripts/fakegate.py",
        "invocation": ["python3", "{gate}", "--case", "{case}"],
        "good_exit": 0,
        "detect_signal": detect_signal,
        "cases": cases,
    }
    if include_anchor:
        manifest["anchors"] = [
            {"kind": "historical", "sha": "deadbee", "path": "anchors/blind.py", "sha256": digest}
        ]
    (control / "control.json").write_text(json.dumps(manifest))
    return tmp_path


def _verdict(tmp_path: Path) -> tuple[str, list[str]]:
    mod = _load_register()
    gate = tmp_path / "scripts" / "fakegate.py"
    res = mod.evaluate(tmp_path / "controls" / "fake-control", gate, tmp_path)
    return res.verdict, res.details


# --------------------------------------------------------------------------- #
# The shipped control: a positive control for this whole suite.
# --------------------------------------------------------------------------- #


def test_the_real_shipped_control_passes():
    """The committed harness-lint control discriminates and is proven able to fail.

    A positive control for the register: if this goes red, every other case
    below is measuring a broken tool rather than the property it names.
    """
    proc = subprocess.run(
        [sys.executable, str(REGISTER), "--root", str(REPO_ROOT), "--strict"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "harness-lint-vacuity" in proc.stdout
    assert "1/1 control(s) discriminate" in proc.stdout


# --------------------------------------------------------------------------- #
# Direction 1: never blame a working gate for an inadequate case.
# --------------------------------------------------------------------------- #


def test_inadequate_bad_case_is_not_blamed_on_the_gate(tmp_path):
    """A bad case that never exercises the rule must NOT read as a blind gate.

    This is the #244 near-miss, mechanised. The gate here is provably sighted -
    `test_sighted_gate_still_reports_a_real_trigger` runs the same gate against a
    real trigger and gets a detection - so a BLIND verdict would be an accusation
    against a working instrument.

    FAILED on the register as first written, which returned BLIND here.
    """
    tree = _build(tmp_path, bad_has_trigger=False)
    verdict, details = _verdict(tree)
    assert verdict == "UNRESOLVED", f"got {verdict}: {details}"
    blob = " ".join(details)
    assert "cannot tell them apart" in blob
    # It must name BOTH readings, not just decline to pick. A verdict that says
    # "inconclusive" without saying inconclusive between WHAT sends the reader
    # back to re-derive the two possibilities by hand.
    assert "the gate is blind" in blob
    assert "never exercised the rule" in blob


def test_sighted_gate_still_reports_a_real_trigger(tmp_path):
    """The gate used above is not broken - it detects when genuinely triggered.

    Without this, the previous test's UNRESOLVED would be consistent with a gate
    that can never report anything, and would prove nothing about the register.
    """
    tree = _build(tmp_path, bad_has_trigger=True)
    verdict, details = _verdict(tree)
    assert verdict == "PASS", f"got {verdict}: {details}"


def test_gate_that_reports_less_than_its_anchor_is_blind(tmp_path):
    """Gate misses what the OLD version caught: a regression, and BLIND is right.

    This is the other half of direction 1. The two-readings branch must not
    swallow a genuine blindness finding - when the anchor CATCHES what the gate
    misses, there is no ambiguity left to be careful about.
    """
    tree = _build(tmp_path, gate_src=GATE_BLIND, anchor_src=GATE_SIGHTED)
    verdict, details = _verdict(tree)
    assert verdict == "BLIND", f"got {verdict}: {details}"
    assert "regression" in " ".join(details)


# --------------------------------------------------------------------------- #
# Direction 2: never call a control proven when it proves nothing.
# --------------------------------------------------------------------------- #


def test_anchor_that_catches_the_bad_case_is_inert(tmp_path):
    """If the blind artifact also catches it, the case does not test the fix."""
    tree = _build(tmp_path, anchor_src=GATE_SIGHTED)
    verdict, details = _verdict(tree)
    assert verdict == "INERT", f"got {verdict}: {details}"
    assert "proves nothing" in " ".join(details)


def test_missing_anchor_is_unproven(tmp_path):
    """No anchor means nothing has demonstrated the control can fail."""
    tree = _build(tmp_path, include_anchor=False)
    verdict, details = _verdict(tree)
    assert verdict == "UNPROVEN", f"got {verdict}: {details}"
    assert "nothing has demonstrated this control can fail" in " ".join(details)


def test_missing_good_case_is_unproven(tmp_path):
    """Without a good case, a gate wedged at 'fail' would score as discriminating."""
    tree = _build(tmp_path, include_good_case=False)
    verdict, details = _verdict(tree)
    assert verdict == "UNPROVEN", f"got {verdict}: {details}"
    assert "stuck at BAD" in " ".join(details)


def test_gate_wedged_at_fail_is_caught_by_the_good_case(tmp_path):
    """A gate that reports on everything is not discriminating, it is stuck."""
    tree = _build(tmp_path, gate_src=GATE_WEDGED)
    verdict, details = _verdict(tree)
    assert verdict == "BLIND", f"got {verdict}: {details}"
    assert "good" in " ".join(details)


# --------------------------------------------------------------------------- #
# A crash is not a detection; an environment failure is not a finding.
# --------------------------------------------------------------------------- #


def test_crash_on_the_bad_case_is_not_a_detection(tmp_path):
    """Non-zero without reporting language is UNRESOLVED, never BAD.

    A gate that dies on the known-bad input exits non-zero exactly like one that
    reported it. Scoring the crash as a detection is this issue's own defect
    class occurring inside the tool built for it.
    """
    tree = _build(tmp_path, gate_src=GATE_CRASHER)
    verdict, details = _verdict(tree)
    assert verdict == "UNRESOLVED", f"got {verdict}: {details}"
    assert "A crash is not a detection" in " ".join(details)


def test_anchor_hash_mismatch_is_unresolved(tmp_path):
    """Anchor bytes must be the ones the control was written against."""
    tree = _build(tmp_path, anchor_sha_override="0" * 64)
    verdict, details = _verdict(tree)
    assert verdict == "UNRESOLVED", f"got {verdict}: {details}"
    assert "MISMATCH" in " ".join(details)


def test_unrunnable_invocation_is_unresolved_not_blind(tmp_path):
    """A missing interpreter is an environment failure, not a blindness finding."""
    tree = _build(tmp_path)
    manifest_path = tree / "controls" / "fake-control" / "control.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["invocation"] = ["definitely-not-a-real-interpreter", "{gate}", "--case", "{case}"]
    manifest_path.write_text(json.dumps(manifest))
    verdict, details = _verdict(tree)
    assert verdict == "UNRESOLVED", f"got {verdict}: {details}"


# --------------------------------------------------------------------------- #
# Discovery, and the deliberate divergence from CPP (claude-power-pack#986).
# --------------------------------------------------------------------------- #


def test_discover_returns_every_directive_not_just_the_first(tmp_path):
    """A gate may be controlled for several properties, so every directive counts.

    CPP's implementation compiles the pattern with re.MULTILINE and then calls
    `.search`, silently certifying a gate against whichever directive appears
    first in file order (claude-power-pack#986). CxPP is native precisely so it
    does not inherit that, and this case is what keeps it from being
    reintroduced.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "twogate.py").write_text(
        "#!/usr/bin/env python3\n"
        "#: NEGATIVE-CONTROL: first-property\n"
        "#: NEGATIVE-CONTROL: second-property\n"
        "print('hi')\n"
    )
    mod = _load_register()
    found = mod.discover(tmp_path)
    assert [rel for _, rel in found] == ["first-property", "second-property"], found


def test_no_registrations_refuses_a_vacuous_pass(tmp_path):
    """The register must not report success having run nothing.

    It enforces ADR 0008's bound, so it is held to it: a run that examined no
    control proves nothing, and saying so is the difference between this tool
    and the vacuous gates #245 fixed.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "plain.py").write_text("print('no directive here')\n")
    proc = subprocess.run(
        [sys.executable, str(REGISTER), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "refusing a vacuous pass" in proc.stderr


def test_every_verdict_is_reachable(tmp_path):
    """Every verdict the register can print is PRODUCED by a scenario here.

    The first version of this test compared two hand-written collections and
    never invoked the register at all - it passed against a register that kept
    its constants and evaluated nothing, and adding a sixth verdict left it
    green, which is the opposite of what its name claims. A vacuous test inside
    the anti-vacuity tool. Found by Codex review on #244; rewritten to run the
    scenarios and read the verdicts back.
    """
    scenarios = {
        "PASS": dict(),
        "BLIND": dict(gate_src=GATE_BLIND, anchor_src=GATE_SIGHTED),
        "INERT": dict(anchor_src=GATE_SIGHTED),
        "UNPROVEN": dict(include_anchor=False),
        "UNRESOLVED": dict(bad_has_trigger=False),
    }
    observed = set()
    for name, kwargs in scenarios.items():
        tree = _build(tmp_path / name, **kwargs)
        verdict, details = _verdict(tree)
        assert verdict == name, f"scenario {name} produced {verdict}: {details}"
        observed.add(verdict)

    mod = _load_register()
    # Derive the universe from the module, so a sixth verdict added there fails
    # here rather than passing silently.
    declared = {
        value
        for key, value in vars(mod).items()
        if key.isupper() and isinstance(value, str) and value == key
    }
    assert declared - {"GOOD", "BAD"} == observed, (
        f"verdicts the register can print but no scenario produces: "
        f"{declared - {'GOOD', 'BAD'} - observed}"
    )


# --------------------------------------------------------------------------- #
# Regression cases from the Codex review of this change (#244).
# --------------------------------------------------------------------------- #


def test_a_gate_that_consumes_its_fixture_cannot_certify_an_inert_control(tmp_path):
    """A self-mutating fixture must not turn an equally-capable anchor into a miss.

    The gate here reports the trigger and deletes it. Sharing one fixture, the
    anchor - which detects exactly as well - would then see a clean tree, "miss"
    the bad case, and the control would score PASS while proving nothing about
    the fix. Each invocation gets a private copy, so the anchor sees the trigger
    and the control is correctly INERT.
    """
    tree = _build(tmp_path, gate_src=GATE_CONSUMING, anchor_src=GATE_CONSUMING)
    verdict, details = _verdict(tree)
    assert verdict == "INERT", f"got {verdict}: {details}"


def test_detect_signal_matching_empty_output_is_refused(tmp_path):
    """A signal that matches nothing-printed would certify a crash as a detection.

    `""`, `"^"` and `".*"` all compile and all match the output of a gate that
    printed nothing, which collapses the one distinction detect_signal exists to
    draw.
    """
    for label, pattern in (("empty", ""), ("caret", "^"), ("dotstar", ".*")):
        tree = _build(tmp_path / label, detect_signal=pattern)
        verdict, details = _verdict(tree)
        assert verdict == "UNRESOLVED", f"pattern {pattern!r} got {verdict}: {details}"
        assert "matches empty output" in " ".join(details)


def test_anchor_crash_is_not_reported_as_a_caught_regression(tmp_path):
    """Gate misses it, anchor CRASHES: that is not evidence the anchor caught it.

    Reading a non-zero-without-reporting-language anchor as "CAUGHT" turns a
    broken anchor into a BLIND accusation against a gate that may be fine.
    """
    tree = _build(tmp_path, gate_src=GATE_BLIND, anchor_src=GATE_CRASHER)
    verdict, details = _verdict(tree)
    assert verdict == "UNRESOLVED", f"got {verdict}: {details}"
    assert "cannot be shown to have caught it" in " ".join(details)
