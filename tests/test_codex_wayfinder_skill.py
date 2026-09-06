"""Native Codex Wayfinder package and starter-map contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".codex" / "skills" / "codex-wayfinder"
PACKAGE = ROOT / "plugins" / "project" / "skills" / "codex-wayfinder"
MAP_ROOT = ROOT / "docs" / "wayfinder" / "native-codex-waves"


def frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    payload = yaml.safe_load(text.split("---", 2)[1])
    assert isinstance(payload, dict)
    return payload


def test_native_and_packaged_payloads_match_with_explicit_metadata() -> None:
    source_files = {
        path.relative_to(SOURCE): path.read_bytes()
        for path in SOURCE.rglob("*")
        if path.is_file()
    }
    package_files = {
        path.relative_to(PACKAGE): path.read_bytes()
        for path in PACKAGE.rglob("*")
        if path.is_file() and "agents" not in path.relative_to(PACKAGE).parts
    }

    assert package_files == source_files
    assert b"Copyright (c) 2026 Matt Pocock" in source_files[Path("LICENSE")]
    assert b"3cca18b368ae95cdbdebbff572ccafa662551015" in source_files[Path("SKILL.md")]

    metadata = yaml.safe_load((PACKAGE / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    assert metadata["policy"]["allow_implicit_invocation"] is False
    assert "$codex-wayfinder" in metadata["interface"]["default_prompt"]


def test_starter_map_has_one_safe_frontier_and_no_invented_decisions() -> None:
    map_payload = frontmatter(MAP_ROOT / "map.md")["wayfinder"]
    assert map_payload["status"] == "proposed"
    assert map_payload["destination_status"] == "proposed"

    tickets: dict[str, tuple[dict[str, Any], str]] = {}
    for path in sorted((MAP_ROOT / "tickets").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        payload = frontmatter(path)["wayfinder"]
        tickets[payload["id"]] = (payload, text)

    assert set(tickets) == {
        "choose-first-milestone",
        "define-session-identity",
        "prove-communication-contract",
        "define-specification-handoff",
    }
    assert all(payload["status"] == "open" for payload, _ in tickets.values())
    assert all("Pending" in text.split("## Resolution", 1)[1] for _, text in tickets.values())

    path_to_id = {
        path.name: frontmatter(path)["wayfinder"]["id"]
        for path in (MAP_ROOT / "tickets").glob("*.md")
    }
    blockers: dict[str, list[str]] = {}
    for ticket_id, (payload, _) in tickets.items():
        blockers[ticket_id] = [path_to_id[Path(link).name] for link in payload["blocked_by"]]

    frontier = [
        ticket_id
        for ticket_id, (payload, _) in tickets.items()
        if payload["status"] == "open"
        and not blockers[ticket_id]
        and payload["claim"] == {"owner": None, "claimed_at": None}
    ]
    assert frontier == ["choose-first-milestone"]

    map_text = (MAP_ROOT / "map.md").read_text(encoding="utf-8")
    decisions = map_text.split("## Decisions so far", 1)[1].split("## Not yet specified", 1)[0]
    assert decisions.strip() == "None yet."
    assert "No first-milestone preference has been selected" in map_text


def test_starter_ticket_dependencies_are_complete_and_acyclic() -> None:
    ticket_paths = sorted((MAP_ROOT / "tickets").glob("*.md"))
    path_to_id = {path.name: frontmatter(path)["wayfinder"]["id"] for path in ticket_paths}
    graph = {
        path_to_id[path.name]: [
            path_to_id[Path(link).name]
            for link in frontmatter(path)["wayfinder"]["blocked_by"]
        ]
        for path in ticket_paths
    }

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ticket_id: str) -> None:
        assert ticket_id not in visiting, f"cycle at {ticket_id}"
        if ticket_id in visited:
            return
        visiting.add(ticket_id)
        for blocker in graph[ticket_id]:
            visit(blocker)
        visiting.remove(ticket_id)
        visited.add(ticket_id)

    for ticket_id in graph:
        visit(ticket_id)
    assert visited == set(graph)
