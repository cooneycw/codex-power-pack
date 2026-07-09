"""CLI for the Codex friction writer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .hooks import event_from_hook_payload, load_payload
from .models import FrictionEventError
from .writer import FrictionWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lib.friction",
        description="Codex friction telemetry writer",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="record a minimized friction event")
    record.add_argument("--event-type", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--event-source")
    record.add_argument("--severity", default="warning")
    record.add_argument("--repo")
    record.add_argument("--branch")
    record.add_argument("--issue")
    _writer_args(record)

    hook = sub.add_parser("hook", help="read a Codex hook payload from stdin")
    hook.add_argument("--event", required=True, help="Codex hook event name")
    hook.add_argument(
        "--print-result",
        action="store_true",
        help="print the write result; hooks stay silent by default",
    )
    _writer_args(hook)

    return parser


def _writer_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cpp-memory-cmd",
        help="override cpp-memory command, e.g. 'python -m lib.cpp_memory'",
    )
    parser.add_argument("--queue", type=Path, help="optional masked local queue path")
    parser.add_argument("--cwd", type=Path, help="working directory for cpp-memory")
    parser.add_argument("--timeout", type=int, default=10)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    writer = FrictionWriter(
        command=args.cpp_memory_cmd,
        queue_path=args.queue,
        cwd=args.cwd,
        timeout=args.timeout,
    )

    try:
        if args.command == "record":
            result = writer.write({
                "event_type": args.event_type,
                "summary": args.summary,
                "event_source": args.event_source,
                "severity": args.severity,
                "repo": args.repo,
                "branch": args.branch,
                "issue": args.issue,
            })
            print(json.dumps(result.public_dict(), sort_keys=True))
            return 0

        if args.command == "hook":
            payload = load_payload(sys.stdin.read())
            event = event_from_hook_payload(args.event, payload)
            if event is None:
                if args.print_result:
                    print(json.dumps({"ok": True, "stored": "none"}))
                return 0
            result = writer.write(event)
            if args.print_result:
                print(json.dumps(result.public_dict(), sort_keys=True))
            return 0
    except FrictionEventError as exc:
        print(json.dumps({"ok": False, "stored": "rejected", "reason": str(exc)}), file=sys.stderr)
        return 2

    return 1
