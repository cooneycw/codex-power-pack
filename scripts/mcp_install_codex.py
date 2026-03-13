#!/usr/bin/env python3
"""Install/update Codex MCP registrations for codex-power-pack.

This script writes deterministic stdio registrations in `~/.codex/config.toml`
using repository-local service directories.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from mcp_common import canonical_servers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install Codex MCP config for codex-power-pack")
    parser.add_argument(
        "--codex-config",
        default=str(Path.home() / ".codex" / "config.toml"),
        help="Path to Codex config TOML",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path used to build --directory args",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing files")
    return parser


def _remove_mcp_sections(text: str, server_names: set[str]) -> str:
    """Remove existing `[mcp_servers.<name>]` and nested sections for selected names."""
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("[mcp_servers.") and stripped.endswith("]"):
            section_key = stripped[len("[mcp_servers.") : -1]
            section_base = section_key.split(".", 1)[0]
            if section_base in server_names:
                index += 1
                while index < len(lines):
                    next_stripped = lines[index].strip()
                    if next_stripped.startswith("[") and next_stripped.endswith("]"):
                        break
                    index += 1
                continue

        result.append(line)
        index += 1

    return "".join(result)


def _format_toml_array(values: list[str]) -> str:
    quoted = [json.dumps(value) for value in values]
    return "[" + ", ".join(quoted) + "]"


def _render_blocks(repo_root: Path) -> str:
    blocks: list[str] = []

    for spec in canonical_servers():
        service_dir = str((repo_root / spec.repo_subdir).resolve())
        args = ["run", "--directory", service_dir, "python", "src/server.py", "--stdio"]

        blocks.append(f"[mcp_servers.{spec.config_name}]")
        blocks.append('command = "uv"')
        blocks.append(f"args = {_format_toml_array(args)}")
        blocks.append("")

        if spec.config_name == "codex-woodpecker":
            blocks.append(f"[mcp_servers.{spec.config_name}.env]")
            blocks.append('AWS_REGION = "us-east-1"')
            blocks.append('AWS_SECRET_NAME = "codex-power-pack"')
            blocks.append('PYTHONUNBUFFERED = "1"')
            blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config_path = Path(args.codex_config).expanduser()
    repo_root = Path(args.repo_root).resolve()

    if not repo_root.exists():
        print(f"ERROR: repo root does not exist: {repo_root}")
        return 1

    canonical_names = {spec.config_name for spec in canonical_servers()}
    migration_aliases = {
        "second-opinion",
        "playwright-persistent",
        "nano-banana",
        "woodpecker-ci",
        "codex-woodpecker",  # ensures stale legacy block is replaced
    }

    names_to_replace = canonical_names | migration_aliases

    original_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    base_text = _remove_mcp_sections(original_text, names_to_replace).rstrip()
    rendered = _render_blocks(repo_root)

    new_text = (base_text + "\n\n" + rendered).lstrip("\n") if base_text else rendered

    print(f"Codex config target: {config_path}")
    print(f"Repo root: {repo_root}")
    print("Servers installed:")
    for name in sorted(canonical_names):
        print(f"- {name}")

    if args.dry_run:
        print("\nDRY RUN: no files written")
        return 0

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = config_path.with_suffix(config_path.suffix + f".bak.{timestamp}")
        backup_path.write_text(original_text, encoding="utf-8")
        print(f"Backup: {backup_path}")

    config_path.write_text(new_text, encoding="utf-8")
    print("Updated Codex MCP config.")
    print("Next step: run `make mcp-doctor`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
