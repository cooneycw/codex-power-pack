#!/usr/bin/env python3
"""Install and diagnose Codex skill registrations for codex-power-pack.

Codex discovers reusable skills from ~/.codex/skills. This script links
repo-local skill packages from .codex/skills into that directory so workflows
resolve consistently from any working directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillTargetStatus:
    name: str
    source: Path
    target: Path
    status: str
    detail: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or diagnose Codex skill links for codex-power-pack"
    )
    parser.add_argument(
        "--repo-skills-dir",
        default=str(Path(__file__).resolve().parents[1] / ".codex" / "skills"),
        help="Path to repository-managed skill packages",
    )
    parser.add_argument(
        "--codex-skills-dir",
        default=str(Path.home() / ".codex" / "skills"),
        help="Target Codex skills directory",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Only report skill registration status; do not write files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace conflicting existing targets after writing a timestamped backup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned install actions without writing files",
    )
    return parser


def discover_repo_skills(repo_skills_dir: Path) -> list[Path]:
    if not repo_skills_dir.is_dir():
        return []
    return sorted(path for path in repo_skills_dir.iterdir() if (path / "SKILL.md").is_file())


def inspect_target(source: Path, target: Path) -> SkillTargetStatus:
    if not target.exists() and not target.is_symlink():
        return SkillTargetStatus(
            name=source.name,
            source=source,
            target=target,
            status="missing",
            detail="target does not exist",
        )

    if target.is_symlink():
        try:
            resolved = target.resolve()
        except OSError:
            return SkillTargetStatus(
                name=source.name,
                source=source,
                target=target,
                status="broken",
                detail="target is a broken symlink",
            )

        if resolved == source.resolve():
            return SkillTargetStatus(
                name=source.name,
                source=source,
                target=target,
                status="ok",
                detail="symlink points to repository skill package",
            )
        return SkillTargetStatus(
            name=source.name,
            source=source,
            target=target,
            status="drift",
            detail=f"symlink points elsewhere: {resolved}",
        )

    target_skill_file = target / "SKILL.md"
    if target_skill_file.is_file():
        if target_skill_file.read_text(encoding="utf-8") == (source / "SKILL.md").read_text(encoding="utf-8"):
            return SkillTargetStatus(
                name=source.name,
                source=source,
                target=target,
                status="copied",
                detail="directory exists with matching SKILL.md (not symlinked)",
            )
        return SkillTargetStatus(
            name=source.name,
            source=source,
            target=target,
            status="drift",
            detail="directory exists but SKILL.md content differs",
        )

    return SkillTargetStatus(
        name=source.name,
        source=source,
        target=target,
        status="drift",
        detail="target exists but is not a valid skill directory",
    )


def _backup_name(path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak.{stamp}")


def _install_one(
    source: Path,
    target: Path,
    *,
    overwrite: bool,
    dry_run: bool,
) -> SkillTargetStatus:
    current = inspect_target(source, target)
    if current.status in {"ok", "copied"}:
        return current

    if current.status in {"missing", "broken"}:
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                target.unlink()
            target.symlink_to(source)
        return SkillTargetStatus(
            name=source.name,
            source=source,
            target=target,
            status="installed",
            detail="created symlink to repository skill package",
        )

    if not overwrite:
        return SkillTargetStatus(
            name=source.name,
            source=source,
            target=target,
            status="conflict",
            detail=current.detail,
        )

    backup_target = _backup_name(target)
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.rename(backup_target)
        target.symlink_to(source)
    return SkillTargetStatus(
        name=source.name,
        source=source,
        target=target,
        status="replaced",
        detail=f"conflicting target backed up to {backup_target}",
    )


def run_doctor(repo_skills_dir: Path, codex_skills_dir: Path) -> int:
    repo_skills = discover_repo_skills(repo_skills_dir)
    if not repo_skills:
        print(f"ERROR: no skill packages found in {repo_skills_dir}")
        return 1

    print(f"Repository skills: {repo_skills_dir}")
    print(f"Codex skills dir:  {codex_skills_dir}")
    print("")

    statuses = [inspect_target(source, codex_skills_dir / source.name) for source in repo_skills]
    grouped: dict[str, list[SkillTargetStatus]] = {}
    for item in statuses:
        grouped.setdefault(item.status, []).append(item)

    for key in ("ok", "copied", "missing", "drift", "broken", "conflict"):
        if key not in grouped:
            continue
        print(f"{key.upper()} ({len(grouped[key])})")
        for item in grouped[key]:
            print(f"- {item.name}: {item.detail}")
        print("")

    unhealthy = {"missing", "drift", "broken", "conflict"}
    if any(grouped.get(state) for state in unhealthy):
        print("Doctor result: FAIL")
        print("Run: make skills-install-codex SKILLS_OVERWRITE=1")
        return 1

    print("Doctor result: PASS")
    return 0


def run_install(repo_skills_dir: Path, codex_skills_dir: Path, *, overwrite: bool, dry_run: bool) -> int:
    repo_skills = discover_repo_skills(repo_skills_dir)
    if not repo_skills:
        print(f"ERROR: no skill packages found in {repo_skills_dir}")
        return 1

    print(f"Repository skills: {repo_skills_dir}")
    print(f"Codex skills dir:  {codex_skills_dir}")
    print("")

    results: list[SkillTargetStatus] = []
    for source in repo_skills:
        target = codex_skills_dir / source.name
        result = _install_one(source, target, overwrite=overwrite, dry_run=dry_run)
        results.append(result)
        print(f"- {source.name}: {result.status} ({result.detail})")

    conflicts = [entry for entry in results if entry.status == "conflict"]
    if conflicts:
        print("")
        print("Install result: PARTIAL")
        print("Conflicts were left in place to avoid destructive changes.")
        print("Re-run with --overwrite to replace conflicting targets.")
        return 2

    print("")
    print("Install result: OK (dry run)" if dry_run else "Install result: OK")
    print("Next step: make skills-doctor")
    return 0


def main() -> int:
    args = build_parser().parse_args()

    repo_skills_dir = Path(args.repo_skills_dir).expanduser().resolve()
    codex_skills_dir = Path(args.codex_skills_dir).expanduser()

    if args.doctor:
        return run_doctor(repo_skills_dir, codex_skills_dir)
    return run_install(
        repo_skills_dir,
        codex_skills_dir,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
