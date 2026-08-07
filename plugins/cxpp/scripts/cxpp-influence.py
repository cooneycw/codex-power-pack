#!/usr/bin/env python3
"""Consent-first management of the optional CxPP AGENTS.md routing block."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

START_RE = re.compile(r"<!-- cxpp-routing:start sha256=([0-9a-f]{64}) -->")
END = "<!-- cxpp-routing:end -->"
BYTE_BUDGET = 1024


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_template() -> Path:
    root = Path(__file__).resolve().parents[1]
    repo_template = root / ".agents" / "routing-block.md"
    return repo_template if repo_template.is_file() else root / "assets" / "routing-block.md"


def agents_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    return path if path.name == "AGENTS.md" else path / "AGENTS.md"


def rendered(template: str) -> str:
    clean = template.strip() + "\n"
    if len(clean.encode("utf-8")) > BYTE_BUDGET:
        raise ValueError(f"routing block exceeds {BYTE_BUDGET}-byte budget")
    return f"<!-- cxpp-routing:start sha256={digest(clean)} -->\n{clean}{END}\n"


def inspect(content: str, template: str) -> tuple[str, tuple[int, int] | None]:
    starts = list(START_RE.finditer(content))
    ends = [match.start() for match in re.finditer(re.escape(END), content)]
    if not starts and not ends:
        return "absent", None
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0].end():
        return "conflict", None
    start = starts[0].start()
    finish = ends[0] + len(END)
    finish += 1 if content[finish:finish + 1] == "\n" else 0
    body_start = starts[0].end() + (1 if content[starts[0].end():starts[0].end() + 1] == "\n" else 0)
    body = content[body_start:ends[0]]
    owned = digest(body) == starts[0].group(1)
    if not owned:
        return "conflict", (start, finish)
    return ("current" if body == template.strip() + "\n" else "upgrade"), (start, finish)


def desired(content: str, template: str, operation: str) -> tuple[str, str]:
    state, span = inspect(content, template)
    if state == "conflict":
        raise ValueError("managed routing block was edited or has malformed markers")
    if operation == "apply":
        block = rendered(template)
        if state == "absent":
            separator = "" if not content else ("\n" if content.endswith("\n") else "\n\n")
            return content + separator + block, "updated"
        if state == "current":
            return content, "already current"
        assert span is not None
        return content[:span[0]] + block + content[span[1]:], "updated"
    if state == "absent":
        return content, "already absent"
    assert span is not None
    result = content[:span[0]] + content[span[1]:]
    return result.rstrip() + ("\n" if result.strip() else ""), "removed"


def report(path: Path, state: str, outcome: str, *, as_json: bool) -> None:
    payload = {"path": str(path), "state": state, "outcome": outcome}
    print(json.dumps(payload, sort_keys=True) if as_json else f"{outcome}: {path} ({state})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=("status", "preview", "preview-remove", "apply", "remove", "decline"),
    )
    parser.add_argument("target")
    parser.add_argument("--template", type=Path, default=default_template())
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    path = agents_path(args.target)
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    template = args.template.read_text(encoding="utf-8")
    state, _ = inspect(content, template)
    if args.operation == "status":
        report(path, state, "inspected", as_json=args.json)
        return 0
    if args.operation == "decline":
        report(path, state, "skipped by user", as_json=args.json)
        return 0
    operation = "remove" if args.operation in {"preview-remove", "remove"} else "apply"
    try:
        updated, outcome = desired(content, template, operation)
    except ValueError as exc:
        print(f"conflict: {path}: {exc}", file=sys.stderr)
        return 2
    if args.operation in {"preview", "preview-remove"}:
        diff = difflib.unified_diff(
            content.splitlines(True),
            updated.splitlines(True),
            fromfile=str(path),
            tofile=str(path),
        )
        print("".join(diff))
        report(path, state, outcome, as_json=args.json)
        return 0
    if not args.approve:
        print("explicit --approve is required after reviewing preview", file=sys.stderr)
        return 3
    if updated != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
    report(path, state, outcome, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
