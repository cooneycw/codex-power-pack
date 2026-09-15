"""The secret gate's CONFIGURATION tripwire (issue #246).

Issue #263 made the scanner's silence mean something by proving it has rules.
This file guards the other half: that the rules are still pointed at the
repository. An allowlist entry is the one edit that narrows a scan without
changing anything about its output - a scan examining three directories fewer
still reports "no leaks found" - so the narrowing has to be made loud somewhere
other than the scan's own verdict.

WHAT THIS CAN AND CANNOT CHECK, because the difference matters and a future
reader should not have to infer it:

    It checks that every allowlist entry is DECLARED here with a justification,
    and that the justification is a non-empty string.

    It cannot check that the justification is TRUE. Nothing can. A test that
    reads "false positive from a test fixture" has no way to know whether the
    entry suppresses a fixture or a live credential.

What that buys is not correctness, it is VISIBILITY: unscanning a path stops
being a one-line config edit and becomes an edit to a test, which is read
differently. The count-preserving-swap hazard applies one layer up - the cheap
repair when this goes red is to paste the new entry into the list below - and
the answer to that is the same as everywhere else: the diff is where the review
happens, so make sure there is one.

The behavioural half lives in .woodpecker.yml's coverage probe, which scans the
repository and requires every committed marker to be reported. This file runs in
`make verify`, where gitleaks does not exist; that one runs in the gitleaks
image, where Python does not. Neither image has both, which is why the property
is checked twice in two languages rather than once properly.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / ".gitleaks.toml"

MARKER_TOKEN = "CXPP-SECRET-SCAN-COVERAGE-MARKER-V1"
MARKER_NAME = ".secret-scan-coverage"

#: An allowlist entry pointing INSIDE a registered control's fixtures. These are
#: the one legitimate case for hiding a path from the repository scan: the
#: fixture must contain something the ruleset reports, or the control cannot ask
#: the gate to report anything. It is not the circular exclusion #246 refuses -
#: a path entry is matched relative to the SCAN ROOT, and the control scans each
#: case as its own root, so the fixture is hidden from the repository scan and
#: fully visible to the control that needs it.
FIXTURE_ENTRY_RE = re.compile(r"^\^?controls/[^/]+/cases/")

#: Every `[allowlist] paths` entry, and why it is there. Read the module
#: docstring before adding one: this list records a decision, it does not make
#: one.
ALLOWLIST_PATHS: dict[str, str] = {
    "^controls/secret-scan-rules/cases/": (
        "negative-control fixtures for this very config. They hold a fabricated AWS key "
        "because the control needs an input the ruleset REPORTS, and anything the ruleset "
        "reports is also reported when it sits in the repository."
    ),
    r"tests/test_creds_masking\.py": (
        "test fixtures for the credential masker: the file asserts that masking happens, so it "
        "necessarily contains the shapes being masked."
    ),
    r"scripts/secrets-mask\.sh": (
        "the masking script itself - it carries the regex patterns it masks WITH, which look "
        "like the things they match."
    ),
    r"lib/creds/masking\.py": (
        "the masking library, for the same reason as the script above."
    ),
}

#: Every `[allowlist] regexes` entry, and why. These are value-scoped, matched
#: against the MATCH (see `regexTarget` below), and they are narrower than a
#: path entry by construction: a path entry also suppresses a REAL secret added
#: to that file later, a value entry does not.
ALLOWLIST_REGEXES: dict[str, str] = {
    "AKIAIOSFODNN7EXAMPLE": "AWS' own documentation placeholder; it is not a key.",
    "sk-abc123xyz456def789": "obviously-synthetic OpenAI-shaped token used in fixtures.",
    "ghp_abc123def456ghi789jkl012mno345pqr678": (
        "obviously-synthetic GitHub-shaped token used in fixtures."
    ),
    "BEGIN OPENSSH PRIVATE KEY.*REDACTED": (
        "a redacted key banner in fixture text - the REDACTED tail is what makes it safe."
    ),
    "BEGIN RSA PRIVATE KEY.*MIIEpAIBAAKCAQEA": (
        "the standard RSA test-key preamble used in fixtures."
    ),
    '"ghp_abcdefghijklmnopqrstuvwxyz123456"': (
        "synthetic token in tests/test_plugin_hooks.py, asserting the friction hook MASKS a "
        "secret it is handed. Bounded by its surrounding quotes and allowlisted BY VALUE "
        "rather than by path deliberately (#263): a path entry would also suppress a real "
        "secret added to that file later."
    ),
}


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def _entry_directory(entry: str) -> str:
    """The directory an allowlist path entry names, as a repo-relative path.

    `tests/test_creds_masking\\.py` -> `tests`; `lib/creds/masking\\.py` ->
    `lib/creds`; `tests/.*` -> `tests`; an entry with no separator -> the root.
    """
    body = entry.lstrip("^")
    if "/" not in body:
        return ""
    return body.rsplit("/", 1)[0].replace("\\", "")


def required_marker_paths() -> set[Path]:
    """Where a coverage marker must live: the root, plus every LIVE entry's directory.

    DERIVED, not listed. A hand-maintained list of marked directories would be
    one more thing to forget in the same edit that adds the exclusion - and the
    edit that adds an exclusion is exactly the one that must not be able to go
    unnoticed.
    """
    required = {REPO_ROOT / MARKER_NAME}
    for entry in ALLOWLIST_PATHS:
        if FIXTURE_ENTRY_RE.match(entry):
            continue
        required.add(REPO_ROOT / _entry_directory(entry) / MARKER_NAME)
    return required


def test_allowlist_paths_are_exactly_the_declared_set() -> None:
    """A fourth path entry is a deliberate act, not a one-line config edit."""
    declared = _config()["allowlist"]["paths"]

    assert set(declared) == set(ALLOWLIST_PATHS), (
        "the allowlist's path entries have changed. Each one removes a path from EVERY "
        "scan, and the scan reports 'no leaks found' either way - so declare it above "
        "with why it is there, and read the module docstring on what that does and does "
        "not establish."
    )
    assert len(declared) == len(set(declared)), "duplicate path entries"
    for entry, why in ALLOWLIST_PATHS.items():
        assert why.strip(), f"path entry {entry!r} has an empty justification"


def test_allowlist_regexes_are_exactly_the_declared_set() -> None:
    """Same contract for value entries. An over-broad one suppresses everything.

    Measured against zricethezav/gitleaks:v8.18.4: adding `[A-Z-]+` to this list
    makes the scan report nothing at all, including a real AWS key - the
    coverage probe catches it behaviourally by finding zero markers, this
    catches the edit.
    """
    declared = _config()["allowlist"]["regexes"]

    assert set(declared) == set(ALLOWLIST_REGEXES), (
        "the allowlist's value entries have changed; declare each one above with why."
    )
    assert len(declared) == len(set(declared)), "duplicate regex entries"
    for entry, why in ALLOWLIST_REGEXES.items():
        assert why.strip(), f"regex entry {entry!r} has an empty justification"


def test_allowlist_declares_no_commit_exemptions() -> None:
    """Negative membership: a `commits` entry is invisible to the coverage probe.

    The repository scan runs in git mode, so a commit SHA listed here silences
    every finding in that commit. The coverage probe cannot see it - markers are
    reported from the commits that added them, which are not the exempted one -
    so this is the only place such an entry would be noticed.
    """
    allowlist = _config()["allowlist"]

    assert "commits" not in allowlist, (
        "a commits allowlist suppresses every finding in the named commits and nothing "
        "else in this repository would report that it had been added"
    )


def test_allowlist_has_no_undeclared_suppression_keys() -> None:
    """`paths` and `regexes` are not the only ways to suppress a finding.

    `stopwords` is the one that matters here, and it is invisible to every other
    check in this change. Measured against zricethezav/gitleaks:v8.18.4 with the
    same two-credential fixture:

        no stopwords                     -> aws-access-token, github-pat
        stopwords = ["ghp_"]             -> aws-access-token          (suppressed)
        a config EXTENDING that one      -> aws-access-token, github-pat

    The third line is why this test has to exist. Stopwords are NOT inherited
    through `[extend]`, so the coverage probe - which extends the production
    config - would go on reporting everything while production quietly stopped.
    A suppression surface the behavioural instrument is structurally blind to can
    only be caught by pinning the config's shape. Found by Codex review on #246.

    `regexTarget` is pinned for a related reason: the value entries above are
    written WITH their surrounding quotes and match against the MATCH. Silently
    switching the target to "secret" would stop those entries matching, which is
    a widening rather than a suppression - loud in the scan, but still a change
    to the meaning of every declared entry.
    """
    allowlist = _config()["allowlist"]

    assert set(allowlist) == {"description", "paths", "regexTarget", "regexes"}, (
        "an undeclared key in [allowlist]. `stopwords` suppresses every finding "
        "containing the word and is inherited by nothing, so neither the coverage probe "
        "nor the secret-scan control would notice it"
    )
    assert allowlist["regexTarget"] == "match", (
        "the declared value entries are written with their surrounding quotes and only "
        "match against the MATCH; changing the target changes what all of them mean"
    )


def test_config_declares_no_unreviewed_top_level_tables() -> None:
    """Pin the config's SHAPE, not only the allowlist's contents.

    A `[[rules]]` table may carry its own `[rules.allowlist]`, which the checks
    above do not read - so a second, unreviewed suppression surface can be added
    without touching either declared list.
    """
    assert set(_config()) == {"title", "extend", "allowlist"}, (
        "a new top-level table in .gitleaks.toml. If it is a rule with its own allowlist, "
        "the suppression checks in this file do not see it."
    )


def test_every_marked_directory_carries_a_live_marker() -> None:
    """The markers the coverage probe depends on still exist and still say it.

    The probe runs in git mode, so it reports a marker from the commit that
    ADDED it - which means a marker deleted from the working tree keeps passing
    there forever. This is the half that notices.
    """
    for marker in sorted(required_marker_paths()):
        rel = marker.relative_to(REPO_ROOT)
        assert marker.is_file(), (
            f"missing coverage marker {rel}. .woodpecker.yml's coverage probe proves the "
            f"scan reaches {rel.parent or '.'} by requiring this file to be reported; "
            "without it, nothing does."
        )
        assert MARKER_TOKEN in marker.read_text(encoding="utf-8"), (
            f"coverage marker {rel} no longer carries the token the probe looks for, so the "
            "probe has stopped proving anything about that path"
        )


def test_no_allowlist_entry_unscans_a_marked_path() -> None:
    """The coverage probe's property, re-derived without gitleaks.

    The probe is the real measurement - it runs the actual scanner - but it only
    runs in the gitleaks image. This runs in `make verify` on every host, and it
    is the check that turns `tests/.*` red at the moment it is written rather
    than one CI round-trip later.
    """
    markers = {str(p.relative_to(REPO_ROOT)) for p in required_marker_paths()}

    for entry in ALLOWLIST_PATHS:
        pattern = re.compile(entry)
        hit = sorted(m for m in markers if pattern.search(m))
        assert not hit, (
            f"allowlist path entry {entry!r} matches coverage marker(s) {hit}, so the "
            "directories those markers stand for are no longer scanned - and the scan "
            "would keep reporting 'no leaks found' exactly as before"
        )
