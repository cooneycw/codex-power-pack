"""Documentation checks for MCP endpoint/transport consistency."""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def test_no_910x_mcp_endpoint_examples_in_codex_docs() -> None:
    files = [
        "README.md",
        "codex-second-opinion/README.md",
        "codex-playwright/README.md",
        "codex-nano-banana/README.md",
        "codex-woodpecker/README.md",
    ]

    bad_pattern = re.compile(r"http://127\\.0\\.0\\.1:91\\d\\d/mcp")
    offenders: list[str] = []

    for file_path in files:
        text = _load(file_path)
        if bad_pattern.search(text):
            offenders.append(file_path)

    assert not offenders, f"Found stale /mcp endpoint examples in: {', '.join(offenders)}"


def test_sse_endpoint_examples_exist_for_all_codex_mcp_servers() -> None:
    expected_examples = {
        "codex-second-opinion/README.md": "http://127.0.0.1:9100/sse",
        "codex-playwright/README.md": "http://127.0.0.1:9101/sse",
        "codex-nano-banana/README.md": "http://127.0.0.1:9102/sse",
        "codex-woodpecker/README.md": "http://127.0.0.1:9103/sse",
    }

    missing: list[str] = []
    for file_path, endpoint in expected_examples.items():
        if endpoint not in _load(file_path):
            missing.append(f"{file_path} -> {endpoint}")

    assert not missing, f"Missing SSE endpoint examples: {', '.join(missing)}"
