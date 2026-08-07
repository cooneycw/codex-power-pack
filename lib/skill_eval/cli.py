"""CLI for deterministic checks, bounded live runs, and safe scorecards."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

from .cases import CaseError, filter_cases, load_suite
from .deterministic import observe
from .evaluate import evaluate_observation, score_results
from .live import run_case
from .models import Category, EvaluationCase, EvaluationResult, EvaluationSuite, Lane, Outcome
from .naming import load_skill_families

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cases", type=Path, default=Path(".agents/skill-evaluation-cases.json"))
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--skill", action="append", default=[])
    parser.add_argument("--category", action="append", choices=[item.value for item in Category], default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--output", type=Path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Codex skill activation and outcome contracts")
    commands = parser.add_subparsers(dest="command", required=True)
    deterministic = commands.add_parser("deterministic", help="run no-network repository-backed checks")
    _common(deterministic)
    live = commands.add_parser("live", help="run explicitly enabled bounded Codex evaluations")
    _common(live)
    live.add_argument("--allow-live", action="store_true", help="required acknowledgement for model-backed runs")
    live.add_argument("--max-cases", type=int)
    live.add_argument("--timeout", type=int)
    live.add_argument("--max-total-tokens", type=int)
    live.add_argument("--model")
    live.add_argument(
        "--output-schema", type=Path, default=Path(".agents/skill-evaluation-output.schema.json")
    )
    return parser


def _selection(args: argparse.Namespace, suite: EvaluationSuite, lane: Lane) -> tuple[EvaluationCase, ...]:
    return filter_cases(
        suite.cases,
        lane=lane,
        case_ids=set(args.case),
        skills=set(args.skill),
        categories={Category(value) for value in args.category},
        tags=set(args.tag),
    )


def _payload(
    suite: EvaluationSuite,
    lane: Lane,
    results: list[EvaluationResult],
    **metadata: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "suite": suite.suite_id,
        "lane": lane.value,
        "generated_at": datetime.now(UTC).isoformat(),
        "results": [result.to_dict() for result in results],
        "score": score_results(results, suite.thresholds),
    }
    payload.update(metadata)
    return payload


def _emit(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def _prune(directory: Path, retention_days: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for path in directory.glob("skill-eval-live-*.json"):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            if modified < cutoff:
                path.unlink()
        except OSError:
            continue


def _provenance(root: Path) -> dict[str, str | None]:
    codex = shutil.which("codex")

    def command(*argv: str) -> str | None:
        try:
            completed = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout.strip() if completed.returncode == 0 else None

    policy = json.loads((root / ".agents" / "skill-invocation-policy.json").read_text(encoding="utf-8"))
    return {
        "codex_version": command(codex, "--version") if codex else None,
        "source_commit": command("git", "rev-parse", "HEAD"),
        "payload_version": str(policy["payload_version"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        suite = load_suite(args.cases.resolve())
        root = REPOSITORY_ROOT
        lane = Lane.DETERMINISTIC if args.command == "deterministic" else Lane.LIVE
        cases = _selection(args, suite, lane)
        if not cases:
            raise CaseError("filters selected zero evaluation cases")

        results: list[EvaluationResult] = []
        metadata: dict[str, object] = {}
        output = args.output
        if lane is Lane.DETERMINISTIC:
            for case in cases:
                results.append(evaluate_observation(case, observe(case, root), lane))
        else:
            if not args.allow_live:
                raise CaseError("live evaluations require --allow-live")
            maximum = suite.live_controls.max_cases
            if args.max_cases is not None:
                if args.max_cases < 1:
                    raise CaseError("--max-cases must be positive")
                maximum = min(maximum, args.max_cases)
            cases = cases[:maximum]
            controls = suite.live_controls
            if args.timeout is not None:
                if args.timeout < 1 or args.timeout > controls.timeout_seconds:
                    raise CaseError(f"--timeout must be between 1 and {controls.timeout_seconds}")
                controls = type(controls)(**{**controls.__dict__, "timeout_seconds": args.timeout})
            token_budget = (
                controls.max_total_tokens if args.max_total_tokens is None else args.max_total_tokens
            )
            if token_budget < 1 or token_budget > controls.max_total_tokens:
                raise CaseError(f"--max-total-tokens must be between 1 and {controls.max_total_tokens}")
            consumed = 0
            budget_exhausted = False
            budget_unverified = False
            skill_families = load_skill_families(root)
            reserve = max(1000, controls.max_total_tokens // controls.max_cases)
            for case in cases:
                estimate = max(reserve, consumed // len(results)) if results else reserve
                if consumed + estimate > token_budget:
                    budget_exhausted = True
                    break
                observation = run_case(
                    case,
                    controls,
                    args.output_schema.resolve(),
                    skill_families,
                    model=args.model,
                )
                results.append(evaluate_observation(case, observation, lane))
                if observation.total_tokens is None:
                    budget_unverified = True
                    break
                consumed += observation.total_tokens
            artifact_dir = root / ".codex" / "evaluations"
            _prune(artifact_dir, controls.retention_days)
            if output is None:
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                output = artifact_dir / f"skill-eval-live-{stamp}.json"
            metadata = {
                "budget": {
                    "max_total_tokens": token_budget,
                    "consumed_tokens": consumed,
                    "exhausted": budget_exhausted,
                    "unverified": budget_unverified,
                    "selected_cases": len(cases),
                    "completed_cases": len(results),
                },
                "provenance": _provenance(root),
            }

        payload = _payload(suite, lane, results, **metadata)
        _emit(payload, output)
        failed = any(result.outcome not in {Outcome.PASS, Outcome.UNAVAILABLE} for result in results)
        unavailable = lane is Lane.LIVE and (
            not results or all(result.outcome is Outcome.UNAVAILABLE for result in results)
        )
        if failed:
            return 1
        return 3 if unavailable else 0
    except (CaseError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"skill-eval: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
