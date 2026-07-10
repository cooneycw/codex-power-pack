"""Tests for Codex friction retro proposals (#96)."""

from pathlib import Path

from lib.friction.retro import _read_jsonl, analyze_events

REPO_ROOT = Path(__file__).resolve().parents[1]


def _event(summary: str, event_type: str = "gate_failure") -> dict[str, object]:
    return {
        "event_type": event_type,
        "summary": summary,
        "event_source": "codex-hook",
        "repo": "example/repo",
        "branch": "main",
        "severity": "error",
    }


def test_repeated_failure_proposes_a_validation_gate() -> None:
    proposals = analyze_events([_event("artifact contract missing"), _event("artifact contract missing")])

    proposal = next(item for item in proposals if item.kind == "validation-gate")
    assert proposal.evidence_count == 2
    assert "preflight" in proposal.action


def test_admin_bootstrap_dependency_proposes_blocking_reminder() -> None:
    proposals = analyze_events([_event("admin-only bootstrap apply is still required", "manual_intervention")])

    proposal = next(item for item in proposals if item.kind == "bootstrap-reminder")
    assert proposal.blocking is True
    assert "exits non-zero" in proposal.action


def test_retro_never_returns_secret_bearing_summary() -> None:
    proposals = analyze_events([
        _event("bootstrap blocked password=supersecret"),
        _event("bootstrap blocked password=supersecret"),
    ])

    rendered = "\n".join(f"{item.title}\n{item.action}" for item in proposals)
    assert "supersecret" not in rendered


def test_retro_normalizes_legacy_codex_jsonl_rows(tmp_path) -> None:
    queue = tmp_path / "friction.jsonl"
    queue.write_text(
        '\n'.join([
            '{"class":"gate-failure","signal":"artifact contract missing","step":"verify"}',
            '{"class":"gate-failure","signal":"artifact contract missing","step":"verify"}',
        ])
    )

    proposals = analyze_events(_read_jsonl(queue))
    assert any(item.kind == "validation-gate" for item in proposals)


def test_repeated_failure_class_proposes_gate_when_legacy_summaries_vary() -> None:
    proposals = analyze_events([
        _event("first volatile failure"),
        _event("second volatile failure"),
    ])

    proposal = next(item for item in proposals if item.kind == "validation-gate")
    assert proposal.evidence_count == 2


def test_retro_skill_uses_codex_queue_and_requires_confirmation() -> None:
    text = (REPO_ROOT / ".codex" / "skills" / "self-improvement-retro" / "SKILL.md").read_text()
    assert ".codex/friction.jsonl" in text
    assert "lib.friction.retro" in text
    assert "bootstrap-check" in text
    assert "explicit user confirmation" in text
