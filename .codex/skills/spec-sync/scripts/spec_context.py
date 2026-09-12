#!/usr/bin/env python3
"""Bounded, derivative Spec Kit governing context; never an approval receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

SCHEMA = "spec-sync-context/v1"
START = "<!-- spec-sync-context:start -->"
END = "<!-- spec-sync-context:end -->"
META = "<!-- spec-sync-context:metadata "
LEDGER_START = "<!-- spec-sync-ledger:start -->"
LEDGER_END = "<!-- spec-sync-ledger:end -->"
FOOTER = b"\n\n## Issue Sync Ledger\n\n"
MAX_OBJECT = 2 * 1024 * 1024
MAX_BODY = 128 * 1024
MAX_META = 32 * 1024
TEXT_BUDGET = 8192
HASH = re.compile(r"[0-9a-f]{64}")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class ContextError(ValueError):
    """Unreliable, changed, or unsupported source/context evidence."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, dict):
            result = {normalize(key): normalize(child) for key, child in item.items()}
            if len(result) != len(item):
                raise ContextError("duplicate normalized metadata keys")
            return result
        if item is None or type(item) in (bool, int):
            return item
        raise ContextError("unsupported metadata scalar")

    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContextError("duplicate metadata key")
        result[key] = value
    return result


def safe_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute() or any(p in ("", ".", "..") for p in relative.split("/")):
        raise ContextError(f"unsafe source path: {relative!r}")
    if unicodedata.normalize("NFC", relative) != relative or any(ord(c) < 32 for c in relative):
        raise ContextError("source paths must be NFC and contain no control characters")
    current = root
    for part in relative.split("/"):
        current /= part
        if current.is_symlink():
            raise ContextError(f"symlink source refused: {relative}")
    if not current.is_file() or current.stat().st_size > MAX_OBJECT:
        raise ContextError(f"missing/overlarge source: {relative}")
    return current


def git_bytes(command: list[str], root: Path) -> bytes:
    # Size-check blobs before capture. Other commands have bounded fixed-size output.
    result = subprocess.run(command, cwd=root, capture_output=True, check=False, timeout=20)
    if result.returncode or len(result.stdout) > MAX_OBJECT:
        raise ContextError(f"source command failed or exceeded budget: {' '.join(command[:3])}")
    return result.stdout


def read_object(root: Path, commit: str, relative: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ContextError("full immutable commit required")
    safe_path(root, relative)
    object_name = f"{commit}:{relative}"
    size = git_bytes(["git", "cat-file", "-s", object_name], root)
    if not size.strip().isdigit() or int(size) > MAX_OBJECT:
        raise ContextError(f"overlarge source object: {relative}")
    entry = git_bytes(["git", "ls-tree", commit, "--", relative], root)
    if not entry.startswith((b"100644 blob ", b"100755 blob ")):
        raise ContextError(f"source object is not a regular file: {relative}")
    return git_bytes(["git", "cat-file", "blob", object_name], root)


def ledger_parts(raw: bytes) -> tuple[bytes, bytes, bytes] | None:
    start, end = LEDGER_START.encode(), LEDGER_END.encode()
    count = raw.count(b"<!-- spec-sync-ledger:")
    if not count:
        return None
    if count != 2 or raw.count(start) != 1 or raw.count(end) != 1 or raw.index(start) >= raw.index(end):
        raise ContextError("incomplete, duplicate, damaged or reversed Issue Sync ledger markers")
    a, b = raw.index(start), raw.index(end) + len(end)
    return raw[:a], raw[a:b], raw[b:]


def ledger_rows(raw: bytes) -> list[dict[str, Any]]:
    parts = ledger_parts(raw)
    if parts is None:
        return []
    lines = parts[1].decode("utf-8").split("\n")
    if lines[:3] != [
        LEDGER_START,
        "| Stable identity | Granularity | Group | Tasks | Issue | URL | State |",
        "|---|---|---|---|---:|---|---|",
    ]:
        raise ContextError("noncanonical ledger header; reconcile mappings")
    rows = []
    for line in lines[3:-1]:
        match = re.fullmatch(
            (
                "\\| `([^`\\n]+)` \\| (stage|story|task) \\| `([^`\\n]+)` \\| (T\\d{"
                "3}(?:, T\\d{3})*) \\| #([1-9]\\d*) \\| (https://github.com/[^ ]+"
                ") \\| (OPEN|CLOSED) \\|"
            ),
            line,
        )
        if not match:
            raise ContextError("noncanonical ledger row; task/content edits cannot be hidden in a ledger")
        identity, granularity, group, tasks, number, url, state = match.groups()
        rows.append(
            dict(
                identity=identity,
                granularity=granularity,
                group=group,
                tasks=tasks.split(", "),
                number=int(number),
                url=url,
                state=state,
            )
        )
    if len({row["identity"] for row in rows}) != len(rows) or len({row["group"] for row in rows}) != len(rows):
        raise ContextError("duplicate ledger mapping claims")
    return rows


def ledger_write(raw: bytes, ledger: bytes) -> bytes:
    parts = ledger_parts(raw)
    if parts:
        return parts[0] + ledger + parts[2]
    # Historical writer behavior, precisely recognized; never used as general normalization.
    return raw.decode("utf-8").rstrip().encode("utf-8") + FOOTER + ledger + b"\n"


def compare_tasks(reviewed: bytes, working: bytes) -> dict[str, str]:
    ledger_rows(reviewed)
    ledger_rows(working)
    if reviewed != working:
        parts = ledger_parts(working)
        if parts is None or ledger_write(reviewed, parts[1]) != working:
            raise ContextError(
                "working tasks differ from immutable source beyond the deterministic ledger transformation"
            )
    return {
        "before_sha256": sha(reviewed),
        "after_sha256": sha(working),
        "comparison": "exact" if reviewed == working else "candidate-ledger-successor",
    }


def snapshot(
    root: Path, commit: str, tasks: str, reader: Callable[[Path, str, str], bytes] = read_object
) -> dict[str, Any]:
    if ".specify/specs/" not in tasks or Path(tasks).name != "tasks.md":
        raise ContextError("expected selected .specify/specs/<feature>/tasks.md")
    paths = {name: str(Path(tasks).with_name(f"{name}.md")) for name in ("spec", "plan", "tasks")}
    raw, local = {}, {}
    for name, path in paths.items():
        local[name] = safe_path(root, path).read_bytes()
        raw[name] = reader(root, commit, path)
        if len(raw[name]) > MAX_OBJECT:
            raise ContextError("overlarge immutable artifact")
        raw[name].decode("utf-8")
    return dict(root=root, commit=commit, paths=paths, raw=raw, local=local)


def require_matching(view: dict[str, Any]) -> dict[str, str]:
    for name in ("spec", "plan"):
        if view["raw"][name] != view["local"][name]:
            raise ContextError(f"working {name}.md differs from immutable source; commit/review before synchronization")
    return compare_tasks(view["raw"]["tasks"], view["local"]["tasks"])


def recheck(view: dict[str, Any]) -> None:
    for name, path in view["paths"].items():
        if safe_path(view["root"], path).read_bytes() != view["local"][name]:
            raise ContextError(f"{path}: source changed during synchronization; reconcile and re-preview")


def sections(raw: bytes) -> list[tuple[int, str, str]]:
    lines = raw.decode("utf-8").splitlines(keepends=True)
    starts = [(i, line.rstrip("\r\n")) for i, line in enumerate(lines) if re.match(r"^#{1,6} ", line)]
    if lines and (not starts or starts[0][0] > 0):
        starts.insert(0, (0, "[Preamble]"))
    return [
        (start + 1, title, "".join(lines[start : (starts[n + 1][0] if n + 1 < len(starts) else len(lines))]))
        for n, (start, title) in enumerate(starts)
    ]


def extract(view: dict[str, Any], stories: list[str]) -> tuple[str, list[str], list[str]]:
    pieces, locations, unresolved = [], [], []
    selected = {story.replace("us-", "US").upper() for story in stories}
    found: set[str] = set()
    for name in ("spec", "plan"):
        if not view["raw"][name].strip():
            unresolved.append(f"empty source; read {view['paths'][name]}")
        active: str | None = None
        story_level = 0
        for line, title, text in sections(view["raw"][name]):
            level = len(title.split(" ", 1)[0])
            declaration = re.match(r"^#{1,6}\s+(US\d+|User Story\s+\d+)\s*(?::|-|$)", title, re.I)
            if declaration:
                active = "US" + re.search(r"\d+", declaration.group(1)).group()
                story_level = level
                if name == "spec" and active in selected:
                    if active in found:
                        unresolved.append(f"duplicate story declaration {active}: {view['paths'][name]}:{line}")
                    found.add(active)
            elif level <= story_level:
                active = None
            location = f"{view['paths'][name]}:{line}"
            reason = ""
            if active in selected:
                reason = f"declared {active}"
            elif active:
                continue
            elif re.search(
                r"constraint|non.functional|non.goal|out.of.scope|global|decision|architecture", title, re.I
            ):
                reason = "global constraint/plan decision (relevance must be reviewed)"
            elif re.search(r"functional requirement", title, re.I):
                # Only explicit User Story columns establish requirement ownership.
                rows = text.splitlines()
                header = next((row for row in rows if re.search(r"\|\s*User Stor(?:y|ies)\s*\|", row, re.I)), None)
                if header:
                    columns = [cell.strip() for cell in header.strip("|").split("|")]
                    index = next(i for i, cell in enumerate(columns) if re.fullmatch(r"User Stor(?:y|ies)", cell, re.I))
                    kept = []
                    for row in rows:
                        if not re.search(r"\bFR[- ]?\d+\b", row):
                            continue
                        cells = [cell.strip() for cell in row.strip("|").split("|")]
                        tags = set(re.findall(r"\bUS\d+\b", cells[index] if len(cells) > index else "", re.I))
                        if {tag.upper() for tag in tags} & selected:
                            kept.append(row)
                        elif not tags:
                            unresolved.append(f"unmapped requirement: {location}: {row}")
                    text = title + "\n" + header + "\n" + "\n".join(kept) + "\n"
                    reason = "explicit requirement-to-story column"
                else:
                    unresolved.append(f"unsupported requirement mapping; read {location}")
            elif name == "plan":
                # Plans often declare decisions in prose under generic headings.
                reason = "shared plan material; applicability requires review"
            elif text.strip() != title.strip():
                unresolved.append(f"unclassified source section; read {location}")
            if reason:
                locations.append(location)
                pieces.append(f"### Source `{location}` — {reason}\n{text.rstrip()}\n")
    for story in sorted(selected - found):
        unresolved.append(f"missing explicit {story} declaration; read {view['paths']['spec']}")
    if not selected:
        unresolved.append(f"selected tasks declare no story relationship; read {view['paths']['spec']}")
    result = "\n".join(pieces)
    if len(result.encode()) > TEXT_BUDGET:
        result = (
            result.encode()[:TEXT_BUDGET].decode("utf-8", errors="ignore")
            + "\n[EXTRACT CAPPED; read all source locations below]"
        )
        unresolved.append("extract capped; completeness is not established")
    return result, locations, unresolved


def validate_selection(view: dict[str, Any], group: dict[str, Any]) -> None:
    keys = {"id", "granularity", "task_ids", "stories", "task_text", "checkpoint", "source_lines"}
    if not isinstance(group, dict) or set(group) != keys or group["granularity"] not in ("stage", "story", "task"):
        raise ContextError("invalid parser-produced selection metadata")
    ids, numbers, stories = group["task_ids"], group["source_lines"], group["stories"]
    if (
        not isinstance(ids, list)
        or not ids
        or len(ids) > 500
        or len(set(ids)) != len(ids)
        or any(not isinstance(item, str) or not re.fullmatch(r"T\d{3}", item) for item in ids)
        or not isinstance(numbers, list)
        or len(numbers) != len(ids)
        or any(type(n) is not int or n <= 0 for n in numbers)
        or numbers != sorted(set(numbers))
        or not isinstance(stories, list)
        or stories != sorted(set(stories))
        or any(not isinstance(item, str) or not re.fullmatch(r"us-\d+", item) for item in stories)
    ):
        raise ContextError("invalid selected task/story identity")
    source = view["raw"]["tasks"].decode("utf-8").splitlines()
    selected = []
    declared_stories: set[str] = set()
    ancestry: list[tuple[int, str]] = []
    scopes: dict[int, list[str]] = {}
    checkpoints: list[tuple[str, list[str]]] = []
    for number, raw_line in enumerate(source, 1):
        heading = re.match(r"^(#{1,6})\s+(.+)", raw_line.strip())
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            ancestry = [(depth, title) for depth, title in ancestry if depth < level]
            ancestry.append((level, title))
        owners = []
        for _, title in ancestry:
            story = re.fullmatch(r"(?:US|User\s+Story\s+)(\d+)(?:\s*[:\-].*|\s*)", title, re.I)
            stage = re.fullmatch(r"(Stage|Wave|Phase)\s+(\d+)(?:\s*:\s*.+)?", title, re.I)
            if story:
                owners.append(f"us-{story.group(1)}")
            elif stage:
                owners.append(f"{stage.group(1).lower()}-{stage.group(2)}")
        scopes[number] = owners
        checkpoint_match = re.match(r"^\*\*Checkpoint:\*\*\s*(.+)$", raw_line.strip(), re.I)
        if checkpoint_match:
            checkpoints.append((unicodedata.normalize("NFC", checkpoint_match.group(1).strip()), owners))
    for number, task_id in zip(numbers, ids):
        if number > len(source):
            raise ContextError("selected task source line missing")
        line = source[number - 1].strip()
        match = re.fullmatch(r"-\s*\[[ xX]\]\s+(?:\*\*)?(T\d{3})(?:\*\*)?\s+(.+)", line)
        if not match or match.group(1) != task_id:
            raise ContextError("selected task identity differs from immutable source line")
        # Verify the renderer projection; grouping remains exclusively compiler-owned.
        description = re.sub(r"\[(?:P|US\d+)\]", "", match.group(2), flags=re.I).strip()
        selected.append(unicodedata.normalize("NFC", f"- [ ] **{task_id}** {description}"))
        tags = {f"us-{tag}" for tag in re.findall(r"\[US(\d+)\]", match.group(2), re.I)}
        story_owner = next((owner for owner in reversed(scopes[number]) if owner.startswith("us-")), None)
        declared_stories.update(tags or ({story_owner} if story_owner else set()))
    if sorted(declared_stories) != stories:
        raise ContextError("story selection differs from source-declared task relationships")
    if group["task_text"] != "\n".join(selected):
        raise ContextError("task wording differs from immutable source")
    checkpoint = group["checkpoint"]
    fallback = f"{ids[0]} is complete and the listed quality commands pass."
    allowed = False
    for text, owners in checkpoints:
        if text != checkpoint or not owners:
            continue
        if owners[-1] == group["id"]:
            allowed = True
        elif group["granularity"] == "story" and owners[-1] in scopes[numbers[0]]:
            owned_lines = [
                n
                for n, owner in scopes.items()
                if owners[-1] in owner and re.match(r"^-\s*\[[ xX]\].*\bT\d{3}\b", source[n - 1].strip())
            ]
            allowed = owned_lines == numbers and stories == [group["id"]]
    if not allowed and not (group["granularity"] == "task" and len(ids) == 1 and checkpoint == fallback):
        raise ContextError("acceptance checkpoint not owned by selected source group")


def make_context(
    view: dict[str, Any],
    repository: str,
    group: dict[str, Any],
    previous: str | None = None,
    revision: str | None = None,
    previous_commit: str | None = None,
) -> tuple[dict[str, Any], str]:
    if previous_commit is not None and (
        not isinstance(previous_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", previous_commit)
    ):
        raise ContextError("previous artifact commit must be a full immutable identity")
    if (previous is None) != (previous_commit is None):
        raise ContextError("previous snapshot and artifact commit must be bound together")
    if previous is not None and (not isinstance(previous, str) or not HASH.fullmatch(previous)):
        raise ContextError("previous snapshot must be a full SHA256 binding")
    if revision is not None and (not isinstance(revision, str) or len(revision.encode()) > 2048):
        raise ContextError("observed revision reference must be bounded text, never authority")
    group = json.loads(canonical(group))
    validate_selection(view, group)
    if not REPO.fullmatch(repository):
        raise ContextError("invalid repository identity")
    extracted, locations, unresolved = extract(view, group["stories"])
    tasks_path = view["paths"]["tasks"]
    metadata = dict(
        schema=SCHEMA,
        source_repository=repository,
        target_repository=repository,
        tasks_path=tasks_path,
        identity=f"spec-sync:v1:{repository}:{tasks_path}:{group['id']}",
        group=group,
        artifact_commit=view["commit"],
        artifacts={name: dict(path=path, sha256=sha(view["raw"][name])) for name, path in view["paths"].items()},
        task_source_sha256=sha(view["raw"]["tasks"]),
        locations=locations,
        unresolved=unresolved,
        scoped_sha256=sha(extracted.encode()),
        previous_snapshot=previous,
        previous_artifact_commit=previous_commit,
        observed_revision=revision,
    )
    metadata = json.loads(canonical(metadata))
    base = f"https://github.com/{repository}/blob/{view['commit']}/"
    visible = "\n".join(
        [
            "## Outcome",
            "Deliver the selected group under the sourced outcomes, acceptance and constraints below.",
            ("The cache is derivative. Source text governs; proposed mechanisms remain subject to existing decisions."),
            "",
            "## Tasks",
            group["task_text"],
            "",
            "## User-story traceability",
            ", ".join(group["stories"]) or "No explicit story mapping.",
            "",
            "## Acceptance checkpoint",
            group["checkpoint"],
            "",
            "## Constraints and non-goals",
            "Preserve the approved artifact boundary. Do not absorb tasks from another synchronization group.",
            extracted,
            "### Source coverage",
            *(f"- `{location}`" for location in locations),
            *(f"- UNRESOLVED: {item}" for item in unresolved),
            "",
            "## Immutable artifacts",
            *(
                f"- [{name}.md]({base}{quote(path, safe='/')}) — raw SHA256 `{metadata['artifacts'][name]['sha256']}`"
                for name, path in view["paths"].items()
            ),
            "",
            ("Retrieval/checksums do not prove acknowledgement, approval, official analysis or native-wave admission."),
        ]
    )
    metadata["snapshot"] = sha(canonical(metadata))
    return metadata, visible


def pack(metadata: dict[str, Any], visible: str) -> str:
    document = dict(metadata, integrity=sha(canonical(metadata) + b"\n" + visible.encode()))
    encoded = canonical(document)
    if len(encoded) > MAX_META or "-->" in encoded.decode():
        raise ContextError("metadata exceeds budget or contains an unsafe marker")
    return START + "\n" + visible + "\n" + META + encoded.decode() + " -->\n" + END


def unpack(body: str) -> tuple[dict[str, Any], str, int, int] | None:
    if len(body.encode()) > MAX_BODY:
        raise ContextError("issue body exceeds context-check budget")
    count = body.count("<!-- spec-sync-context:")
    if not count:
        return None
    if count != 3 or body.count(START) != 1 or body.count(END) != 1 or body.count(META) != 1:
        raise ContextError("malformed generated context markers; not ordinary absent context")
    a, b, m = body.index(START), body.index(END) + len(END), body.index(META)
    if not a < m < b or body[m - 1 : m] != "\n" or not body[m:b].endswith(" -->\n" + END):
        raise ContextError("crossed/damaged context boundaries")
    encoded = body[m + len(META) : b - len(" -->\n" + END)]
    if len(encoded.encode()) > MAX_META:
        raise ContextError("overlarge context metadata")
    data = json.loads(encoded, object_pairs_hook=unique_object)
    keys = {
        "schema",
        "source_repository",
        "target_repository",
        "tasks_path",
        "identity",
        "group",
        "artifact_commit",
        "artifacts",
        "task_source_sha256",
        "locations",
        "unresolved",
        "scoped_sha256",
        "previous_snapshot",
        "previous_artifact_commit",
        "observed_revision",
        "snapshot",
        "integrity",
    }
    if (
        not isinstance(data, dict)
        or set(data) != keys
        or data["schema"] != SCHEMA
        or canonical(data).decode() != encoded
    ):
        raise ContextError("unsupported/noncanonical context metadata")
    visible = body[a + len(START) + 1 : m - 1]
    integrity = data.pop("integrity")
    if integrity != sha(canonical(data) + b"\n" + visible.encode()):
        raise ContextError("edited generated context; reconcile ownership before refresh")
    if data["snapshot"] != sha(canonical({k: v for k, v in data.items() if k != "snapshot"})):
        raise ContextError("invalid snapshot binding")
    # Dependencies must be wholly outside context, never nested/crossed into it.
    positions = [match.start() for match in re.finditer(r"<!-- spec-sync-dependencies:", body)]
    if positions and (len(positions) != 2 or any(a <= pos < b for pos in positions) or positions[0] < a < positions[1]):
        raise ContextError("overlapping context/dependency ownership")
    if positions:
        dependency = re.search(
            (
                "<!-- spec-sync-dependencies:start sha256=([0-9a-f]{64}) -->\\"
                "n(.*?)\\n<!-- spec-sync-dependencies:end -->"
            ),
            body,
            re.S,
        )
        if not dependency or sha(dependency.group(2).encode()) != dependency.group(1):
            raise ContextError("damaged/edited dependency ownership")
    return data, visible, a, b


def replace_context(body: str, replacement: str) -> str:
    current = unpack(body)
    if not current:
        raise ContextError(
            (
                "legacy/unattested context: review entire body, preserve huma"
                "n decisions, explicitly reconcile superseded sections before"
                " adopting the proposed managed view; no competing view appen"
                "ded"
            )
        )
    return body[: current[2]] + replacement + body[current[3] :]


def source_repository(root: Path) -> str:
    origin = git_bytes(["git", "config", "--get", "remote.origin.url"], root).decode().strip()
    match = re.fullmatch(r"(?:https://github.com/|git@github.com:)([^/]+/[^/]+?)(?:\.git)?", origin)
    if not match or not REPO.fullmatch(match.group(1)):
        raise ContextError("trusted source requires an explicit GitHub origin repository")
    return match.group(1)


def check(
    body: str,
    root: Path,
    repository: str,
    issue: int,
    tasks: str | None,
    group: str | None,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    current = unpack(body)
    if not current:
        return dict(
            state="legacy/unattested" if "spec-sync:v1:" in body else "absent",
            evidence="ordinary analysis remains available; no generated source receipt",
            issue_body=body,
        )
    data, _, _, _ = current
    if not tasks or not group or not task_ids or issue <= 0 or not REPO.fullmatch(repository):
        raise ContextError(
            ("generated context requires independently selected --tasks, --group, --task-ids, --repo and --issue")
        )
    identity = f"spec-sync:v1:{repository}:{tasks}:{group}"
    if (
        data["source_repository"] != repository
        or data["target_repository"] != repository
        or data["identity"] != identity
        or data["tasks_path"] != tasks
        or data["group"]["id"] != group
        or body.count(f"<!-- {identity} -->") != 1
        or body.count("<!-- spec-sync:v1:") != 1
        or data["group"]["task_ids"] != task_ids
    ):
        raise ContextError("context does not match expected repository/task/group identity")
    if source_repository(root) != repository:
        raise ContextError("trusted checkout source repository mismatch")
    view = snapshot(root, data["artifact_commit"], tasks)
    expected, text = make_context(
        view,
        repository,
        data["group"],
        data["previous_snapshot"],
        data["observed_revision"],
        data["previous_artifact_commit"],
    )
    if data != expected:
        raise ContextError("metadata does not match retrieved immutable source objects")
    differences = []
    for name in ("spec", "plan", "tasks"):
        if view["raw"][name] != view["local"][name]:
            differences.append(
                dict(path=view["paths"][name], expected=sha(view["raw"][name]), observed=sha(view["local"][name]))
            )
    return dict(
        state="changed" if differences else "unresolved" if data["unresolved"] else "current",
        issue=issue,
        identity=identity,
        snapshot=data["snapshot"],
        retrieved=data["artifacts"],
        checkout_differences=differences,
        governing_text=text,
        issue_text_outside_context=body[:current[2]] + body[current[3]:],
        previous_snapshot=data["previous_snapshot"],
        previous_artifact_commit=data["previous_artifact_commit"],
        observed_revision=data["observed_revision"],
        authority=(
            "retrieval only; old decisions/receipts retain their original"
            " binding; inspect referenced decisions, never reinterpret ap"
            "proval"
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--tasks")
    parser.add_argument("--group")
    parser.add_argument("--task-ids", help="independently selected comma-separated task identities")
    args = parser.parse_args()
    try:
        path = Path(args.body_file)
        if path.stat().st_size > MAX_BODY:
            raise ContextError("overlarge issue body")
        body = path.read_bytes().decode("utf-8")
        print(
            json.dumps(
                check(
                    body,
                    Path(args.checkout).resolve(),
                    args.repo,
                    args.issue,
                    args.tasks,
                    args.group,
                    args.task_ids.split(",") if args.task_ids else None,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"spec-context: unreliable context: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
