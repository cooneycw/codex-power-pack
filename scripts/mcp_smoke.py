#!/usr/bin/env python3
"""Run MCP smoke checks against Codex Power Pack transports.

Exit codes:
- 0: all checks passed
- 2: transport endpoint unavailable (SSE connection or stdio launch failure)
- 3: handshake/tools failure (SSE)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from mcp_common import parse_profiles, probe_sse_server, probe_stdio_server, selected_servers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MCP smoke tests (SSE and/or stdio)")
    parser.add_argument(
        "--profiles",
        default="core",
        help="Profiles to probe (space/comma separated): core browser cicd",
    )
    parser.add_argument(
        "--tools-list",
        action="store_true",
        help="Also run JSON-RPC tools/list after initialize",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio", "both"],
        default="sse",
        help="Transport to validate (default: sse)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    profiles = parse_profiles(args.profiles)
    specs = selected_servers(profiles)

    if not specs:
        print("No MCP servers selected for profiles:", ", ".join(sorted(profiles)))
        return 0

    results = []
    if args.transport in {"sse", "both"}:
        results.extend(probe_sse_server(spec, check_tools_list=args.tools_list) for spec in specs)
    if args.transport in {"stdio", "both"}:
        results.extend(probe_stdio_server(spec) for spec in specs)

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        print("MCP Smoke Results")
        for result in results:
            status = "PASS" if result.ok else "FAIL"
            target = result.sse_url
            if result.sse_url.startswith("stdio://"):
                target = result.endpoint or result.sse_url
            detail = f"server={result.server_name or '-'} version={result.server_version or '-'}"
            if not result.ok:
                detail = f"stage={result.stage} error={result.error or 'unknown'}"
            print(f"- [{status}] {result.config_name} ({target}) {detail}")

    if all(result.ok for result in results):
        return 0

    if any(result.stage == "endpoint" for result in results if not result.ok):
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
