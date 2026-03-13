#!/usr/bin/env python3
"""Diagnose Codex MCP registration and endpoint health.

Checks:
1. Codex config drift (`~/.codex/config.toml`) for expected MCP server registrations.
2. Stale stdio `--directory` paths.
3. MCP initialize handshake against canonical SSE endpoints.

Exit codes:
- 0: all checks passed
- 2: endpoint unavailable
- 3: handshake/tools failure
- 4: config drift (missing server entries, stale stdio paths)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from mcp_common import (
    extract_directory_from_args,
    load_mcp_servers_from_toml,
    parse_profiles,
    probe_sse_server,
    selected_servers,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose MCP registration and connectivity")
    parser.add_argument(
        "--codex-config",
        default=str(Path.home() / ".codex" / "config.toml"),
        help="Path to Codex config TOML",
    )
    parser.add_argument(
        "--profiles",
        default="core browser cicd",
        help="Profiles to validate (space/comma separated): core browser cicd",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    profiles = parse_profiles(args.profiles)
    specs = selected_servers(profiles)
    expected_names = {spec.config_name for spec in specs}

    config_path = Path(args.codex_config).expanduser()
    config_servers = load_mcp_servers_from_toml(config_path)

    missing_servers: list[str] = []
    stale_stdio_paths: list[str] = []
    bad_stdio_paths: list[str] = []

    for name in sorted(expected_names):
        if name not in config_servers:
            missing_servers.append(name)
            continue

        args_value = config_servers[name].get("args")
        stdio_dir = extract_directory_from_args(args_value)
        if not stdio_dir:
            continue

        directory_path = Path(stdio_dir).expanduser()
        if not directory_path.exists():
            bad_stdio_paths.append(f"{name}: {stdio_dir}")
        if "voice-bot-acs/codex-power-pack/mcp-woodpecker-ci" in stdio_dir:
            stale_stdio_paths.append(f"{name}: {stdio_dir}")

    probe_results = [probe_sse_server(spec, check_tools_list=False) for spec in specs]

    payload = {
        "config_path": str(config_path),
        "profiles": sorted(profiles),
        "expected_servers": sorted(expected_names),
        "missing_servers": missing_servers,
        "bad_stdio_paths": bad_stdio_paths,
        "stale_stdio_paths": stale_stdio_paths,
        "probe_results": [asdict(result) for result in probe_results],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("MCP Doctor")
        print(f"- Codex config: {config_path}")
        print(f"- Profiles: {', '.join(sorted(profiles))}")

        if missing_servers:
            print("- Missing MCP registrations:")
            for name in missing_servers:
                print(f"  - {name}")

        if bad_stdio_paths:
            print("- Missing stdio directories:")
            for row in bad_stdio_paths:
                print(f"  - {row}")

        if stale_stdio_paths:
            print("- Legacy/stale registration paths:")
            for row in stale_stdio_paths:
                print(f"  - {row}")

        print("- Endpoint probes:")
        for result in probe_results:
            status = "PASS" if result.ok else "FAIL"
            detail = f"server={result.server_name or '-'} version={result.server_version or '-'}"
            if not result.ok:
                detail = f"stage={result.stage} error={result.error or 'unknown'}"
            print(f"  - [{status}] {result.config_name} {detail}")

    config_failed = bool(missing_servers or bad_stdio_paths or stale_stdio_paths)
    failed_results = [result for result in probe_results if not result.ok]

    if config_failed:
        return 4
    if any(result.stage == "endpoint" for result in failed_results):
        return 2
    if failed_results:
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
