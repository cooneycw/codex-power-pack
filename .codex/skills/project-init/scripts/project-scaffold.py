#!/usr/bin/env python3
"""Create a minimal Codex-native Python project without external side effects."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold(name: str, root: Path) -> list[Path]:
    """Create the deterministic project files and return their relative paths."""
    package = name.replace("-", "_")
    files = {
        "pyproject.toml": f'''[project]
name = "{name}"
version = "0.1.0"
description = ""
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["mypy>=1.10", "pytest>=8.0", "ruff>=0.4"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
''',
        ".gitignore": ".venv/\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n.mypy_cache/\n.env\n",
        "AGENTS.md": f'''# {name}

- Never print secrets, tokens, passwords, connection strings, or raw `.env` contents.
- Use Makefile targets as the canonical interface for lint, test, typecheck, and verify.
- Keep host-managed services and credentials outside this repository.
- Reproduce failures with the relevant Make target, fix the root cause, and run `make verify` after repairs.
''',
        "Makefile": '''.PHONY: lint test typecheck verify

lint:
\tuv run ruff check .

test:
\tuv run pytest

typecheck:
\tuv run mypy .

verify: lint test typecheck
''',
        ".codex/cicd.yml": "build:\n  required_targets: [lint, test, typecheck]\n",
        ".github/workflows/ci.yml": '''name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: uv sync --extra dev
      - run: make verify
''',
        f"src/{package}/__init__.py": f'"""{name}."""\n\n__version__ = "0.1.0"\n',
        f"tests/test_{package}.py": f'''from {package} import __version__


def test_version_is_available() -> None:
    assert __version__ == "0.1.0"
''',
    }
    written: list[Path] = []
    for relative, content in files.items():
        target = root / relative
        _write(target, content)
        written.append(Path(relative))
    return written


def _run(argv: list[str], root: Path) -> None:
    subprocess.run(argv, cwd=root, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a Codex-native Python project")
    parser.add_argument("name")
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--git", action="store_true", help="initialize a local Git repository")
    parser.add_argument("--initial-commit", action="store_true", help="create a local initial commit (requires --git)")
    parser.add_argument("--author-name", help="Git author name for the optional local initial commit")
    parser.add_argument("--author-email", help="Git author email for the optional local initial commit")
    args = parser.parse_args(argv)

    if not NAME_PATTERN.fullmatch(args.name):
        parser.error("name must be lowercase kebab-case and start with a letter")
    if args.initial_commit and not args.git:
        parser.error("--initial-commit requires --git")
    if bool(args.author_name) != bool(args.author_email):
        parser.error("--author-name and --author-email must be provided together")

    root = args.path.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        parser.error(f"target must be new or empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    written = scaffold(args.name, root)

    if args.git:
        _run(["git", "init", "--initial-branch=main"], root)
        if args.initial_commit:
            _run(["git", "add", "."], root)
            commit = ["git"]
            if args.author_name:
                commit.extend(["-c", f"user.name={args.author_name}", "-c", f"user.email={args.author_email}"])
            commit.extend(["commit", "-m", "Initial Codex project scaffold"])
            _run(commit, root)

    print(f"Scaffolded {args.name} at {root}")
    for relative in written:
        print(relative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
