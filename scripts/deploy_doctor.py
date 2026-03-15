#!/usr/bin/env python3
"""Diagnose deploy path drift between host-managed artifacts and repo-owned scripts."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_UNIT_PATHS = (
    Path("/etc/systemd/system/woodpecker-bootstrap.service"),
    Path.home() / ".config/systemd/user/woodpecker-bootstrap.service",
    Path("/etc/systemd/system/cloudflared.service"),
    Path.home() / ".config/systemd/user/cloudflared.service",
)

DEFAULT_WRAPPER_PATHS = (
    Path("/usr/local/bin/cpp-deploy-mcp"),
    Path("/usr/local/bin/codex-power-pack-deploy"),
    Path("/usr/local/bin/deploy-mcp"),
)

PROVISIONING_ONLY_UNITS = {"woodpecker-bootstrap.service", "cloudflared.service"}
RUNTIME_MARKERS = (
    "make deploy",
    "docker compose",
    "deploy-mcp",
    "cpp-deploy-mcp",
    "deploy_mcp.sh",
    "mcp-smoke",
    "up -d --build",
    "up -d --wait",
)


@dataclass
class ArtifactStatus:
    kind: str
    path: str
    status: str
    detail: str
    command: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose deploy/runtime drift")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to the repository root (default: current directory)",
    )
    parser.add_argument(
        "--unit-path",
        action="append",
        default=[],
        help="Additional systemd unit file paths to inspect",
    )
    parser.add_argument(
        "--wrapper-path",
        action="append",
        default=[],
        help="Additional host wrapper paths to inspect",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    return parser


def parse_execstart(text: str) -> list[str]:
    commands: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ExecStart="):
            commands.append(stripped.split("=", 1)[1].strip())
    return commands


def contains_runtime_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in RUNTIME_MARKERS)


def is_repo_owned_command(command: str, repo_root: Path) -> bool:
    normalized = command.replace("\\", "/")
    return str(repo_root) in normalized or "scripts/deploy_mcp.sh" in normalized


def inspect_repo_artifact(path: Path, detail: str) -> ArtifactStatus:
    if path.exists():
        return ArtifactStatus(kind="repo-artifact", path=str(path), status="ok", detail=detail)
    return ArtifactStatus(kind="repo-artifact", path=str(path), status="drift", detail=f"Missing {detail}")


def inspect_unit(path: Path, repo_root: Path) -> ArtifactStatus:
    if not path.exists():
        return ArtifactStatus(kind="systemd-unit", path=str(path), status="missing", detail="Not present")

    text = path.read_text(encoding="utf-8", errors="ignore")
    commands = parse_execstart(text)
    if not commands:
        return ArtifactStatus(kind="systemd-unit", path=str(path), status="warning", detail="No ExecStart found")

    drift_messages: list[str] = []
    repo_owned_commands = [cmd for cmd in commands if is_repo_owned_command(cmd, repo_root)]

    for command in commands:
        runtime = contains_runtime_marker(command)
        repo_owned = is_repo_owned_command(command, repo_root)

        if path.name in PROVISIONING_ONLY_UNITS:
            if runtime and not repo_owned:
                drift_messages.append(f"Provisioning-only unit runs runtime command: {command}")
            continue

        if runtime and not repo_owned:
            drift_messages.append(f"Runtime command is outside repo checkout: {command}")

    if drift_messages:
        return ArtifactStatus(
            kind="systemd-unit",
            path=str(path),
            status="drift",
            detail="; ".join(drift_messages),
            command="; ".join(commands),
        )

    if path.name in PROVISIONING_ONLY_UNITS:
        detail = "Provisioning-only unit"
    elif repo_owned_commands:
        detail = "Runtime unit points at repo-owned entrypoint"
    else:
        detail = "No deploy runtime commands detected"

    return ArtifactStatus(
        kind="systemd-unit",
        path=str(path),
        status="ok",
        detail=detail,
        command="; ".join(commands),
    )


def inspect_wrapper(path: Path, repo_root: Path, canonical_entrypoint: Path) -> ArtifactStatus:
    if not path.exists():
        return ArtifactStatus(kind="host-wrapper", path=str(path), status="missing", detail="Not present")

    if path.is_symlink():
        target = path.resolve()
        if target == canonical_entrypoint:
            return ArtifactStatus(kind="host-wrapper", path=str(path), status="ok", detail=f"Symlink to {target}")
        return ArtifactStatus(
            kind="host-wrapper",
            path=str(path),
            status="drift",
            detail=f"Symlink points to {target}, expected {canonical_entrypoint}",
        )

    text = path.read_text(encoding="utf-8", errors="ignore")
    if str(repo_root) in text and "scripts/deploy_mcp.sh" in text:
        return ArtifactStatus(
            kind="host-wrapper",
            path=str(path),
            status="ok",
            detail="Wrapper delegates to repo-owned deploy script",
        )

    if contains_runtime_marker(text):
        return ArtifactStatus(
            kind="host-wrapper",
            path=str(path),
            status="drift",
            detail="Wrapper contains runtime deploy logic outside the repo checkout",
        )

    return ArtifactStatus(
        kind="host-wrapper",
        path=str(path),
        status="warning",
        detail="Wrapper exists but no deploy runtime markers were detected",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    canonical_entrypoint = repo_root / "scripts" / "deploy_mcp.sh"
    bootstrap_script = repo_root / "woodpecker" / "bootstrap-secrets.py"

    unit_paths = [Path(value).expanduser() for value in args.unit_path] or list(DEFAULT_UNIT_PATHS)
    wrapper_paths = [Path(value).expanduser() for value in args.wrapper_path] or list(DEFAULT_WRAPPER_PATHS)

    artifacts = [
        inspect_repo_artifact(canonical_entrypoint, "canonical deploy entrypoint"),
        inspect_repo_artifact(bootstrap_script, "bootstrap secrets helper"),
    ]
    artifacts.extend(inspect_unit(path, repo_root) for path in unit_paths)
    artifacts.extend(inspect_wrapper(path, repo_root, canonical_entrypoint) for path in wrapper_paths)

    payload = {
        "repo_root": str(repo_root),
        "canonical_entrypoint": str(canonical_entrypoint),
        "artifacts": [asdict(artifact) for artifact in artifacts],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Deploy Doctor")
        print(f"- Repo root: {repo_root}")
        print(f"- Canonical runtime entrypoint: {canonical_entrypoint}")
        for artifact in artifacts:
            status = artifact.status.upper()
            print(f"- [{status}] {artifact.kind} {artifact.path}: {artifact.detail}")
            if artifact.command:
                print(f"    ExecStart: {artifact.command}")

    if any(artifact.status == "drift" for artifact in artifacts):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
