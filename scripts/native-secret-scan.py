#!/usr/bin/env python3
"""Native secret scan only: not history or the other security modules.

Exit 0 = examined source, no unexcepted native findings; 1 = finding;
2 = invalid input/policy or no source files examined. No raw matches printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.security.modules.secrets import scan  # noqa: E402

#: NEGATIVE-CONTROL: native-secret-fixture-scope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print("native-secret-scan: UNKNOWN - root is not a directory", file=sys.stderr)
        return 2
    try:
        result = scan(str(args.root))
    except Exception:
        # A crash is UNKNOWN, never a detection. Exception text may contain input.
        print("native-secret-scan: UNKNOWN - scanner execution failed", file=sys.stderr)
        return 2
    for summary in result.passed:
        print(summary)
    for finding in result.findings:
        print(f"native-secret-scan: finding {finding.id} at {finding.location}")
    if result.errors or result.skipped or any(f.id == "INVALID_FIXTURE_POLICY" for f in result.findings):
        print("native-secret-scan: UNKNOWN - incomplete scan or invalid policy", file=sys.stderr)
        return 2
    return 1 if result.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
