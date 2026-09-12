#!/usr/bin/env python3
"""Opt-in disposable preflight. No session launch, resume, queue, receipt, or fallback.

This is tooling for a separately approved experiment, not native live acceptance.
The inspected 0.154.0 protocol cannot yet establish the required current permissions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lib.native_wave.codex_transport import CodexTransport  # noqa: E402
from lib.native_wave.delivery import DeliveryService  # noqa: E402
from lib.native_wave.delivery_store import DeliveryStore  # noqa: E402
from lib.native_wave.delivery_types import DeliveryError, encode  # noqa: E402
from lib.native_wave.identity import LinuxHostProcessProbe  # noqa: E402
from lib.native_wave.storage import SQLiteWaveStore, StoreConfig  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--permit", required=True)
    parser.add_argument("--codex", required=True, type=Path)
    parser.add_argument("--approved-preflight", action="store_true", required=True,
                        help="attests the separately judged exact experiment; not a permission override")
    args = parser.parse_args()
    try:
        root = args.manifest.resolve().parent
        info = root.lstat()
        if (not root.name.startswith("cxpp-delivery-206-") or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise DeliveryError("fresh private disposable run root required")
        if args.manifest.stat().st_size > 16384:
            raise DeliveryError("manifest byte budget exceeded")
        manifest = json.loads(args.manifest.read_text())
        if not 0 <= time.time() - manifest["created_at"] < 900:
            raise DeliveryError("experiment deadline exceeded")
        participants = manifest["fresh_participants"]
        if not isinstance(participants, list) or not 1 <= len(participants) <= 3:
            raise DeliveryError("at most three separately launched disposable participants")
        if any(str(UUID(value)) != value for value in participants):
            raise DeliveryError("participant UUID required")
        # The manifest is a same-user experiment declaration, not evidence of native freshness.
        authority = SQLiteWaveStore.open(StoreConfig(root / "wave.sqlite3"))
        journal = DeliveryStore.open(root / "delivery.sqlite3", manifest["journal_id"])
        service = DeliveryService(authority, journal, LinuxHostProcessProbe())
        permit, _ = journal.read(args.permit)
        if permit.issuer_thread not in participants or permit.recipient_thread not in participants:
            raise DeliveryError("permit outside experiment participant allowlist")
        snapshot = service._validate(permit)
        observed = CodexTransport(args.codex).inspect(permit.runtime, permit.recipient_thread, snapshot.capability)
        result = {"case": "native-preflight", "runtime_version": permit.runtime.cli_version,
                  "state": observed.state, "detail": observed.detail, "live_acceptance": False,
                  "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "receipt_confirmed": service.status(args.permit)["receipt_confirmed"],
                  "queue_calls": 0, "session_launches": 0}
        print(encode(result))
        return 2  # Preflight never substitutes for an independent recipient live acceptance run.
    except (RuntimeError, OSError, ValueError, TypeError, KeyError) as exc:
        print(encode({"case": "native-preflight", "error": str(exc), "live_acceptance": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
