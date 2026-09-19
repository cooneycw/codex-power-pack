#!/usr/bin/env python3
"""Synthetic blind anchor: widen exact exceptions into whole-file exclusions.

Not a historical revision. Deliberately mutate ONLY the exception matcher,
then execute the current real scanner/CLI. The control must reject this mutant.
"""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lib.security.fixture_policy import FixturePolicy  # noqa: E402


def path_only(self: FixturePolicy, relative: str, finding_id: str, matched: str) -> bool:
    return any(entry[0] == relative for entry in self.entries)


FixturePolicy.matches = path_only  # type: ignore[method-assign]
runpy.run_path(str(ROOT / "scripts/native-secret-scan.py"), run_name="__main__")
