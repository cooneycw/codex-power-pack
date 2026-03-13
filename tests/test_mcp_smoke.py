"""Unit tests for scripts/mcp_smoke.py argument handling."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_smoke import build_parser  # type: ignore[import-not-found]  # noqa: E402


def test_build_parser_defaults_to_sse_transport() -> None:
    args = build_parser().parse_args([])
    assert args.transport == "sse"


def test_build_parser_accepts_stdio_transport() -> None:
    args = build_parser().parse_args(["--transport", "stdio", "--profiles", "cicd"])
    assert args.transport == "stdio"
    assert args.profiles == "cicd"
