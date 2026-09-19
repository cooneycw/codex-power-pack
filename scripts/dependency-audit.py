#!/usr/bin/env python3
"""Audit owned dependency populations; 0=clean, 1=advisory, 2=unknown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: dependency-audit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.security import dependency_audit as core  # noqa: E402


def report(evidence: core.Evidence) -> None:
    print(f"dependency-audit: source={evidence.source} examined={len(evidence.packages)} "
          "scope=all-platform-registry-versions")
    if not evidence.packages:
        print("dependency-audit: explicitly dependency-free (no third-party runtime/dev packages)")
    for pin in evidence.packages:
        print(f"  examined {pin.name}=={pin.version}")
    for dep, vuln in evidence.findings:
        print(f"DEP-AUDIT-FINDING: {evidence.source} {dep['name']}=={dep['version']} {vuln['id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--from-capture", type=Path)
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.selftest:
            core.selftest(root)
            print("DEP-AUDIT-SELFTEST: known advisory detected; clean nonempty population examined")
            return 0
        if args.from_capture:
            evidence = core.replay(args.from_capture)
            report(evidence)
            return 1 if evidence.findings else 0
        sources = core.discover(root)
        excluded = core.excluded_manifests(root, sources)
        print("dependency-audit: verdict-scope=owned-locks-and-root-requirements; "
              "not whole-repository dependency coverage")
        for source in excluded:
            print(f"DEP-AUDIT-OUTSIDE-SCOPE: {source.relative_to(root)} (independent declaration; not audited)")
        print(f"dependency-audit: sources={len(sources)} discovery=owned-lock-walk "
              f"pruned={','.join(sorted(core.PRUNE))}")
        found = False
        for source in sources:
            evidence = core.audit(str(source.relative_to(root)), core.population(source), root)
            report(evidence)
            found |= bool(evidence.findings)
        return 1 if found else 0
    except core.Unknown as exc:
        print(f"DEP-AUDIT-UNKNOWN: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
