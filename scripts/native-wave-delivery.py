#!/usr/bin/env python3
"""Explicit delivery operations. Detached notify cannot confirm a recipient receipt."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.native_wave.codex_transport import CodexTransport  # noqa: E402
from lib.native_wave.delivery import DeliveryService  # noqa: E402
from lib.native_wave.delivery_store import DeliveryStore  # noqa: E402
from lib.native_wave.delivery_types import DeliveryError, RuntimeBinding, encode  # noqa: E402
from lib.native_wave.identity import LinuxHostProcessProbe  # noqa: E402
from lib.native_wave.storage import SQLiteWaveStore, StoreConfig  # noqa: E402
from lib.native_wave.types import LocalIdentityContext, ThreadId  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--journal-id", help="required for every operation except explicit journal-create")
    parser.add_argument("--authority", type=Path)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("journal-create")
    issue = sub.add_parser("permit")
    issue.add_argument("--wave", required=True)
    issue.add_argument("--event", required=True)
    issue.add_argument("--role", required=True)
    issue.add_argument("--runtime", type=Path, required=True, help="JSON RuntimeBinding, never a thread alias")
    issue.add_argument("--deadline", type=int, required=True, help="absolute Unix seconds; max 900 seconds away")
    issue.add_argument("--max-attempts", type=int, default=3)
    pending = sub.add_parser("pending")
    pending.add_argument("--wave", required=True)
    pending.add_argument("--role", required=True)
    pending.add_argument("--after-sequence", type=int, default=0)
    pending.add_argument("--limit", type=int, default=100)
    for operation in ("fetch", "receipt", "status", "notify", "stop"):
        child = sub.add_parser(operation)
        child.add_argument("--permit", required=True)
        if operation == "receipt":
            child.add_argument("--fetch-token", required=True)
        if operation == "notify":
            child.add_argument("--codex", required=True, type=Path, help="absolute pinned executable")
    args = parser.parse_args()
    try:
        if args.operation == "journal-create":
            print(encode({"journal_id": DeliveryStore.create(args.journal).store_id}))
            return 0
        if not args.journal_id or not args.authority:
            raise DeliveryError("explicit journal-id and authority are required; missing journals are never recreated")
        journal = DeliveryStore.open(args.journal, args.journal_id)
        service = DeliveryService(SQLiteWaveStore.open(StoreConfig(args.authority)), journal, LinuxHostProcessProbe())
        # No native identity is manufactured for detached status/notify.
        context = None
        if args.operation not in {"notify", "status"}:
            context = LocalIdentityContext(ThreadId(UUID(os.environ.get("CODEX_THREAD_ID", ""))))
        result: object
        if args.operation == "notify":
            result = service.notify(args.permit, CodexTransport(args.codex))
        elif args.operation == "status":
            result = service.status(args.permit)
        elif args.operation == "permit":
            assert context is not None
            if args.runtime.stat().st_size > 16384:
                raise DeliveryError("runtime binding byte budget exceeded")
            runtime = RuntimeBinding(**json.loads(args.runtime.read_text()))
            permit = service.issue(args.wave, args.event, args.role, context, runtime,
                                   deadline=args.deadline, max_attempts=args.max_attempts)
            result = {"permit_id": permit.permit_id, "deadline": permit.deadline, "max_attempts": permit.max_attempts}
        elif args.operation == "pending":
            assert context is not None
            result = service.pending(args.wave, args.role, context,
                                     after_sequence=args.after_sequence, limit=args.limit)
        elif args.operation == "fetch":
            assert context is not None
            result = service.fetch(args.permit, context)
        elif args.operation == "receipt":
            assert context is not None
            result = service.receipt(args.permit, args.fetch_token, context)
        else:
            assert context is not None
            service.stop(args.permit, context)
            result = {"notification_stopped": True}
        print(encode(result))
        return 0
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        print(encode({"error": str(exc), "receipt_confirmed": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
