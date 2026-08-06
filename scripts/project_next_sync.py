#!/usr/bin/env python3
"""Generate or verify the project plugin's deterministic runtime bundle."""

from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PACKAGE = REPO_ROOT / "lib" / "project_next"
SOURCE_ENTRY = REPO_ROOT / "scripts" / "project-next.py"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "project"
TARGET_PACKAGE = PLUGIN_ROOT / "lib" / "project_next"
TARGET_ENTRY = PLUGIN_ROOT / "scripts" / "project-next.py"


def source_files() -> dict[Path, Path]:
    files = {TARGET_PACKAGE / path.name: path for path in SOURCE_PACKAGE.glob("*.py") if path.is_file()}
    files[TARGET_ENTRY] = SOURCE_ENTRY
    return files


def check() -> int:
    drift = [
        target.relative_to(REPO_ROOT).as_posix()
        for target, source in source_files().items()
        if not target.is_file() or not filecmp.cmp(source, target, shallow=False)
    ]
    expected = set(source_files())
    extras = sorted(
        path.relative_to(REPO_ROOT).as_posix() for path in TARGET_PACKAGE.glob("*.py") if path not in expected
    )
    if drift or extras:
        print("project-next runtime bundle drift detected:")
        for path in sorted(drift + extras):
            print(f"  {path}")
        print("Run: python3 scripts/project_next_sync.py --write")
        return 1
    print("project-next runtime bundle is current")
    return 0


def write() -> int:
    TARGET_PACKAGE.mkdir(parents=True, exist_ok=True)
    TARGET_ENTRY.parent.mkdir(parents=True, exist_ok=True)
    expected = set(source_files())
    for path in TARGET_PACKAGE.glob("*.py"):
        if path not in expected:
            path.unlink()
    for target, source in source_files().items():
        shutil.copy2(source, target)
    print(f"wrote {len(expected)} project-next runtime files")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    return check() if args.check else write()


if __name__ == "__main__":
    raise SystemExit(main())
