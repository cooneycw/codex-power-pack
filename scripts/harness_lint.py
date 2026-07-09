#!/usr/bin/env python3
"""Lint Codex skills for unadapted Claude-only constructs.

Generated CxPP skills may still mention Claude-only surfaces in their source
body. That is acceptable only when the skill's SKILL.md carries an explicit
Codex harness adaptation for the same construct. This gate catches copied
instructions that would otherwise break under Codex.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"
DEFAULT_ALLOWLIST = REPO_ROOT / ".codex" / "harness-lint-allowlist.txt"


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    pattern: re.Pattern[str]
    adaptation_terms: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: Path
    line: int
    text: str
    description: str


@dataclass(frozen=True)
class Allow:
    rule_id: str
    path: str
    needle: str
    reason: str


RULES = (
    Rule(
        id="agent-tool",
        description="Claude Agent tool reference",
        pattern=re.compile(r"\bAgent\s+tool\b"),
        adaptation_terms=("Agent tool",),
    ),
    Rule(
        id="skill-tool",
        description="Claude Skill tool reference",
        pattern=re.compile(r"\bSkill\s+tool\b"),
        adaptation_terms=("Skill tool",),
    ),
    Rule(
        id="ask-user-question",
        description="Claude AskUserQuestion tool reference",
        pattern=re.compile(r"\bAskUserQuestion\b"),
        adaptation_terms=("AskUserQuestion",),
    ),
    Rule(
        id="claude-worktree-path",
        description="Claude native worktree path",
        pattern=re.compile(r"\.claude/worktrees"),
        adaptation_terms=(),
    ),
    Rule(
        id="bang-command-prefix",
        description="Claude ! shell command prefix",
        pattern=re.compile(r"^\s*!(?!\[)"),
        adaptation_terms=("! prefix",),
    ),
    Rule(
        id="claude-plugin-command",
        description="Claude /plugin command reference",
        pattern=re.compile(r"(?<![\w.-])/plugin\b"),
        adaptation_terms=("/plugin",),
    ),
    Rule(
        id="claude-md-reference",
        description="CLAUDE.md reference",
        pattern=re.compile(r"\bCLAUDE\.md\b"),
        adaptation_terms=("CLAUDE.md",),
    ),
)


def _markdown_files(skills_root: Path) -> list[Path]:
    if not skills_root.is_dir():
        return []
    files: list[Path] = []
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        files.extend(sorted(skill_dir.rglob("*.md")))
    return files


def _skill_dir_for(path: Path, skills_root: Path) -> Path | None:
    rel = path.relative_to(skills_root)
    if len(rel.parts) < 2:
        return None
    skill_dir = skills_root / rel.parts[0]
    return skill_dir if skill_dir.is_dir() else None


def _adaptation_text(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ""

    lines = skill_md.read_text().splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "## Codex harness adaptations":
            start = index
            break
    if start is None:
        return ""

    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("# "):
            break
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def _is_inside_adaptation_block(path: Path, line_number: int, skills_root: Path) -> bool:
    if path.name != "SKILL.md":
        return False
    lines = path.read_text().splitlines()
    start = None
    for index, line in enumerate(lines, start=1):
        if line.strip() == "## Codex harness adaptations":
            start = index
            break
    if start is None or line_number <= start:
        return False
    for index, line in enumerate(lines[start:], start=start + 1):
        if line.startswith("# ") or line.startswith("## "):
            return line_number < index
    return True


def _has_adaptation(path: Path, rule: Rule, skills_root: Path) -> bool:
    if not rule.adaptation_terms:
        return False
    skill_dir = _skill_dir_for(path, skills_root)
    if skill_dir is None:
        return False
    text = _adaptation_text(skill_dir)
    return any(term in text for term in rule.adaptation_terms)


def _is_cpp_source_context(finding: Finding) -> bool:
    """Allow stale Claude paths only when the line says it is source context."""

    if finding.rule_id != "claude-worktree-path":
        return False
    markers = (
        "CPP source context",
        "Claude source context",
        "Claude Power Pack source context",
        "claude-power-pack source context",
    )
    return any(marker in finding.text for marker in markers)


def read_allowlist(path: Path) -> list[Allow]:
    if not path.is_file():
        return []

    allows: list[Allow] = []
    errors: list[str] = []
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|", 3)]
        if len(parts) != 4 or not all(parts):
            errors.append(f"{path}:{line_number}: expected rule|path|needle|reason")
            continue
        rule_id, rel_path, needle, reason = parts
        if rule_id not in {rule.id for rule in RULES}:
            errors.append(f"{path}:{line_number}: unknown rule '{rule_id}'")
            continue
        allows.append(Allow(rule_id=rule_id, path=rel_path, needle=needle, reason=reason))

    if errors:
        raise ValueError("\n".join(errors))
    return allows


def _allowed(finding: Finding, skills_root: Path, allows: list[Allow]) -> bool:
    rel = finding.path.relative_to(skills_root).as_posix()
    return any(
        allow.rule_id == finding.rule_id and allow.path == rel and (allow.needle == "*" or allow.needle in finding.text)
        for allow in allows
    )


def lint_skills(skills_root: Path = DEFAULT_SKILLS_ROOT, allowlist_path: Path = DEFAULT_ALLOWLIST) -> list[Finding]:
    skills_root = skills_root.resolve()
    allowlist_path = allowlist_path.resolve()
    allows = read_allowlist(allowlist_path)

    findings: list[Finding] = []
    for path in _markdown_files(skills_root):
        text = path.read_text()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in RULES:
                if not rule.pattern.search(line):
                    continue
                finding = Finding(
                    rule_id=rule.id,
                    path=path,
                    line=line_number,
                    text=line.strip(),
                    description=rule.description,
                )
                if _is_inside_adaptation_block(path, line_number, skills_root):
                    continue
                if _has_adaptation(path, rule, skills_root):
                    continue
                if _is_cpp_source_context(finding):
                    continue
                if _allowed(finding, skills_root, allows):
                    continue
                findings.append(finding)
    return findings


def run_check(skills_root: Path = DEFAULT_SKILLS_ROOT, allowlist_path: Path = DEFAULT_ALLOWLIST) -> int:
    try:
        findings = lint_skills(skills_root=skills_root, allowlist_path=allowlist_path)
    except ValueError as exc:
        print(f"harness-lint: invalid allowlist\n{exc}", file=sys.stderr)
        return 2

    if findings:
        print("harness-lint: unadapted Claude-only constructs found", file=sys.stderr)
        for finding in findings:
            rel = finding.path.relative_to(skills_root).as_posix()
            print(
                f"{rel}:{finding.line}: {finding.rule_id}: {finding.description}: {finding.text}",
                file=sys.stderr,
            )
        print(
            "\nAdd a Codex harness adaptation to the skill, rewrite the copied instruction,"
            " or add a reviewed rule|path|needle|reason entry to .codex/harness-lint-allowlist.txt.",
            file=sys.stderr,
        )
        return 1

    print(f"harness-lint: {len(_markdown_files(skills_root))} markdown file(s) passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint Codex skills for unadapted Claude-only constructs.")
    parser.add_argument("--check", action="store_true", help="fail on findings (default)")
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS_ROOT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    args = parser.parse_args(argv)
    return run_check(skills_root=args.skills_root, allowlist_path=args.allowlist)


if __name__ == "__main__":
    sys.exit(main())
