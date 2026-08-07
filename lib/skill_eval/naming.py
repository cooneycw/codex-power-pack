"""Fail-closed normalization for installed and portable skill names."""

from __future__ import annotations

import json
from pathlib import Path

from .cases import CaseError


def load_skill_families(root: Path) -> dict[str, str]:
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(marketplace.read_text(encoding="utf-8"))
    families: dict[str, str] = {}
    for plugin in payload["plugins"]:
        family = str(plugin["name"]).casefold()
        skill_root = root / "plugins" / family / "skills"
        if not skill_root.is_dir():
            raise CaseError(f"marketplace plugin {family!r} has no skills directory")
        for path in skill_root.iterdir():
            if path.is_dir() and (path / "SKILL.md").is_file():
                previous = families.setdefault(path.name.casefold(), family)
                if previous != family:
                    raise CaseError(f"skill {path.name!r} is published by multiple families")
    return families


def normalize_selected_skill(
    raw: object, expected_skill: str | None, families: dict[str, str]
) -> tuple[str | None, str | None]:
    if raw is None:
        return None, None
    original = str(raw)
    text = original.strip().lstrip("$").casefold()
    if text in {"", "none", "null", "no_skill", "no-skill"}:
        return None, original
    if ":" not in text:
        return text, original
    family, _, name = text.partition(":")
    expected_family = families.get((expected_skill or name).casefold())
    if name and expected_family is not None and family == expected_family and families.get(name) == family:
        return name, original
    return text, original
