"""Semantic compatibility gate coverage."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "skill_contract_lint.py"
_spec = importlib.util.spec_from_file_location("skill_contract_lint", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
skill_lint = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = skill_lint
_spec.loader.exec_module(skill_lint)


def test_repository_passes_semantic_skill_contract() -> None:
    assert skill_lint.lint_contract(today=date(2026, 8, 6)) == []
    assert skill_lint.run_check() == 0


def test_reviewed_exclusions_expire_loudly() -> None:
    findings = skill_lint.lint_contract(today=date(2027, 4, 1))

    expired = [finding for finding in findings if finding.rule == "expired-exclusion"]
    assert len(expired) == 10
    assert {finding.subject for finding in expired} >= {"flow-repair", "browser-help", "cpp-help"}


def test_contract_has_no_unresolved_operational_reference() -> None:
    contract = skill_lint._baseline_module().build_contract()

    assert not [item for item in contract["references"] if item["classification"] == "unexplained"]
    assert {item["classification"] for item in contract["references"]} >= {
        "resolvable",
        "adapted",
        "excluded",
        "source_context",
    }
