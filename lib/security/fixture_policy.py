"""Exact, reviewed native-secret fixture exceptions, never path exclusions.

Only the policy at the scan root is consulted. Digests cover the scanner's
entire matched text (including assignment syntax for assignment detectors).
Neither policy parsing nor diagnostics may echo supplied values.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

POLICY_PATH = ".codex/security-fixtures.toml"


class InvalidFixturePolicy(ValueError):
    """An existing policy cannot safely be used; scanning must not pass."""


def _plain_path(value: str) -> bool:
    return (
        bool(value)
        and not PurePosixPath(value).is_absolute()
        and PurePosixPath(value).as_posix() == value
        and all(part not in ("", ".", "..") for part in value.split("/"))
        and not any(char in value for char in "\\*?[]:")
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
    )


def _has_symlink(root: Path, relative: str) -> bool:
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            return True
    return False


@dataclass(frozen=True)
class FixturePolicy:
    root: Path
    entries: frozenset[tuple[str, str, str]] = field(default_factory=frozenset)

    def matches(self, relative: str, finding_id: str, matched: str) -> bool:
        # Check links at use time too: an approved path is not an approved alias.
        digest = hashlib.sha256(matched.encode("utf-8")).hexdigest()
        return (
            (relative, finding_id, digest) in self.entries
            and _plain_path(relative)
            and not _has_symlink(self.root, relative)
        )


def load_fixture_policy(root: Path, finding_ids: set[str]) -> FixturePolicy:
    """Absent means no exceptions; every malformed existing policy is refused."""
    root = root.resolve()
    policy_path = root / POLICY_PATH
    try:
        if _has_symlink(root, POLICY_PATH):
            raise InvalidFixturePolicy("policy path must not contain symlinks")
        try:
            policy_path.lstat()
        except FileNotFoundError:
            return FixturePolicy(root)
        if not policy_path.is_file():
            raise InvalidFixturePolicy("policy must be a regular file")
        with policy_path.open("rb") as stream:
            data = tomllib.load(stream)
        if set(data) != {"version", "fixtures"} or type(data["version"]) is not int or data["version"] != 1:
            raise InvalidFixturePolicy("expected version 1 and fixtures only")
        if not isinstance(data["fixtures"], list):
            raise InvalidFixturePolicy("fixtures must be an array")
        entries: set[tuple[str, str, str]] = set()
        for record in data["fixtures"]:
            if not isinstance(record, dict) or set(record) != {"path", "finding_id", "sha256", "reason"}:
                raise InvalidFixturePolicy("fixture requires path, finding_id, sha256 and reason only")
            if not all(isinstance(value, str) and value.strip() for value in record.values()):
                raise InvalidFixturePolicy("fixture fields must be nonempty strings")
            relative, finding_id, digest = record["path"], record["finding_id"], record["sha256"]
            if not _plain_path(relative) or _has_symlink(root, relative):
                raise InvalidFixturePolicy("fixture path must be exact, relative and without symlinks")
            if finding_id not in finding_ids or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise InvalidFixturePolicy("unknown finding type or invalid SHA-256")
            key = (relative, finding_id, digest)
            if key in entries:
                raise InvalidFixturePolicy("duplicate fixture identity")
            entries.add(key)
        return FixturePolicy(root, frozenset(entries))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        # TOML error text can contain the offending value: never forward it.
        raise InvalidFixturePolicy("policy could not be read or parsed") from None
