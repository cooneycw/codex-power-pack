"""Safety controls for the optional live Codex lane."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from lib.skill_eval.cases import load_suite
from lib.skill_eval.live import (
    _bounded_communicate,
    _explicit_unavailable,
    _safe_items,
    _tokens,
    redact,
    run_case,
)
from lib.skill_eval.naming import load_skill_families, normalize_selected_skill

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / ".agents" / "skill-evaluation-cases.json"


def test_live_lane_requires_explicit_acknowledgement() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "skill-eval.py"), "live", "--cases", str(CASES)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "--allow-live" in completed.stderr


def test_unavailable_codex_is_not_reported_as_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    suite = load_suite(CASES)
    case = next(case for case in suite.cases if "live" in {lane.value for lane in case.lanes})
    monkeypatch.setattr("lib.skill_eval.live.shutil.which", lambda _: None)

    observation = run_case(
        case,
        suite.live_controls,
        ROOT / ".agents" / "skill-evaluation-output.schema.json",
        load_skill_families(ROOT),
    )

    assert observation.available is False
    assert observation.runtime_error == "Codex CLI is unavailable"


def test_redaction_masks_credential_shapes() -> None:
    aws_key = "".join(("AKIA", "1234", "5678", "90AB", "CDEF"))

    assert "super-secret-value" not in redact("api_key=super-secret-value")
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in redact("token ghp_abcdefghijklmnopqrstuvwxyz")
    assert aws_key not in redact(aws_key)


def test_namespace_normalization_accepts_only_the_publishing_family() -> None:
    families = load_skill_families(ROOT)

    assert normalize_selected_skill("project:project-next", "project-next", families)[0] == "project-next"
    assert normalize_selected_skill("$PROJECT-NEXT", "project-next", families)[0] == "project-next"
    assert normalize_selected_skill("spec:project-next", "project-next", families)[0] == "spec:project-next"
    assert normalize_selected_skill("evil:project-next", "project-next", families)[0] == "evil:project-next"
    assert normalize_selected_skill("none", None, families)[0] is None


def test_token_accounting_uses_structured_usage_events() -> None:
    events = (Path(__file__).parent / "fixtures" / "codex-events.jsonl").read_bytes()
    assert _tokens(events) == 13655
    assert _tokens(b'{"text":"\\"total_tokens\\":999999"}\n') is None


def test_bounded_communicate_stops_excess_output_and_timeouts() -> None:
    noisy = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100000)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout, _, timed_out, exceeded = _bounded_communicate(noisy, 5, 1024)
    assert len(stdout) <= 1024
    assert timed_out is False
    assert exceeded is True

    sleepy = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    _, _, timed_out, _ = _bounded_communicate(sleepy, 1, 1024)
    assert timed_out is True


def test_model_authored_arrays_are_redacted_and_bounded() -> None:
    values = ["password=do-not-store", *(f"value-{index}" for index in range(40))]
    safe = _safe_items(values)
    assert len(safe) == 32
    assert all(len(value) <= 64 for value in safe)
    assert "do-not-store" not in safe[0]


def test_explicit_only_case_is_unavailable_when_exec_cannot_attach_it() -> None:
    suite = load_suite(CASES)
    explicit = next(case for case in suite.cases if case.case_id == "CASE-009")
    implicit = next(case for case in suite.cases if case.case_id == "CASE-001")

    assert _explicit_unavailable(explicit, None) is True
    assert _explicit_unavailable(explicit, "project-init") is False
    assert _explicit_unavailable(implicit, None) is False
