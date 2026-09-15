"""Regression checks for the post-demolition Woodpecker pipeline."""

import subprocess
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_EVENTS = {"push", "pull_request"}


def _pipeline() -> dict:
    return yaml.safe_load((REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))


def _events(step: dict) -> set[str]:
    events: set[str] = set()
    for condition in step.get("when", []):
        value = condition.get("event", [])
        events.update(value if isinstance(value, list) else [value])
    return events


def test_gitleaks_is_the_first_blocking_ci_step() -> None:
    """Issue #97: scan credentials before dependency installation or validation."""
    pipeline = _pipeline()

    steps = pipeline["steps"]
    assert next(iter(steps)) == "secret-scan"
    assert steps["secret-scan"]["image"] == "zricethezav/gitleaks:v8.18.4"
    commands = steps["secret-scan"]["commands"]
    # EXTENDED, never relaxed. #246 added a third command and the count moved
    # with it; what must not move is the repo scan being LAST, so no probe can
    # ever be appended after the verdict it is supposed to qualify. Equality on
    # the count is the point - `>= 2` would let a fourth arrive unnoticed.
    assert len(commands) == 3
    assert commands[-1] == "gitleaks detect --source . --config .gitleaks.toml --verbose"
    assert _events(steps["secret-scan"]) == REQUIRED_EVENTS


def test_secret_scan_runs_a_positive_control_before_the_repo_scan() -> None:
    """Issue #263: a green scan is what the BROKEN scanner produced.

    Until 2026-09-15 this step passed `--config .gitleaks.toml`, which REPLACES
    gitleaks' built-in ruleset, against a config declaring no rules - so it
    reported "no leaks found" on everything. The probe makes the step's silence
    mean something by requiring a known secret to be detected first.

    The assertions below are deliberately about the probe's FAILURE path rather
    than its text. gitleaks exits NON-ZERO when it finds something, so the probe
    must fail when gitleaks SUCCEEDS; written the natural way round it would
    pass in both worlds and be exactly the instrument that cannot fail.
    """
    probe = _pipeline()["steps"]["secret-scan"]["commands"][0]

    # EXACTLY 1, never merely non-zero: gitleaks exits 1 on a find and 0 on a
    # clean scan, so a non-zero test would also accept 127 (binary absent) and
    # report a scanner that never ran as one that works.
    assert "--exit-code" in probe, (
        "the probe must move a FIND to a distinct status: gitleaks' default find-code "
        "is 1 and it also exits 1 on a fatal error, so requiring 1 reads a broken "
        "config as a detection"
    )
    assert "probe_rc" in probe, "the probe must capture the exit code, not branch on truthiness"
    assert "trap " in probe, "the fixture must be removed on every exit path, not just success"
    assert "--source /tmp/secret-scan-probe" in probe, "the probe must scan its own fixture"
    assert "--config .gitleaks.toml" in probe, "the probe must use the config under test"
    assert "exit 1" in probe, "the probe must fail the step when detection does not happen"


def test_gitleaks_config_loads_the_default_ruleset() -> None:
    """Issue #263: without this the scanner has no rules at all.

    Cheap, runs everywhere, and catches the specific regression: `--config`
    replaces the built-in ruleset rather than merging with it, so removing this
    block silently turns every scan into a pass. The probe above catches the
    same thing behaviourally but only runs in the gitleaks image; this runs in
    `make verify`, where gitleaks is not installed.
    """
    config = tomllib.loads((REPO_ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    # PARSED, not substring-matched. A text search is satisfied by a comment
    # mentioning [extend], so deleting the real table while leaving the prose
    # that explains it would keep the guard green - a guard passing on the
    # documentation of the thing it is guarding.
    assert config.get("extend", {}).get("useDefault") is True, (
        "gitleaks --config REPLACES the built-in ruleset; without extend.useDefault "
        "the scanner has no rules and reports 'no leaks found' on everything (#263)"
    )


def test_required_ci_uses_complete_local_contract_and_exact_pin() -> None:
    steps = _pipeline()["steps"]

    assert _events(steps["validate"]) == REQUIRED_EVENTS
    assert steps["validate"]["commands"][-1] == "make verify"
    assert "git make" in "\n".join(steps["validate"]["commands"])

    pin_step = steps["codex-skills-pin-integrity"]
    assert _events(pin_step) == REQUIRED_EVENTS
    commands = "\n".join(pin_step["commands"])
    assert "--pin-ref" in commands
    assert commands.index("--pin-ref") < commands.index("git clone")
    assert "https://github.com/cooneycw/claude-power-pack.git" in commands
    assert "checkout --detach" in commands
    assert "make codex-skills-pin-check CPP_ROOT=/tmp/claude-power-pack-pinned" in commands
    assert "git make" in commands


def test_dependency_audit_is_required_and_precedes_advisory_report() -> None:
    steps = _pipeline()["steps"]
    names = list(steps)

    assert _events(steps["dependency-audit"]) == REQUIRED_EVENTS
    assert steps["dependency-audit"]["commands"][-1] == "make dep-audit"
    tools = "\n".join(steps["dependency-audit"]["commands"])
    assert "make" in tools
    assert "uv pip-audit bandit" in tools
    assert names.index("dependency-audit") < names.index("codex-skills-upstream-report")


def test_latest_upstream_report_is_manual_or_named_cron_only() -> None:
    step = _pipeline()["steps"]["codex-skills-upstream-report"]
    commands = "\n".join(step["commands"])

    assert _events(step) == {"manual", "cron"}
    assert step["when"] == [
        {"event": "manual"},
        {"event": "cron", "cron": "codex-skills-upstream-report"},
    ]
    assert "--latest-ref" in commands
    assert commands.index("--latest-ref") < commands.index("git init")
    assert "remote add origin https://github.com/cooneycw/claude-power-pack.git" in commands
    assert 'fetch --depth=1 origin "$CPP_REF"' in commands
    assert 'checkout --detach "$CPP_REF"' in commands
    assert (
        'make codex-skills-upstream-report CPP_ROOT=/tmp/claude-power-pack-current CPP_REF="$CPP_REF"'
        in commands
    )
    assert "make codex-skills-currency-check" not in commands


def test_single_workflow_preserves_aggregate_pr_and_push_context_shape() -> None:
    pipeline = _pipeline()
    workflow_events = set(pipeline["when"][0]["event"])

    assert workflow_events == {"push", "pull_request", "manual", "cron"}
    assert not (REPO_ROOT / ".woodpecker").exists()


def test_make_verify_dependency_bearing_scripts_use_the_uv_environment() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    for command in (
        "uv run --extra dev python scripts/skill_contract_baseline.py --check",
        "uv run --extra dev python scripts/skill_contract_lint.py --check",
        "uv run --extra dev python scripts/project_next_sync.py --check",
    ):
        assert command in makefile


def test_pipeline_contains_no_deleted_runtime_image_gates() -> None:
    """The repository no longer owns runtime images after demolition."""
    text = (REPO_ROOT / ".woodpecker.yml").read_text(encoding="utf-8")

    assert "image-security" not in text
    assert "runtime-smoke" not in text


def _run_probe_with_stub_gitleaks(tmp_path: Path, exit_code: int, anchor_exit: int = 0) -> int:
    """Execute the REAL probe against a stub gitleaks returning `exit_code`.

    Behavioural rather than textual. The earlier guards asserted that the probe
    CONTAINED `-ne 1` and `probe_rc`, which a branch reversed to fail on success
    also satisfies - the assertion constrained the vocabulary, not the logic.
    Running it is the only thing that distinguishes them, and a stub costs
    nothing: no gitleaks, no container, so this runs inside `make verify` where
    the real binary is absent.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    stub = bin_dir / "gitleaks"
    # Config-aware since #246: the step now runs the same fixture through the
    # production config AND through the pre-#263 anchor, and a stub that
    # answered both the same way could only simulate a scanner wedged at one
    # verdict. `anchor_exit` defaults to 0 - missed, as a blind anchor must.
    stub.write_text(
        "#!/bin/sh\n"
        'config=""; prev=""\n'
        'for a in "$@"; do [ "$prev" = "--config" ] && config="$a"; prev="$a"; done\n'
        "case \"$config\" in\n"
        f"  *anchors/*) exit {anchor_exit} ;;\n"
        f"  *) exit {exit_code} ;;\n"
        "esac\n"
    )
    stub.chmod(0o755)
    (tmp_path / ".gitleaks.toml").write_text('title = "stub"\n')

    probe = _pipeline()["steps"]["secret-scan"]["commands"][0]
    return subprocess.run(
        ["sh", "-c", probe],
        cwd=tmp_path,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
    ).returncode


def test_probe_passes_only_when_gitleaks_reports_a_find(tmp_path):
    """Exit 1 means detected. Nothing else may be read as detection.

    gitleaks exits 1 on a find and 0 on a clean scan, so a probe testing for
    "non-zero" also accepts 127 (binary missing), 139 (crash) and every other
    failure - reporting a scanner that never ran as one that works. That is the
    same rule this repo's negative-control register enforces: a crash is not a
    detection.
    """
    assert _run_probe_with_stub_gitleaks(tmp_path / "found", 42) == 0, (
        "the probe must PASS when gitleaks reports a find at its declared --exit-code"
    )
    assert _run_probe_with_stub_gitleaks(tmp_path / "clean", 0) == 1, (
        "the probe must FAIL when the scanner detects nothing - an empty ruleset"
    )
    assert _run_probe_with_stub_gitleaks(tmp_path / "fatal", 1) == 1, (
        "the probe must FAIL on gitleaks' ERROR status. This is the case a naive "
        "probe gets wrong: 1 is both the default find-code and the fatal-error "
        "code, so an unparseable config reads as a successful detection"
    )
    assert _run_probe_with_stub_gitleaks(tmp_path / "absent", 127) == 1, (
        "the probe must FAIL when gitleaks did not run at all, not report success"
    )
    assert _run_probe_with_stub_gitleaks(tmp_path / "crash", 139) == 1, (
        "the probe must FAIL when the scanner crashed, not read the crash as a find"
    )


def test_step_fails_when_the_pre_fix_config_also_detects(tmp_path):
    """The anchor half: the probe is evidence only if it could have failed.

    `--exit-code 42` from the anchor means the config as it stood before #263 -
    the one with no rules at all - reported the probe secret. Then the probe
    above it would pass against that config too, and proves nothing. The step
    must go red rather than print a reassuring "scanner detected the known
    secret".
    """
    assert _run_probe_with_stub_gitleaks(tmp_path / "inert", 42, anchor_exit=42) == 1, (
        "a probe its own anchor also detects is not a control; the step must fail"
    )
    assert _run_probe_with_stub_gitleaks(tmp_path / "anchor-fatal", 42, anchor_exit=1) == 1, (
        "gitleaks failing on the anchor means the anchor did not run - not that it missed"
    )


# --------------------------------------------------------------------------- #
# The coverage probe (#246): the scanner has rules, but does it see the repo?
# --------------------------------------------------------------------------- #

MARKER = "CXPP-SECRET-SCAN-COVERAGE-MARKER-V1"


def test_coverage_probe_scans_the_repository_not_a_fixture() -> None:
    """Issue #246: the #263 probe scans /tmp, so no repo exclusion can affect it.

    Measured against zricethezav/gitleaks:v8.18.4: a targeted `tests/.*` path
    exclusion leaves the #263 probe green while a real AWS key planted in
    `tests/` reports "no leaks found". The coverage probe closes that by
    scanning the REPOSITORY with the production config, so the allowlist's path
    entries - which are matched relative to the scan root - actually apply.
    """
    probe = _pipeline()["steps"]["secret-scan"]["commands"][1]

    assert "--source ." in probe, (
        "the coverage probe must scan the repository; a fixture under /tmp cannot be "
        "affected by the path exclusions it exists to detect"
    )
    assert "--no-git" in probe, (
        "the expected set comes from `git grep` - the working tree - so the scan must "
        "read the working tree too. In git mode a pure rename reports the OLD path and "
        "a harmless `git mv` reads exactly like an allowlist exclusion"
    )
    assert "--config .gitleaks-coverage-probe.toml" in probe
    assert MARKER in probe, "the probe must look for the committed marker token"
    assert "--exit-code" in probe, "a find must land on a status nothing else uses"
    assert "git grep -l" in probe, (
        "the marked set must be DERIVED from the repository, not listed in the step - a "
        "listed set is one more thing to forget in the edit that adds an exclusion"
    )
    # An EXIT trap's last status becomes the script's, in BOTH directions.
    # Measured: unguarded, a cleanup that could not remove its scratch file
    # turned "no leaks found" into exit 1; guarded with `|| true`, the trap
    # swallowed a real `exit 1` and the probe stopped being able to fail.
    assert "trap " in probe, "the probe's scratch files must be removed on every exit path"
    assert "rc=$?" in probe and "exit $rc" in probe, (
        "the cleanup must hand back the status that triggered it - neither inventing a "
        "failure from a temp file's permissions nor swallowing a real one"
    )


def test_coverage_probe_config_extends_production_rather_than_replacing_it() -> None:
    """The probe must inherit the PRODUCTION allowlist, or it tests nothing.

    `[extend] path` inherits the extended config's rules, its own extend chain,
    and its allowlist - measured, and the last of those is the whole mechanism:
    if the path entries did not carry over, adding `tests/.*` to .gitleaks.toml
    would not affect this probe and it would stay green through exactly the
    change it exists to catch.
    """
    config = tomllib.loads(
        (REPO_ROOT / ".gitleaks-coverage-probe.toml").read_text(encoding="utf-8")
    )

    assert config["extend"]["path"] == ".gitleaks.toml"
    assert [r["regex"] for r in config["rules"]] == [MARKER], (
        "the marker rule belongs HERE and only here. In .gitleaks.toml it would report "
        "every marker on every real scan, and the only way to quieten that is an "
        "allowlist entry - the move this probe exists to detect"
    )
    assert config["allowlist"]["regexTarget"] == "match", (
        "regexTarget is not inherited through [extend] while the entries that depend on "
        "it are; without this the probe's allowlist behaves differently from production's"
    )


def _run_coverage_probe(
    tmp_path: Path,
    *,
    exit_code: int,
    reported: list[str],
    marked: bool = True,
    extra_marked: str | None = None,
) -> subprocess.CompletedProcess:
    """Execute the REAL coverage probe against a stub gitleaks.

    Behavioural, for the same reason as the probe test above: the textual
    assertions constrain the step's vocabulary, not its logic. A version of this
    loop that reported success on an empty report would satisfy every string
    check in `test_coverage_probe_scans_the_repository_not_a_fixture`.
    """
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    # Always present, always EXCLUDED from the marked set: gitleaks does not
    # scan the file passed as --config, so requiring it would fail every run.
    (repo / ".gitleaks-coverage-probe.toml").write_text(f"regex = '{MARKER}'\n")
    if marked:
        (repo / "marked.txt").write_text(f"{MARKER}\n")
        (repo / "sub" / "marked.txt").write_text(f"{MARKER}\n")
    if extra_marked is not None:
        (repo / extra_marked).write_text(f"{MARKER}\n")
    for args in (["init", "-q", "."], ["add", "-A"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    report = tmp_path / "report.json"
    report.write_text("[\n" + ",\n".join(f'  {{ "File": "{f}" }}' for f in reported) + "\n]\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "gitleaks"
    stub.write_text(
        "#!/bin/sh\n"
        'out=""; prev=""\n'
        'for a in "$@"; do [ "$prev" = "--report-path" ] && out="$a"; prev="$a"; done\n'
        f'[ -n "$out" ] && cp {report} "$out"\n'
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)

    probe = _pipeline()["steps"]["secret-scan"]["commands"][1]
    # The whole process, not just its status: two different failures both exit 1
    # here - "this path was not reported" and "this path cannot be compared" -
    # and a test that reads only the code cannot tell them apart.
    return subprocess.run(
        ["sh", "-c", probe],
        cwd=repo,
        # TMPDIR per scenario. The probe's scratch paths are otherwise shared
        # absolute ones, and a leftover report from another run is exactly what
        # the grep would read - reporting every marked path as unscanned for a
        # reason that has nothing to do with the scan.
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "TMPDIR": str(tmp_path)},
        capture_output=True,
        text=True,
    )


def test_coverage_probe_fails_when_a_marked_path_goes_unreported(tmp_path):
    """The whole point: an unscanned path must be loud, and silence is the default.

    Every scenario below is a state in which the repository scan itself would
    still print "no leaks found", which is why none of them can be detected by
    looking at the scan.
    """
    everything = [".gitleaks-coverage-probe.toml", "marked.txt", "sub/marked.txt"]

    assert _run_coverage_probe(tmp_path / "ok", exit_code=42, reported=everything).returncode == 0, (
        "every marked path reported - the probe must pass"
    )
    assert _run_coverage_probe(
        tmp_path / "excluded", exit_code=42, reported=[".gitleaks-coverage-probe.toml", "marked.txt"]
    ).returncode == 1, (
        "sub/marked.txt was not reported, which is what a `sub/.*` allowlist entry looks "
        "like from here; the probe must fail rather than pass on the two that were"
    )
    assert _run_coverage_probe(tmp_path / "silent", exit_code=0, reported=[]).returncode == 1, (
        "nothing reported at all - an over-broad allowlist regex suppresses the markers "
        "and every real finding with them"
    )
    assert _run_coverage_probe(tmp_path / "fatal", exit_code=1, reported=[]).returncode == 1, (
        "gitleaks failed; it did not scan, and that must not read as coverage"
    )
    # The report here says the scanner DID report the file, spelled the way
    # gitleaks actually spells it. Measured with the pinned image on a file named
    # `amp&ersand.txt`: the report carries "File": "amp\u0026ersand.txt" while
    # `git grep -l` prints `amp&ersand.txt`. So a literal match calls a reported
    # file unscanned - a limit of the probe dressed up as a security finding.
    #
    # Asserted on the MESSAGE, not the status: both outcomes exit 1, so an
    # exit-code assertion passes with or without the guard. The first version of
    # this scenario did exactly that and was vacuous.
    escaped = _run_coverage_probe(
        tmp_path / "escaped",
        exit_code=42,
        reported=everything + [r"amp\u0026ersand.txt"],
        extra_marked="amp&ersand.txt",
    )
    assert escaped.returncode == 1, "an uncomparable path must stop the probe, not be skipped"
    assert "cannot compare this path" in escaped.stderr, (
        "the probe must say the comparison is impossible. Reporting a file the scanner "
        "DID report as 'unscanned' sends someone to look for an allowlist entry that "
        "does not exist"
    )
    assert _run_coverage_probe(
        tmp_path / "unmarked", exit_code=42, reported=[".gitleaks-coverage-probe.toml"], marked=False
    ).returncode == 1, (
        "no markers in the repository at all. The loop would then have nothing to check "
        "and would pass by having had nothing to look at - the vacuous green this whole "
        "file exists to refuse"
    )
