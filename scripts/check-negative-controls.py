#!/usr/bin/env python3
"""Run every gate's registered NEGATIVE CONTROL, and prove the control can fail (issue #244).

ADR 0008 says a load-bearing instrument must ship a committed input that makes
it report the other verdict. Nothing in this repository could check that. A green
from a blind gate and a green from a working gate are the same bytes, so the
blindness gets found by the next person to rely on the gate, not by its author.

THE ONE IDEA: the proof that a control CAN FAIL is a by-product of RUNNING the
control, never a separate ritual someone remembers. A control with no anchor is
UNPROVEN and `--strict` refuses it, so forgetting produces a red rather than a
silence.

Design adopted from claude-power-pack's `check-negative-controls.py` (CPP #924).
Written natively here rather than vendored - see ADR 1002 for that decision and
the measurement behind it.

---------------------------------------------------------------------------
What a control asserts - three checks, and why each exists
---------------------------------------------------------------------------
DISCRIMINATION   gate(known-bad) == BAD *and* gate(known-good) == GOOD. Both
                 directions. A gate wedged at "fail" passes the known-bad half
                 on its own, so the good case is what separates a working gate
                 from a stuck one.

ANCHOR           the same control, run against a known-blind artifact, must
                 FAIL - the artifact must MISS the known-bad input. This is
                 "show the control still failing if the fix is reverted",
                 executed on every run instead of once by hand. An anchor that
                 CATCHES the bad input proves the control is not load-bearing:
                 INERT.

ANCHOR SANITY    the anchor must agree with the current gate on the known-GOOD
                 input. If it disagrees there too, it differs for reasons beyond
                 the blindness under test, and the demonstration is not isolated.

---------------------------------------------------------------------------
A CRASH IS NOT A DETECTION
---------------------------------------------------------------------------
Deciding a case from the exit code alone means a gate that FELL OVER on the
known-bad input scores exactly like one that REPORTED it - an uncaught traceback
also exits non-zero. So the manifest DECLARES the signal: `detect_signal`, a
regex the gate's own output (stdout and stderr together) must carry when it
genuinely reports a finding. A BAD verdict needs the gate to have SAID
something, not merely to have exited badly.

`detect_signal` is also what makes a control PROPERTY-SCOPED rather than
gate-scoped. `harness-lint` refuses a vacuous pass AND reports unadapted
constructs; both are non-zero exits. Only the declared signal distinguishes
"this control is about vacuity" from "this control is about constructs".

---------------------------------------------------------------------------
ONE GATE MAY REGISTER SEVERAL CONTROLS (the deliberate divergence)
---------------------------------------------------------------------------
`discover()` collects EVERY `#: NEGATIVE-CONTROL:` directive in a gate, not the
first. CPP's implementation compiles its pattern with re.MULTILINE - anticipating
several - and then calls `.search`, taking one (claude-power-pack#986, filed from
this work). That is silent rather than merely wrong: `.search` takes the first
match in FILE ORDER, so moving two comment lines changes what a gate is
certified against, with no diff to any control and no change to this tool's
output.

It matters here because a gate's anchor is property-specific. Measured on
2026-09-15: the pre-#245 `harness_lint.py` at 0f0491d MISSES the vacuous root
(exit 0, "0 markdown file(s) passed") and CATCHES an `Agent tool` construct
(exit 1, identical to the current gate). One anchor cannot serve both
properties, and the anchor must miss EVERY bad case in its control - so the two
properties need two controls, which needs two directives.

---------------------------------------------------------------------------
WHAT THIS IS NOT
---------------------------------------------------------------------------
It is NOT a coverage map. A registered control proves ONE property of ONE gate,
and only gates that can be pointed at a fixture can be registered at all. Read
`--list` as "what has been proven", never as "what is covered". ADR 1002
carries the current gap and why it is shaped the way it is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTROLS_ROOT = REPO_ROOT / "controls"

#: A gate registers a control by carrying this directive in its own source, so
#: the registration lives next to the thing it describes rather than in a
#: central list that drifts. MULTILINE and finditer together: a gate may carry
#: several, one per property it is controlled for.
REGISTRATION_RE = re.compile(r"^#:?\s*NEGATIVE-CONTROL:\s*(?P<path>\S+)\s*$", re.MULTILINE)

GOOD = "GOOD"
BAD = "BAD"

#: Verdicts. Kept distinct on purpose: collapsing any two of them reports an
#: environment failure as a blindness finding, or the reverse.
PASS = "PASS"
BLIND = "BLIND"
INERT = "INERT"
UNPROVEN = "UNPROVEN"
UNRESOLVED = "UNRESOLVED"

#: Stands in for an exit code when the invocation could not be executed AT ALL -
#: a missing interpreter, a permissions error, a timeout. It is not a verdict.
#: Collapsing it into an exit code makes an unrunnable control score as a
#: detection on the bad case and as a gate alarm on the good one: an environment
#: failure reported as "the gate stopped discriminating".
UNRUNNABLE = None

EXEC_TIMEOUT_S = 120


@dataclass
class Result:
    name: str
    gate: str
    verdict: str = PASS
    details: list[str] = field(default_factory=list)


def discover(root: Path) -> list[tuple[Path, str]]:
    """Every (gate, control-path) registration under `scripts/`.

    A gate may register more than one control; every directive is returned.
    """
    found: list[tuple[Path, str]] = []
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        return found
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in REGISTRATION_RE.finditer(text):
            found.append((path, match.group("path")))
    return found


def _escaping_symlink(case: Path) -> Path | None:
    """First symlink inside `case` whose target lies outside it, if any.

    Copying a fixture per invocation isolates its CONTENTS, not everything those
    contents can reach. A link pointing out of the case still points at shared
    state in every copy, so a gate that repairs content through it mutates the
    one original and the anchor that runs next sees it clean - the private-copy
    fix defeated by the thing it was meant to fix. A relative link that escapes
    also silently means something different once relocated. Found by the second
    Codex pass on #244.
    """
    if not case.is_dir():
        return None
    base = case.resolve()
    for path in case.rglob("*"):
        if not path.is_symlink():
            continue
        target = Path(os.readlink(path))
        resolved = target if target.is_absolute() else (path.parent / target)
        try:
            resolved.resolve().relative_to(base)
        except ValueError:
            return path
    return None


def _invoke(invocation: list[str], gate: Path, case: Path, root: Path) -> tuple[int | None, str, str]:
    """Run one invocation against a PRIVATE COPY of the case.

    The gate and the anchor are run against the same case path in turn. A gate
    that REPAIRS or consumes the offending input - a formatter, a --fix mode, a
    sweep - would leave the anchor a clean tree, so an anchor every bit as
    capable would miss it and the control would score PASS on a fixture that
    mutated itself. Copying per invocation removes the ordering dependency
    rather than testing for it. Found by Codex review on #244.
    """
    escaping = _escaping_symlink(case)
    if escaping is not None:
        # Refused rather than guessed: remapping the target into every private
        # tree would change what the fixture means, and following it would
        # reintroduce the shared-state failure.
        return UNRUNNABLE, "", (
            f"case contains a symlink escaping the fixture: "
            f"{escaping.relative_to(case)} -> {os.readlink(escaping)}. "
            "A link out of the case points at shared state in every copy, so one "
            "invocation can change what the next one sees."
        )

    with tempfile.TemporaryDirectory(prefix="negctl-") as tmp:
        scratch = Path(tmp) / case.name
        if case.is_dir():
            shutil.copytree(case, scratch, symlinks=True)
        else:
            shutil.copy2(case, scratch)
        return _run(invocation, gate, scratch, root)


def _run(invocation: list[str], gate: Path, case: Path, root: Path) -> tuple[int | None, str, str]:
    argv = [part.replace("{gate}", str(gate)).replace("{case}", str(case)) for part in invocation]
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError as exc:
        return UNRUNNABLE, "", f"interpreter or gate not found: {exc}"
    except PermissionError as exc:
        return UNRUNNABLE, "", f"not executable: {exc}"
    except subprocess.TimeoutExpired:
        return UNRUNNABLE, "", f"timed out after {EXEC_TIMEOUT_S}s"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), ""


def _verdict_of(code: int | None, output: str, good_exit: int, signal: re.Pattern[str]) -> str:
    """GOOD, BAD, or UNSIGNALLED - a third OBSERVATION, not a third expectation.

    UNSIGNALLED is a non-zero exit with none of the gate's own reporting language
    in it. That is what a crash looks like, and it must not be read as a
    detection.
    """
    if code == good_exit:
        return GOOD
    if signal.search(output):
        return BAD
    return "UNSIGNALLED"


def _provenance(anchor: dict, anchor_path: Path) -> str:
    declared = anchor.get("sha256")
    if not declared:
        return "undeclared"
    actual = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
    return "verified" if actual == declared else f"MISMATCH(declared {declared[:12]}, actual {actual[:12]})"


def evaluate(control_dir: Path, gate: Path, root: Path) -> Result:
    name = control_dir.name
    res = Result(name=name, gate=str(gate.relative_to(root)))

    manifest_path = control_dir / "control.json"
    if not manifest_path.is_file():
        res.verdict = UNRESOLVED
        res.details.append(f"no control.json in {control_dir}")
        return res
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        res.verdict = UNRESOLVED
        res.details.append(f"control.json unreadable: {exc}")
        return res

    try:
        invocation = list(manifest["invocation"])
        good_exit = int(manifest["good_exit"])
        cases = list(manifest["cases"])
        signal = re.compile(manifest["detect_signal"], re.MULTILINE)
    except (KeyError, TypeError, ValueError, re.error) as exc:
        res.verdict = UNRESOLVED
        res.details.append(f"control.json is not a usable manifest: {exc}")
        return res

    limits = manifest.get("limits")
    if limits:
        # Adopted from claude-power-pack at 459f3c2: a machine-readable "what
        # this control does NOT establish". It is printed with the verdict so a
        # PASS is never read as wider than the control's own author claimed.
        res.details.append(f"limits: {limits}")

    if signal.search(""):
        # "", "^" and ".*" all compile and all match a gate that printed nothing.
        # A crash would then satisfy the signal requirement, which is the exact
        # distinction detect_signal exists to draw. Found by Codex review on #244.
        res.verdict = UNRESOLVED
        res.details.append(
            f"detect_signal {manifest['detect_signal']!r} matches empty output, so a gate that "
            "printed nothing would count as having reported a finding. Declare the gate's own "
            "reporting language."
        )
        return res

    bad_cases = [control_dir / c["input"] for c in cases if c["expect"] == BAD]
    good_cases = [control_dir / c["input"] for c in cases if c["expect"] == GOOD]
    if not bad_cases:
        res.verdict = UNPROVEN
        res.details.append("no known-bad case: nothing asks this gate to report the other verdict")
        return res
    if not good_cases:
        # Without it, a gate wedged at "always fail" scores as discriminating.
        res.verdict = UNPROVEN
        res.details.append("no known-good case: a gate stuck at BAD would pass this control")
        return res

    anchors = list(manifest.get("anchors") or [])
    if not anchors:
        res.verdict = UNPROVEN
        res.details.append("no anchor: nothing has demonstrated this control can fail")
        return res
    for anchor in anchors:
        anchor_path = control_dir / anchor["path"]
        if not anchor_path.is_file():
            res.verdict = UNRESOLVED
            res.details.append(f"anchor missing: {anchor['path']}")
            return res
        prov = _provenance(anchor, anchor_path)
        res.details.append(f"anchor {anchor.get('sha', '?')}: provenance {prov}")
        if prov.startswith("MISMATCH"):
            res.verdict = UNRESOLVED
            res.details.append("anchor bytes are not the ones this control was written against")
            return res

    # -- DISCRIMINATION ----------------------------------------------------- #
    for case in cases:
        case_path = control_dir / case["input"]
        if not case_path.exists():
            res.verdict = UNRESOLVED
            res.details.append(f"case input missing: {case['input']}")
            return res
        code, output, diag = _invoke(invocation, gate, case_path, root)
        if code is UNRUNNABLE:
            res.verdict = UNRESOLVED
            res.details.append(f"case {case['name']}: gate could not be executed - {diag}")
            return res
        got = _verdict_of(code, output, good_exit, signal)
        want = case["expect"]
        if got == want:
            res.details.append(f"case {case['name']}: gate said {got} as required (exit {code})")
            continue
        if got == "UNSIGNALLED":
            res.verdict = UNRESOLVED
            res.details.append(
                f"case {case['name']}: gate exited {code} without its own reporting language. "
                "A crash is not a detection; the required property could not be confirmed."
            )
            return res
        if want == BAD and got == GOOD:
            # TWO READINGS, and the register is not entitled to pick one by
            # itself: the gate may be blind to this input, or the input may not
            # be bad. This is the #244 near-miss - a fixture of SendMessage,
            # ~/.claude/scripts/ and /flow:auto PASSED harness-lint and nearly
            # got a working gate reported as blind. The anchor is the only
            # evidence available, so consult it before naming a culprit.
            verdicts = []
            for anchor in anchors:
                a_code, a_out, a_diag = _invoke(invocation, control_dir / anchor["path"], case_path, root)
                if a_code is UNRUNNABLE:
                    res.verdict = UNRESOLVED
                    res.details.append(f"anchor could not be executed - {a_diag}")
                    return res
                verdicts.append(_verdict_of(a_code, a_out, good_exit, signal))
            if any(v == "UNSIGNALLED" for v in verdicts):
                # Non-zero with no reporting language. Reading that as "the anchor
                # caught it" turns a broken anchor into an accusation against a
                # working gate - the same misscore the anchor block below already
                # avoids. Found by Codex review on #244.
                res.verdict = UNRESOLVED
                res.details.append(
                    f"case {case['name']}: the gate did not report it, and the anchor exited "
                    "non-zero without reporting language. The anchor cannot be shown to have "
                    "caught it, so nothing here is evidence about the gate."
                )
                return res
            if all(v == GOOD for v in verdicts):
                res.verdict = UNRESOLVED
                res.details.append(
                    f"case {case['name']}: the gate did not report it, and neither did the blind "
                    "anchor. Those are the same bytes for 'the gate is blind' and 'this case never "
                    "exercised the rule', so this run cannot tell them apart. Check the case "
                    "against the gate's actual rules before concluding anything about the gate."
                )
                return res
            res.verdict = BLIND
            res.details.append(
                f"case {case['name']}: the gate missed it but the anchor CAUGHT it - the gate "
                "reports less than an older version did, which is a regression, not a bad case"
            )
            return res
        res.verdict = BLIND
        res.details.append(f"case {case['name']}: wanted {want}, gate said {got} (exit {code})")
        return res

    # -- ANCHOR + ANCHOR SANITY --------------------------------------------- #
    for anchor in anchors:
        anchor_path = control_dir / anchor["path"]
        for case_path in bad_cases:
            code, output, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor.get('sha', '?')} could not be executed - {diag}")
                return res
            got = _verdict_of(code, output, good_exit, signal)
            if got == "UNSIGNALLED":
                # A blind anchor is supposed to sail past the bad input, not die
                # on it. Calling a crash "CAUGHT" accuses a healthy anchor of not
                # being blind and sends someone to replace a good artifact.
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor.get('sha', '?')} exited {code} on {case_path.name} without "
                    "reporting language - cannot confirm it is blind to this input"
                )
                return res
            if got == BAD:
                res.verdict = INERT
                res.details.append(
                    f"anchor {anchor.get('sha', '?')} CAUGHT {case_path.name}, so this control "
                    "would still pass against a gate that never had the fix - it proves nothing"
                )
                return res
            res.details.append(
                f"anchor {anchor.get('sha', '?')}: missed {case_path.name} (blind, as required)"
            )

        for case_path in good_cases:
            code, output, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor.get('sha', '?')} could not be executed - {diag}")
                return res
            if _verdict_of(code, output, good_exit, signal) != GOOD:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor.get('sha', '?')} disagrees with the gate on {case_path.name} too, "
                    "so it differs for reasons beyond the blindness under test"
                )
                return res
            res.details.append(
                f"anchor {anchor.get('sha', '?')}: agrees on {case_path.name} (isolated, as required)"
            )

    return res


def run(root: Path, controls_root: Path, strict: bool, list_only: bool) -> int:
    registrations = discover(root)
    if not registrations:
        # Nothing scanned proves nothing. This tool is itself an instrument, and
        # an empty run reporting success is the exact defect it exists to find.
        print(
            "negative-controls: refusing a vacuous pass - no gate under scripts/ carries a "
            "'#: NEGATIVE-CONTROL:' directive, so no control was run.",
            file=sys.stderr,
        )
        return 3

    results: list[Result] = []
    for gate, rel in registrations:
        control_dir = (controls_root / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
        if list_only:
            print(f"{gate.relative_to(root)}  ->  {control_dir.relative_to(root)}")
            continue
        results.append(evaluate(control_dir, gate, root))

    if list_only:
        return 0

    failed = [r for r in results if r.verdict != PASS]
    for res in results:
        print(f"[{res.verdict}] {res.name}  ({res.gate})")
        for line in res.details:
            print(f"    {line}")

    proven = len(results) - len(failed)
    print(f"\nnegative-controls: {proven}/{len(results)} control(s) discriminate and are proven able to fail")
    if failed:
        print("negative-controls: " + ", ".join(f"{r.name}={r.verdict}" for r in failed), file=sys.stderr)
        return 1
    if strict:
        # Nothing further to refuse: UNPROVEN and UNRESOLVED already land in
        # `failed`. --strict exists so the caller can SAY it wants that, and so
        # a future softening has to change this line deliberately.
        return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run every gate's registered negative control.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to scan")
    parser.add_argument("--controls-root", type=Path, default=None, help="controls/ tree (default: <root>/controls)")
    parser.add_argument("--strict", action="store_true", help="refuse unproven controls (they already fail)")
    parser.add_argument("--list", action="store_true", dest="list_only", help="list registrations and exit")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    controls_root = (args.controls_root or (root / "controls")).resolve()
    return run(root, controls_root, strict=args.strict, list_only=args.list_only)


if __name__ == "__main__":
    sys.exit(main())
