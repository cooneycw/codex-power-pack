#!/usr/bin/env python3
"""Keep already-reviewed plugin hook roots usable during CxPP transitions."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

HOOK_FAMILIES = frozenset({"secrets", "self-improvement"})
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class TransitionError(RuntimeError):
    """A transition could not preserve its trusted hook roots."""


@dataclass(frozen=True)
class Snapshot:
    family: str
    version: str
    original: Path
    retained: Path
    digest: str


def tree_digest(root: Path) -> str:
    """Hash names, types, modes, link targets, and file bytes deterministically."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        stat = path.lstat()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(f"{stat.st_mode:o}".encode("ascii") + b"\0")
        if path.is_symlink():
            digest.update(b"link\0" + os.readlink(path).encode("utf-8") + b"\0")
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif path.is_dir():
            digest.update(b"dir\0")
        else:
            raise TransitionError(f"unsupported cache entry type: {path}")
    return digest.hexdigest()


def validated_name(value: str, label: str) -> str:
    if not SAFE_NAME.fullmatch(value):
        raise TransitionError(f"invalid {label}: {value!r}")
    return value


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def cache_root(codex_home: Path, marketplace: str) -> Path:
    return codex_home / "plugins" / "cache" / marketplace


def retention_root(codex_home: Path, marketplace: str) -> Path:
    return codex_home / "plugins" / ".cxpp-hook-retention" / marketplace


def copy_atomically(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.cxpp-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, temporary, symlinks=True)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def discover_roots(root: Path, families: list[str]) -> list[tuple[str, Path]]:
    discovered: list[tuple[str, Path]] = []
    for family in families:
        if family not in HOOK_FAMILIES:
            continue
        family_root = root / family
        if not family_root.is_dir():
            continue
        for version_root in sorted(family_root.iterdir()):
            if version_root.is_dir() and not version_root.is_symlink():
                validated_name(version_root.name, "plugin version")
                discovered.append((family, version_root))
    return discovered


def create_snapshots(root: Path, retained_root: Path, families: list[str]) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    for family, original in discover_roots(root, families):
        retained = retained_root / family / original.name
        expected = tree_digest(original)
        if retained.exists():
            if not retained.is_dir() or tree_digest(retained) != expected:
                raise TransitionError(
                    f"conflicting recovery snapshot for {family}/{original.name}; run recover before retrying"
                )
        else:
            copy_atomically(original, retained)
        if tree_digest(retained) != expected:
            raise TransitionError(f"snapshot verification failed for {family}/{original.name}")
        snapshots.append(Snapshot(family, original.name, original, retained, expected))
    return snapshots


def restore_snapshot(snapshot: Snapshot) -> bool:
    """Restore one trusted root; return whether changed bytes occupied its path."""
    collision = False
    quarantine: Path | None = None
    if snapshot.original.exists():
        if not snapshot.original.is_dir() or tree_digest(snapshot.original) != snapshot.digest:
            collision = True
            quarantine = snapshot.original.parent / f".{snapshot.original.name}.cxpp-replaced-{uuid.uuid4().hex}"
            os.replace(snapshot.original, quarantine)
        else:
            return collision
    try:
        copy_atomically(snapshot.retained, snapshot.original)
        if tree_digest(snapshot.original) != snapshot.digest:
            raise TransitionError(f"restored digest mismatch for {snapshot.family}/{snapshot.version}")
    except Exception:
        if quarantine is not None and quarantine.exists() and not snapshot.original.exists():
            os.replace(quarantine, snapshot.original)
        raise
    if quarantine is not None and quarantine.exists():
        shutil.rmtree(quarantine)
    return collision


def remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def restore_all(snapshots: list[Snapshot], retained_root: Path) -> bool:
    collision = False
    failures: list[str] = []
    for snapshot in snapshots:
        try:
            collision = restore_snapshot(snapshot) or collision
            shutil.rmtree(snapshot.retained)
            remove_empty_parents(snapshot.retained.parent, retained_root)
        except Exception as exc:  # Preserve every remaining snapshot for external recovery.
            failures.append(f"{snapshot.family}/{snapshot.version}: {exc}")
    if failures:
        raise TransitionError("restoration failed; run recover from an external terminal: " + "; ".join(failures))
    return collision


def residual_snapshots(retained_root: Path) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    if not retained_root.is_dir():
        return snapshots
    for family_root in sorted(retained_root.iterdir()):
        if not family_root.is_dir() or family_root.name not in HOOK_FAMILIES:
            continue
        for retained in sorted(family_root.iterdir()):
            if not retained.is_dir() or retained.is_symlink():
                continue
            validated_name(retained.name, "plugin version")
            original = retained_root.parent.parent / "cache" / retained_root.name / family_root.name / retained.name
            snapshots.append(
                Snapshot(family_root.name, retained.name, original, retained, tree_digest(retained))
            )
    return snapshots


def reinstall(args: argparse.Namespace, codex_home: Path, retained_root: Path) -> int:
    if not args.approve:
        raise TransitionError("explicit --approve is required after reviewing the cxpp-update preview")
    if residual_snapshots(retained_root):
        raise TransitionError("unfinished hook recovery snapshots exist; run recover before reinstalling")

    root = cache_root(codex_home, args.marketplace)
    snapshots = create_snapshots(root, retained_root, args.family)
    command_failure = 0
    collision = False

    def interrupt(signum: int, _frame: object) -> None:
        raise InterruptedError(f"received signal {signum}")

    prior_handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
    for signum in prior_handlers:
        signal.signal(signum, interrupt)
    try:
        child_env = {**os.environ, "CODEX_HOME": str(codex_home)}
        for family in args.family:
            completed = subprocess.run(
                [args.codex_bin, "plugin", "add", f"{family}@{args.marketplace}", "--json"],
                check=False,
                env=child_env,
            )
            if completed.returncode != 0:
                command_failure = completed.returncode
                break
    except (OSError, InterruptedError) as exc:
        print(f"plugin reinstall interrupted: {exc}", file=sys.stderr)
        command_failure = 1
    finally:
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)
        collision = restore_all(snapshots, retained_root)

    if collision:
        raise TransitionError(
            "a plugin reused an existing version path with changed bytes; "
            "trusted bytes were restored and the update was rejected"
        )
    if command_failure:
        print("plugin reinstall failed; retained hook roots were restored", file=sys.stderr)
        return command_failure
    print(f"updated: {len(args.family)} plugin(s); retained {len(snapshots)} reviewed hook root(s)")
    return 0


def recover(args: argparse.Namespace, retained_root: Path) -> int:
    if not args.approve:
        raise TransitionError("explicit --approve is required after reviewing recovery preflight")
    snapshots = residual_snapshots(retained_root)
    collision = restore_all(snapshots, retained_root)
    if collision:
        raise TransitionError("recovery found changed bytes at a trusted path; original reviewed bytes were restored")
    print(f"recovered: {len(snapshots)} hook root(s)")
    return 0


def preflight(args: argparse.Namespace, codex_home: Path, retained_root: Path) -> int:
    selected = [family for family in args.family if family in HOOK_FAMILIES]
    roots = discover_roots(cache_root(codex_home, args.marketplace), selected)
    residual = residual_snapshots(retained_root)
    print("hook-bearing families: " + (", ".join(selected) if selected else "none"))
    print(f"reviewed roots to retain: {len(roots)}")
    print(f"unfinished recovery snapshots: {len(residual)}")
    return 2 if residual else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("preflight", "reinstall", "recover"))
    parser.add_argument("--codex-home", type=Path, default=default_codex_home())
    parser.add_argument("--marketplace", default="codex-power-pack")
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    args.marketplace = validated_name(args.marketplace, "marketplace")
    args.family = list(dict.fromkeys(validated_name(family, "plugin family") for family in args.family))
    if args.operation in {"preflight", "reinstall"} and not args.family:
        parser.error("at least one --family is required")
    return args


def main() -> int:
    try:
        args = parse_args()
        codex_home = args.codex_home.expanduser().resolve()
        retained = retention_root(codex_home, args.marketplace)
        if args.operation == "preflight":
            return preflight(args, codex_home, retained)
        if args.operation == "reinstall":
            return reinstall(args, codex_home, retained)
        return recover(args, retained)
    except TransitionError as exc:
        print(f"cxpp hook transition stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
