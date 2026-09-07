#!/usr/bin/env python3
"""codex_skills_sync.py - vendor + drift-gate the CPP-generated Codex skills (pull model).

codex-power-pack#75 (epic #64, single source-of-truth bridge): CxPP does NOT author
the shared CPP command families. claude-power-pack (CPP) authors those once in
`.claude/commands/<family>/` and generates per-command Codex skill dirs under its
`codex/skills/`. This repo PULLS that generated output - pinned by CPP commit SHA -
into `.codex/skills/`, and gates drift so a hand-edit of a generated skill fails CI.
CxPP-owned native skill families may also live under `.codex/skills/`; they are
explicitly excluded from this vendored manifest and refresh/prune logic.

Surfaces:
    .codex/skills/<family>-<cmd>/     generated skill dirs (SKILL.md [+ reference.md]
                                      [+ scripts/*]), byte-identical to CPP output.
    .codex/skills/agents-md-*/        CxPP-authored native AGENTS.md skills (not
                                      vendored; not covered by the drift manifest).
    .codex/skills/project-next/       CxPP-authored deterministic project triage
                                      adapter; lib/project_next owns decisions
    .codex/skills/project-lite/       CxPP-authored native project orientation skill
    .codex/skills/codex-wayfinder/    CxPP-authored multi-session decision mapping
    .codex/skills/cxpp-*/             CxPP-authored host bootstrap/status skills
    .codex/skills/spec-*/             CxPP-authored spec-kit workflow skills
    .codex/skills/woodpecker-*/       CxPP-authored Woodpecker API client skills
    .codex/skills/README.md           CxPP-authored surface note (NOT vendored; not
                                      covered by the drift manifest).
    vendor/claude-power-pack/PIN      provenance: CPP repo URL + pinned commit SHA.
    vendor/claude-power-pack/codex-skills.sha256
                                      integrity manifest (`<sha256>  <relpath>`) of
                                      every generated file under `.codex/skills/`.

Modes:
    --check   (default) recompute `.codex/skills/` hashes, compare to the manifest,
              and assert every skill's SKILL.md carries the CPP GENERATED marker;
              exit 1 on any drift. Git-free and network-free, so it runs unchanged in
              the `uv:python3.11` validate container.
    --write   re-snapshot the manifest from the current `.codex/skills/` tree (bless a
              fresh refresh). Fetches nothing.
    --refresh --cpp-root PATH [--ref SHA]
              (maintainer) mirror `<cpp-root>/codex/skills/<dir>/` -> `.codex/skills/`,
              after validating the exact clean source/ref, update PIN, then
              re-snapshot the manifest.
    --source-check --cpp-root PATH
              compare the adopted, Codex-adapted payload with a CPP checkout;
              used by CI after a shallow upstream clone to catch stale pins.
    --pin-check --cpp-root PATH
              prove the checkout is the exact clean PIN and compare complete
              adapted/generated/manifest/plugin payload coverage and bytes.
    --pin-ref print the strictly parsed immutable commit for safe CI checkout.
    --latest-ref
              resolve CPP main once through the fixed repository URL and print
              only its strictly validated immutable commit.
    --source-report --cpp-root PATH --ref SHA
              compare a validated immutable latest CPP checkout with the reviewed
              CxPP baseline and emit a versioned, digested, non-mutating report.

Reconcile rule (hybrid SoT): for generated shared families, edit the SOURCE in claude-power-pack
`.claude/commands/<family>/`, regenerate CPP's `codex/skills/` (`make codex-skills`
there), then re-run this with `--refresh` here. For CxPP-owned native families,
edit their `.codex/skills/<name>/` package directly and keep the allowlist below
narrow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"
VENDOR_DIR = REPO_ROOT / "vendor" / "claude-power-pack"
MANIFEST_PATH = VENDOR_DIR / "codex-skills.sha256"
PIN_PATH = VENDOR_DIR / "PIN"
ADOPTION_POLICY_PATH = VENDOR_DIR / "adoption-policy.json"
RETAIN_OVERLAY_ROOT = VENDOR_DIR / "overlays" / "retain"
PLUGINS_ROOT = REPO_ROOT / "plugins"
OVERLAY_PATH = Path(__file__).resolve()

CPP_REPO_URL = "https://github.com/cooneycw/claude-power-pack"
PIN_PULL_SOURCE = "codex/skills/"
PIN_PULL_DESTINATION = ".codex/skills/"
PIN_FIELDS = {"repo", "commit", "pulls"}
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
REPORT_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
ADOPTION_TARGET_COMMIT = "f64a654f76ea8d26a33eb33f785f6e1065a823b6"
ADOPTION_COUNTS = {"adopt": 6, "adapt": 27, "defer": 26}
ADOPTION_AUDIT_IDENTITIES = {
    "report_sha256": "cc752f61b4f8e0aef496f65f8a435192382ff3229b201918566fb4cb2252e8ba",
    "generated_at": "2026-09-07T18:37:24Z",
    "cxpp_commit": "c2deddded086f061fa0f5c4ba27ac250c831c943",
    "cxpp_tree": "5d099e9df494f83ab0b681038f1365799449b7aa",
    "baseline_pin_commit": "4726ccf43899ac20ec886e588f1b9faf3da51065",
    "baseline_manifest_sha256": (
        "c0b9908274dc1ebf76338b8a345abb6c98c28acbf9355056786fa6afbbf5d397"
    ),
    "baseline_overlay_sha256": (
        "ba6c7f5d547f570d495aecf069b75da5ee98e9ef82d82d27f861286b87232a93"
    ),
    "baseline_adapted_payload_sha256": (
        "592b37fae2a81e47b01bc8ac10a72d9ef5cdaa5cd8d98c83848dce5d968f5edb"
    ),
    "target_adapted_payload_sha256": (
        "df25b2c274a009e4e91339e061bf6563cee1f376a4cde191aaa06989b0d7e7d4"
    ),
}
ADOPTION_CHANGE_SET_SHA256 = (
    "b232d95fb3ddc6b3252609f8fa9ddda7a3d921f155d285606f3f8e2030bc817c"
)
ADOPTION_DECISIONS_SHA256 = (
    "6cf7036f98f23df04e9bc7f94393da71e83017ad76503e4d61a99b67b6208beb"
)
ADOPTION_RETAINED_PAYLOADS_SHA256 = (
    "958d4cecdb59f855e3bc0860c42b50a9c255735cb86a34b58b66755a8bc4904b"
)
ADOPTION_BOUNDARIES = {
    "excluded_source_skills": ["claude-md-help", "claude-md-lint"],
    "native_collisions": [
        "documentation-c4",
        "documentation-pptx",
        "evaluate-issue",
        "project-init",
        "project-lite",
        "project-next",
        "qa-help",
        "qa-test",
        "second-opinion-help",
        "second-opinion-models",
        "second-opinion-start",
        "security-deep",
        "security-help",
        "security-quick",
        "security-scan",
        "self-improvement-retro",
    ],
    "missing_plugin_destinations": [
        {"skill": "flow-register", "reason": "no-contract-record"},
        {"skill": "flow-wave", "reason": "no-contract-record"},
    ],
    "reviewed_exclusions": [
        "browser-help",
        "browser-session",
        "cicd-woodpecker",
        "cpp-dockers",
        "cpp-happy-check",
        "cpp-help",
        "cpp-load-best-practices",
        "cpp-load-mcp-docs",
        "flow-auto_codex",
        "flow-repair",
    ],
}

# The GENERATED marker CPP's codex-skill-sync.py stamps into every skill it emits.
MARKER_PREFIX = "<!-- GENERATED by claude-power-pack"

# Shared families CPP generates that CxPP does NOT adopt (a CxPP-owned pull policy).
# `claude-md` is Out-of-Scope per the plugin-marketplace-modernization spec: CxPP is
# the AGENTS.md world, and a Codex-native `agents-md` family covers it (epic #64/#66),
# so CPP's CLAUDE.md-oriented claude-md skills are not pulled here (codex-power-pack#75).
PULL_EXCLUDE_FAMILIES = {"claude-md", "agents-md"}

# CxPP-owned top-level files that live under .codex/skills/ but are NOT pulled from
# CPP, so the drift manifest and copy/prune logic must leave them alone.
LOCAL_FILES = {"README.md"}

# CxPP-owned native skill dirs under .codex/skills/. These are edited in this repo
# and intentionally do not carry the CPP GENERATED marker. project-next is not a
# prompt-policy fork: docs/project-next-contract.md and lib/project_next are the
# authoritative cross-harness behavioral contract, while this native skill is a
# thin Codex adapter. Keep this allowlist narrow so generated CPP drift stays
# protected.
LOCAL_SKILL_DIRS = {
    "agents-md-help",
    "agents-md-lint",
    "claude-code-review",
    "codex-wayfinder",
    "cxpp-init",
    "cxpp-status",
    "cxpp-update",
    "documentation-c4",
    "documentation-pptx",
    "project-lite",
    "project-init",
    "project-next",
    "qa-help",
    "qa-test",
    "second-opinion-help",
    "second-opinion-models",
    "second-opinion-start",
    "security-deep",
    "security-help",
    "security-quick",
    "security-scan",
    "self-improvement-retro",
    "spec-adopt",
    "spec-sync",
    "evaluate-issue",
    "woodpecker-help",
    "woodpecker-logs",
    "woodpecker-restart",
    "woodpecker-status",
}

# Helpers that execute as part of an installed flow skill.  CPP's generated
# references use Claude's stable ~/.claude/scripts location; Codex plugins do
# not populate that directory.  CxPP ships these files inside each skill and
# resolves them from the skill package instead (issue #139).
FLOW_RUNTIME_HELPERS = {
    "check-ignored-additions.sh",
    "flow-finish-gate.sh",
    "flow-live-driver-guard.sh",
    "flow-stale-check.sh",
    "flow-start-resolve.sh",
    "flow-worktree-guard.sh",
    "friction-log.sh",
    "gh-pr-merge.sh",
    "hook-permission-census.sh",
    "worktree-remove.sh",
}

FLOW_AUTO_DESCRIPTION = (
    "Deliver an open GitHub issue end to end through an isolated worktree, "
    "necessity and approval gates, implementation, tests, PR, merge, CI, and "
    "optional deployment. Use for issue-lifecycle requests; do not use for "
    "questions, ordinary repository edits, or closed issues without approval."
)

LEGACY_SKILL_REPLACEMENTS = {
    "cpp-init": "cxpp-init",
    "cpp-status": "cxpp-status",
    "cpp-update": "cxpp-update",
    "codex-code_review": "claude-code-review",
}

_CODEX_PROJECT_HELP_BODY = """# Project Skills

Use project skills for three distinct goals. Select one explicitly with
`$skill-name`, discover installed skills with `/skills`, or describe the matching
goal in ordinary language when the skill is eligible for implicit selection.

| Goal | Owning skill | Boundary |
|---|---|---|
| Create a new local Python project | `$project-init` | Explicit-only; confirms the path and optional Git/commit |
| Orient quickly inside an existing repository | `$project-lite` | Read-only; never scaffolds a project |
| Recommend the next repository action | `$project-next` | Read-only triage; never starts issue work |

`$project-init` creates only a local Python scaffold. It does not publish to
GitHub, install Codex Power Pack, adopt Spec Kit, create issues, or add persistent
guidance. Those are separate, consented handoffs:

- GitHub publication: use a repository-aware GitHub workflow after reviewing
  owner, name, visibility, remote, and first push.
- Spec Kit adoption: use `$spec-adopt`.
- Approved spec-to-issue synchronization: use `$spec-sync`.
- Persistent Codex Power Pack guidance or hooks: use `$cxpp-init`.

Do not select `$project-init` for existing-repository orientation, next-work
analysis, publication, Spec Kit operations, ordinary repository changes, or any
request that does not explicitly ask for a new local Python project.
"""

SKILL_DIR_TOKEN = "<SKILL_DIR>"
_GENERIC_WORKTREE_ADAPTATION = (
    "- Native worktrees (`EnterWorktree`/`ExitWorktree` tool calls,"
    " `.claude/worktrees/` paths): use plain git instead -"
    " `git worktree add <path> -b <branch>`, work inside it, then"
    " `git worktree remove <path>` when done."
)
_CXPP_WORKTREE_ADAPTATION = (
    "- Codex worktrees: use the bundled resolver and plain git. Worktrees live"
    " at `$FLOW_WORKTREE_BASE/<repo>-<branch>` when configured, otherwise as a"
    " visible sibling `../<repo>-<branch>`; enter with `cd` and clean up with"
    " `git worktree remove`. Never use Claude's hidden worktree directory."
)
_SKILL_HELPER_PREAMBLE = f"""## Codex installed-skill runtime contract

`{SKILL_DIR_TOKEN}` below means the absolute directory containing this loaded
skill's `SKILL.md`. Resolve it from the skill locator before running a command;
never interpret bundled helper paths relative to the target repository. The
bundled resolver always selects the plain-git lane and creates visible sibling
worktrees (or uses `FLOW_WORKTREE_BASE` when configured).

"""
_CLAUDE_CICD_DISCOVERY = (
    "for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do"
)
_CODEX_CICD_DISCOVERY = f"""# Prefer the CxPP-owned runner. The first two candidates cover a
# repo-local .codex skill and a checkout-local plugin respectively; installed
# marketplace skills then fall through to the standard CxPP checkout locations.
# claude-power-pack is an explicit compatibility fallback only (CxPP #142).
for dir in \\
  "{SKILL_DIR_TOKEN}/../../.." \\
  "{SKILL_DIR_TOKEN}/../../../.." \\
  "$HOME/Projects/codex-power-pack" \\
  /opt/codex-power-pack \\
  "$HOME/.codex-power-pack" \\
  "$HOME/Projects/claude-power-pack" \\
  /opt/claude-power-pack \\
  "$HOME/.claude-power-pack"; do"""
_GITHUB_REPO_PREAMBLE = """## Codex target-repository contract

Resolve `REPO` from an explicit `owner/repo` argument when supplied; otherwise
run `gh repo view --json nameWithOwner --jq .nameWithOwner` in the current
checkout. Pass `--repo "$REPO"` to every issue command. If neither source can
resolve a repository, ask the user before performing a write.

"""
_CLAUDE_REVIEW_ESCALATION = """If implementation hits a blocker:
- Make up to two materially distinct, evidence-driven attempts to resolve it
  locally. Repeating the same failing command or edit does not count as a new
  attempt.
- If the blocker persists, invoke `$claude-code-review` (the Codex-native
  `claude:code_review` capability) once for that blocker fingerprint. Give it
  the issue criteria, failed approaches, safe error summary, and current
  worktree. Claude is read-only support; Codex remains responsible for every
  edit and decision.
- Verify Claude's findings against the code, apply only supported fixes, and
  rerun the focused test. If the skill or SDK is unavailable, continue directly
  to the normal STOP path.
- If the blocker remains unresolved after the review, **STOP** and report it.
- Suggest manual intervention."""
_CODEX_DOCTOR_HELPERS = f"""# Installed Codex flow helper family (issue #139).
# Resolve SKILL_DIR from this loaded flow-doctor skill before running.
FLOW_SKILLS_ROOT="{SKILL_DIR_TOKEN}/.."
for script in flow-start-resolve.sh flow-stale-check.sh flow-worktree-guard.sh \
  flow-live-driver-guard.sh gh-pr-merge.sh; do
  helper=$(find "$FLOW_SKILLS_ROOT" -path "*/scripts/$script" -type f -perm -u+x -print -quit)
  if [ -n "$helper" ]; then
    echo "PASS $script (bundled Codex flow helper)"
  else
    echo "FAIL $script (missing from installed flow plugin; reinstall or upgrade flow@codex-power-pack)"
  fi
done"""


class IntegrityError(ValueError):
    """A provenance, source, manifest, or payload integrity violation."""


class Pin(NamedTuple):
    repo: str
    commit: str
    source: str
    destination: str


class PreparedPayload(NamedTuple):
    content: bytes
    mode: int


class PreparedPlugin(NamedTuple):
    destination: Path
    metadata: PreparedPayload | None


class AdoptionDisposition(NamedTuple):
    path: str
    source_change: str
    action: str
    owner: str
    reason: str
    retained: PreparedPayload | None


class AdoptionPolicy(NamedTuple):
    source_commit: str
    source_tree: str
    source_skills_tree: str
    dispositions: dict[str, AdoptionDisposition]
    policy_sha256: str
    historical_audit: dict[str, object]
    boundaries: dict[str, object]


def _safe_relative_path(value: str, *, label: str, trailing_slash: bool = False) -> str:
    """Validate a repository-relative POSIX path without normalizing attacker input."""
    if not value or "\x00" in value or "\\" in value or value.startswith("/"):
        raise IntegrityError(f"{label}: expected a safe relative POSIX path")
    if trailing_slash != value.endswith("/"):
        suffix = " with a trailing slash" if trailing_slash else " without a trailing slash"
        raise IntegrityError(f"{label}: expected a file path{suffix}")
    trimmed = value[:-1] if trailing_slash else value
    parts = trimmed.split("/")
    if not trimmed or any(part in {"", ".", ".."} for part in parts):
        raise IntegrityError(f"{label}: path is empty, non-normalized, or escapes its root")
    if re.match(r"^[A-Za-z]:", parts[0]):
        raise IntegrityError(f"{label}: drive-qualified paths are not allowed")
    return value


def _github_repo_identity(value: str) -> tuple[str, str]:
    """Return a normalized GitHub owner/repository for documented safe URL forms."""
    patterns = (
        r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?",
        r"ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group(1).lower(), match.group(2).lower()
    raise IntegrityError("repository URL is not a documented credential-free GitHub spelling")


def read_pin(path: Path | None = None) -> Pin:
    """Parse the provenance file strictly; duplicate or unknown fields are invalid."""
    pin_path = path or PIN_PATH
    if not pin_path.is_file():
        raise IntegrityError(f"PIN is missing at {pin_path}")

    fields: dict[str, str] = {}
    for line_number, raw in enumerate(pin_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise IntegrityError(f"PIN line {line_number}: expected 'field: value'")
        if key not in PIN_FIELDS:
            raise IntegrityError(f"PIN line {line_number}: unknown field '{key}'")
        if key in fields:
            raise IntegrityError(f"PIN line {line_number}: duplicate field '{key}'")
        fields[key] = value

    missing = sorted(PIN_FIELDS - fields.keys())
    if missing:
        raise IntegrityError(f"PIN missing field(s): {', '.join(missing)}")
    if not COMMIT_RE.fullmatch(fields["commit"]):
        raise IntegrityError("PIN commit must be exactly 40 lowercase hexadecimal characters")
    if _github_repo_identity(fields["repo"]) != _github_repo_identity(CPP_REPO_URL):
        raise IntegrityError("PIN repository does not identify cooneycw/claude-power-pack")

    pulls = re.fullmatch(r"(\S+)\s+->\s+(\S+)", fields["pulls"])
    if pulls is None:
        raise IntegrityError("PIN pulls must be '<source>/  ->  <destination>/'")
    source = _safe_relative_path(pulls.group(1), label="PIN pulls source", trailing_slash=True)
    destination = _safe_relative_path(
        pulls.group(2), label="PIN pulls destination", trailing_slash=True
    )
    if source != PIN_PULL_SOURCE or destination != PIN_PULL_DESTINATION:
        raise IntegrityError(
            f"PIN pulls must map {PIN_PULL_SOURCE} to {PIN_PULL_DESTINATION}"
        )
    return Pin(fields["repo"], fields["commit"], source, destination)


def _git_output(cpp_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cpp_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if completed.returncode != 0:
        raise IntegrityError(f"source checkout failed git {args[0]} validation")
    return completed.stdout.strip()


def _git_bytes(cpp_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(cpp_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise IntegrityError(f"source checkout failed git {args[0]} validation")
    return completed.stdout


def _resolve_latest_cpp_commit(repo: str = CPP_REPO_URL) -> str:
    """Resolve CPP main once and reject anything except one immutable ref."""
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--exit-code", repo, "refs/heads/main"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError as exc:
        raise IntegrityError("latest CPP ref resolution could not execute Git") from exc
    if completed.returncode != 0:
        raise IntegrityError("latest CPP ref resolution failed")
    lines = completed.stdout.splitlines()
    if len(lines) != 1:
        raise IntegrityError("latest CPP ref resolution must return exactly one result")
    fields = lines[0].split("\t")
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise IntegrityError("latest CPP ref resolution returned an unexpected ref")
    commit = fields[0]
    if not COMMIT_RE.fullmatch(commit):
        raise IntegrityError("latest CPP ref is not a 40-character lowercase commit")
    return commit


def _assert_no_symlinks(root: Path, *, label: str) -> None:
    if root.is_symlink():
        raise IntegrityError(f"{label}: root may not be a symlink")
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_symlink():
            rel = path.relative_to(root).as_posix()
            raise IntegrityError(f"{label}: symlink path is unsafe: {rel}")


def _validate_source_checkout(cpp_root: Path, *, commit: str, repo: str) -> tuple[str, str]:
    """Validate source identity and cleanliness without trusting a branch label."""
    if cpp_root.is_symlink() or not cpp_root.is_dir():
        raise IntegrityError("source checkout must be an existing non-symlink directory")
    if not COMMIT_RE.fullmatch(commit):
        raise IntegrityError("source ref must be exactly 40 lowercase hexadecimal characters")

    resolved_root = cpp_root.resolve()
    top_level = Path(_git_output(cpp_root, "rev-parse", "--show-toplevel")).resolve()
    if top_level != resolved_root:
        raise IntegrityError("source path must name the Git worktree root")
    origin = _git_output(cpp_root, "remote", "get-url", "origin")
    if _github_repo_identity(origin) != _github_repo_identity(repo):
        raise IntegrityError("source origin does not match the PIN repository")

    _git_output(cpp_root, "cat-file", "-e", f"{commit}^{{commit}}")
    head = _git_output(cpp_root, "rev-parse", "HEAD")
    if head != commit:
        raise IntegrityError(f"source HEAD {head} does not match declared ref {commit}")
    dirty = _git_output(cpp_root, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise IntegrityError("source checkout is dirty")

    source_root = cpp_root / PIN_PULL_SOURCE
    if not source_root.is_dir():
        raise IntegrityError(f"source checkout has no {PIN_PULL_SOURCE}")
    _assert_no_symlinks(source_root, label="source payload")
    tree = _git_output(cpp_root, "rev-parse", "HEAD^{tree}")
    return head, tree


def _assert_repo_ancestors_safe(path: Path, *, label: str) -> None:
    """Reject lexical or symlink redirection at any component below REPO_ROOT."""
    lexical_repo = REPO_ROOT.absolute()
    lexical_path = path.absolute()
    try:
        relative = lexical_path.relative_to(lexical_repo)
    except ValueError as exc:
        raise IntegrityError(f"{label}: destination escapes repository root") from exc

    current = lexical_repo
    for index, part in enumerate(relative.parts):
        current /= part
        if current.is_symlink():
            raise IntegrityError(f"{label}: symlink component is unsafe: {current}")
        if index < len(relative.parts) - 1 and current.exists() and not current.is_dir():
            raise IntegrityError(f"{label}: parent component is not a directory: {current}")

    resolved_repo = REPO_ROOT.resolve()
    if not path.resolve(strict=False).is_relative_to(resolved_repo):
        raise IntegrityError(f"{label}: destination escapes repository root")


def _assert_destination_tree_safe(root: Path, *, label: str) -> None:
    """Reject roots, ancestors, or existing descendants that redirect writes."""
    _assert_repo_ancestors_safe(root, label=label)
    if root.exists() and not root.is_dir():
        raise IntegrityError(f"{label}: destination root is not a directory")
    _assert_no_symlinks(root, label=label)


def _assert_publication_file_safe(path: Path, *, label: str) -> None:
    """Require a regular-or-absent in-repo file with ordinary directory parents."""
    _assert_repo_ancestors_safe(path, label=label)
    if path.exists() and not path.is_file():
        raise IntegrityError(f"{label}: existing destination is not a regular file")


def _is_local_path(path: Path) -> bool:
    rel = path.relative_to(SKILLS_ROOT)
    first = rel.parts[0]
    return first in LOCAL_FILES or first in LOCAL_SKILL_DIRS


def _is_python_cache(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def _generated_files() -> list[Path]:
    """Every pulled file under .codex/skills/ - i.e. files inside a skill subdir.

    Top-level files and CxPP-owned native skill dirs are excluded: they are owned
    here, not vendored, so they are not part of the drift surface.
    """
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(
        p
        for p in SKILLS_ROOT.rglob("*")
        if p.is_file()
        and not _is_python_cache(p)
        and not _is_local_path(p)
        and len(p.relative_to(SKILLS_ROOT).parts) > 1
    )


def _rel(path: Path) -> str:
    return path.relative_to(SKILLS_ROOT).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_manifest() -> dict[str, str]:
    """Map `<relpath>` -> sha256 for every generated file under .codex/skills/."""
    return {_rel(p): _sha256(p) for p in _generated_files()}


def format_manifest(manifest: dict[str, str]) -> str:
    lines = [f"{digest}  {rel}" for rel, digest in sorted(manifest.items())]
    return "\n".join(lines) + ("\n" if lines else "")


def read_manifest(path: Path | None = None) -> dict[str, str]:
    manifest_path = path or MANIFEST_PATH
    if not manifest_path.is_file():
        return {}
    manifest: dict[str, str] = {}
    for line_number, raw in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (\S+)", raw)
        if match is None:
            raise IntegrityError(
                f"manifest line {line_number}: expected '<64 lowercase hex>  <relative path>'"
            )
        digest, rel = match.groups()
        if not DIGEST_RE.fullmatch(digest):
            raise IntegrityError(f"manifest line {line_number}: malformed digest")
        _safe_relative_path(rel, label=f"manifest line {line_number}")
        if rel in manifest:
            raise IntegrityError(f"manifest line {line_number}: duplicate path '{rel}'")
        manifest[rel] = digest
    return manifest


def _skill_dirs() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(d for d in SKILLS_ROOT.iterdir() if d.is_dir())


def _generated_skill_dirs() -> list[Path]:
    return sorted(d for d in _skill_dirs() if d.name not in LOCAL_SKILL_DIRS)


def _marker_violations() -> list[str]:
    """Skill dirs whose SKILL.md is missing or does not carry the GENERATED marker."""
    violations: list[str] = []
    for skill_dir in _generated_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            violations.append(f"{skill_dir.name}: no SKILL.md")
        elif MARKER_PREFIX not in skill_md.read_text():
            violations.append(f"{skill_dir.name}: SKILL.md missing GENERATED marker")
    return violations


def run_check() -> int:
    try:
        pin = read_pin()
        _load_adoption_policy(required=pin.commit == ADOPTION_TARGET_COMMIT)
        expected = read_manifest()
        _assert_destination_tree_safe(SKILLS_ROOT, label="generated skills")
    except IntegrityError as exc:
        print(f"codex-skills-sync: invalid provenance: {exc}", file=sys.stderr)
        return 1
    if not expected:
        print(
            "codex-skills-sync: no manifest at"
            f" {MANIFEST_PATH.relative_to(REPO_ROOT)}; run --refresh to pull from CPP.",
            file=sys.stderr,
        )
        return 1

    actual = compute_manifest()
    drift = 0

    for rel in sorted(set(expected) - set(actual)):
        print(f"MISSING: .codex/skills/{rel} (in manifest, not on disk)")
        drift = 1
    for rel in sorted(set(actual) - set(expected)):
        print(f"EXTRA: .codex/skills/{rel} (on disk, not in manifest)")
        drift = 1
    for rel in sorted(set(expected) & set(actual)):
        if expected[rel] != actual[rel]:
            print(f"DRIFT: .codex/skills/{rel} differs from the vendored (pinned) copy")
            drift = 1

    for violation in _marker_violations():
        print(f"MARKER: .codex/skills/{violation}")
        drift = 1

    if drift:
        print(
            "\ncodex-skills-sync: DRIFT detected. These are generated from"
            " claude-power-pack; do not hand-edit. To reconcile, edit the SOURCE in"
            " claude-power-pack .claude/commands/<family>/, regenerate there"
            " (make codex-skills), then re-run: scripts/codex_skills_sync.py --refresh"
            " --cpp-root <path>",
            file=sys.stderr,
        )
        return 1

    print(f"codex-skills-sync: {len(actual)} file(s) across {len(_generated_skill_dirs())} generated skill(s) in sync")
    return 0


def run_write() -> int:
    try:
        pin = read_pin()
        if pin.commit == ADOPTION_TARGET_COMMIT:
            raise IntegrityError(
                "selective-adoption manifests may be written only by --refresh from the exact source"
            )
        _assert_destination_tree_safe(SKILLS_ROOT, label="generated skills")
    except IntegrityError as exc:
        print(f"codex-skills-sync: snapshot refused: {exc}", file=sys.stderr)
        return 1
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    manifest = compute_manifest()
    MANIFEST_PATH.write_text(format_manifest(manifest))
    print(
        f"codex-skills-sync: snapshot {len(manifest)} file(s) ->"
        f" {MANIFEST_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


def _write_pin(ref: str) -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pinned claude-power-pack source for the generated Codex skills (pull model).",
        "# Managed by scripts/codex_skills_sync.py --refresh; do not hand-edit.",
        f"repo: {CPP_REPO_URL}",
        f"commit: {ref}",
        f"pulls: {PIN_PULL_SOURCE}  ->  {PIN_PULL_DESTINATION}",
        "",
    ]
    PIN_PATH.write_text("\n".join(lines))


def _source_skill_dirs(cpp_root: Path) -> list[Path]:
    src_root = cpp_root / "codex" / "skills"
    if not src_root.is_dir():
        return []
    excluded_prefixes = tuple(f"{fam}-" for fam in PULL_EXCLUDE_FAMILIES)
    return sorted(
        d
        for d in src_root.iterdir()
        if d.is_dir()
        and (d / "SKILL.md").is_file()
        and not d.name.startswith(excluded_prefixes)
        # A newly generated upstream command must never overwrite a native
        # CxPP skill with the same name (#135/#139).
        and d.name not in LOCAL_SKILL_DIRS
    )


def _git_source_payloads(
    cpp_root: Path, commit: str
) -> dict[str, dict[str, PreparedPayload]]:
    """Load every adopted input from immutable Git blobs and verify the checkout.

    `git status` can hide modified paths through index flags and ignored files.  The
    exact-pin lane therefore derives its input inventory and bytes from the pinned
    tree, then independently proves that the filesystem view has no consumed-file
    additions, removals, byte changes, or executable-bit changes.
    """
    raw_tree = _git_bytes(
        cpp_root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        commit,
        "--",
        PIN_PULL_SOURCE.rstrip("/"),
    )
    tree_entries: dict[str, tuple[str, str]] = {}
    prefix = PIN_PULL_SOURCE
    for raw_entry in raw_tree.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        if not separator:
            raise IntegrityError("pinned source tree contains a malformed entry")
        try:
            mode, object_type, object_id = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise IntegrityError("pinned source tree contains an unsupported entry") from exc
        if not path.startswith(prefix):
            raise IntegrityError(f"pinned source path escapes {prefix}: {path}")
        rel = _safe_relative_path(path[len(prefix) :], label="pinned source path")
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise IntegrityError(f"pinned source path has unsafe Git mode/type: {path}")
        if rel in tree_entries:
            raise IntegrityError(f"pinned source tree has duplicate path: {rel}")
        tree_entries[rel] = (mode, object_id)

    excluded_prefixes = tuple(f"{family}-" for family in PULL_EXCLUDE_FAMILIES)
    skill_names = {
        rel.partition("/")[0]
        for rel in tree_entries
        if "/" in rel and rel.endswith("/SKILL.md")
    }
    skill_names = {
        name
        for name in skill_names
        if not name.startswith(excluded_prefixes) and name not in LOCAL_SKILL_DIRS
    }
    if not skill_names:
        raise IntegrityError("pinned source tree has no adopted generated skills")

    immutable: dict[str, dict[str, PreparedPayload]] = {
        name: {} for name in sorted(skill_names)
    }
    for rel, (mode, object_id) in sorted(tree_entries.items()):
        skill_name, separator, skill_rel = rel.partition("/")
        if not separator or skill_name not in immutable:
            continue
        rel_path = Path(skill_rel)
        if _is_python_cache(rel_path):
            continue
        if skill_name == "evaluate-help" and skill_rel == "scripts/speckit-tasks-to-issues.sh":
            continue
        content = _git_bytes(cpp_root, "cat-file", "blob", object_id)
        immutable[skill_name][skill_rel] = PreparedPayload(
            content, 0o755 if mode == "100755" else 0o644
        )

    actual_skill_dirs = {path.name: path for path in _source_skill_dirs(cpp_root)}
    if set(actual_skill_dirs) != set(immutable):
        missing = sorted(set(immutable) - set(actual_skill_dirs))
        extra = sorted(set(actual_skill_dirs) - set(immutable))
        raise IntegrityError(
            f"source skill inventory differs from pinned tree: missing={missing}, extra={extra}"
        )

    for skill_name, expected in immutable.items():
        skill_dir = actual_skill_dirs[skill_name]
        actual_paths = {
            path.relative_to(skill_dir).as_posix(): path
            for path in skill_dir.rglob("*")
            if path.is_file()
            and not _is_python_cache(path)
            and not (
                skill_name == "evaluate-help"
                and path.relative_to(skill_dir).as_posix()
                == "scripts/speckit-tasks-to-issues.sh"
            )
        }
        if set(actual_paths) != set(expected):
            missing = sorted(set(expected) - set(actual_paths))
            extra = sorted(set(actual_paths) - set(expected))
            raise IntegrityError(
                f"source skill {skill_name} differs from pinned file inventory: "
                f"missing={missing}, extra={extra}"
            )
        for rel, pinned in expected.items():
            path = actual_paths[rel]
            if path.read_bytes() != pinned.content:
                raise IntegrityError(
                    f"source skill {skill_name}/{rel} differs from pinned Git blob"
                )
            executable = bool(path.stat().st_mode & 0o111)
            if executable != bool(pinned.mode & 0o111):
                raise IntegrityError(
                    f"source skill {skill_name}/{rel} executable bit differs from pinned tree"
                )
    return immutable


def _adapt_flow_text(skill_dir: Path, source_file: Path, text: str) -> str:
    """Apply the narrow CxPP-owned Codex runtime overlay to flow payloads."""
    if not skill_dir.name.startswith("flow-"):
        return text

    text = text.replace(_GENERIC_WORKTREE_ADAPTATION, _CXPP_WORKTREE_ADAPTATION)
    text = text.replace(".claude/friction.jsonl", ".codex/friction.jsonl")
    text = text.replace(".claude/security.yml", ".codex/security.yml")

    for helper in sorted(FLOW_RUNTIME_HELPERS):
        helper_owner = next(
            (
                candidate
                for candidate in (
                    skill_dir,
                    skill_dir.parent / "flow-start",
                    skill_dir.parent / "flow-auto",
                    skill_dir.parent / "flow-merge",
                )
                if (candidate / "scripts" / helper).is_file()
            ),
            None,
        )
        if helper_owner is None:
            continue
        if helper_owner == skill_dir:
            resolved = f"{SKILL_DIR_TOKEN}/scripts/{helper}"
        else:
            resolved = f"{SKILL_DIR_TOKEN}/../{helper_owner.name}/scripts/{helper}"
        text = text.replace(f"~/.claude/scripts/{helper}", resolved)
        text = re.sub(
            rf"(?<![/A-Za-z0-9_.-])scripts/{re.escape(helper)}",
            resolved,
            text,
        )

    # New upstream prose can refer to the stable Claude helper directory
    # without naming an individual helper (#590). Codex packages helpers with
    # the loaded skill, so the generic directory must follow the same overlay.
    text = text.replace("~/.claude/scripts/", f"{SKILL_DIR_TOKEN}/scripts/")

    # Generated references describe Claude's native hidden worktrees.  The
    # SKILL.md adaptation and resolver below are authoritative for Codex, but
    # remove the stale path spellings as well so examples cannot be followed
    # literally and the harness lint remains meaningful.
    text = text.replace(".claude/worktrees", "../<repo>-<branch>")
    text = text.replace(
        "Helpers are invoked bare at their stable `~/.claude/scripts/` paths",
        "Helpers are invoked by absolute path from the installed Codex skill package",
    )

    if skill_dir.name == "flow-doctor" and source_file.name == "reference.md":
        text = re.sub(
            r"# Flow helper family \(issue #581\):.*?^done$",
            _CODEX_DOCTOR_HELPERS,
            text,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
        text = text.replace(
            "| Flow helper family | ✅/⚠️ | flow-start-resolve, flow-stale-check,"
            " flow-worktree-guard, flow-live-driver-guard, gh-pr-merge at"
            " ~/.claude/scripts/ (zero-prompt lane, #581) |",
            "| Flow helper family | ✅/❌ | Bundled executable helpers in the installed"
            " flow skill packages (#139) |",
        )
        text = text.replace(
            "2c. ⚠️ **Flow helper(s) not at ~/.claude/scripts/** - the #581 zero-prompt"
            " lane degrades to CPP-checkout fallback paths, which prompt. Run"
            " `/cpp:update` (Step 5b re-links new scripts) or `/cpp:init` Tier 2",
            "2c. ❌ **Bundled Codex flow helper(s) missing** - reinstall or upgrade"
            " `flow@codex-power-pack`; a CPP clone is not required.",
        )

    if source_file.name == "reference.md" and SKILL_DIR_TOKEN in text:
        marker_end = text.find("\n\n")
        if marker_end != -1 and _SKILL_HELPER_PREAMBLE not in text:
            text = text[: marker_end + 2] + _SKILL_HELPER_PREAMBLE + text[marker_end + 2 :]
    return text


def _adapt_flow_cicd_runtime(skill_dir: Path, source_file: Path, text: str) -> str:
    """Prefer CxPP's runner in Codex finish lanes, retaining CPP as fallback."""
    if source_file.name != "reference.md" or skill_dir.name not in {
        "flow-auto",
        "flow-finish",
        "flow-merge",
    }:
        return text

    discovery = re.compile(
        rf'^(?P<indent>[ \t]*)CPP_DIR=""\n(?P=indent)'
        rf'{re.escape(_CLAUDE_CICD_DISCOVERY)}\n(?P<body>.*?)\n(?P=indent)done',
        re.DOTALL | re.MULTILINE,
    )

    def adapt_match(match: re.Match[str]) -> str:
        # A flow reference can also locate CPP solely for legacy helper scripts.
        # Adapt only blocks whose nearby command actually invokes lib.cicd.
        if "python -m lib.cicd" not in text[match.end() : match.end() + 1600]:
            return match.group(0)
        indent = match.group("indent")
        body = match.group("body").replace(
            'if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then',
            'if [ -d "$dir/lib/cicd" ] && '
            '{ [ -f "$dir/AGENTS.md" ] || [ -f "$dir/CLAUDE.md" ]; }; then',
        )
        body = body.replace(
            '[ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ] && { CPP_DIR="$dir"; break; }',
            '[ -d "$dir/lib/cicd" ] && '
            '{ [ -f "$dir/AGENTS.md" ] || [ -f "$dir/CLAUDE.md" ]; } && '
            '{ CPP_DIR="$dir"; break; }',
        )
        discovery_text = "\n".join(f"{indent}{line}" for line in _CODEX_CICD_DISCOVERY.splitlines())
        return (
            f'{indent}CPP_DIR=""\n{indent}CICD_RUNTIME_KIND=""\n{discovery_text}\n'
            f'{body}\n{indent}done\n'
            f'{indent}if [ -n "$CPP_DIR" ]; then\n'
            f'{indent}  if [ -f "$CPP_DIR/AGENTS.md" ]; then\n'
            f'{indent}    CICD_RUNTIME_KIND="cxpp"\n'
            f'{indent}  else\n'
            f'{indent}    CICD_RUNTIME_KIND="cpp-compat"\n'
            f'{indent}  fi\n'
            f'{indent}fi'
        )

    text = discovery.sub(adapt_match, text)
    runner_command = re.compile(
        r'^(?P<indent>[ \t]*)PYTHONPATH="\$CPP_DIR:\$PYTHONPATH" '
        r'uv run --project "\$CPP_DIR" python -m lib\.cicd '
        r'(?P<args>run --plan finish|check --summary)$',
        re.MULTILINE,
    )

    def adapt_runner_command(match: re.Match[str]) -> str:
        indent = match.group("indent")
        args = match.group("args")
        return (
            f'{indent}if [ "$CICD_RUNTIME_KIND" = "cxpp" ]; then\n'
            f'{indent}    PYTHONPATH="$CPP_DIR:$PYTHONPATH" '
            f'uv run python -m lib.cicd {args}\n'
            f"{indent}else\n"
            f'{indent}    PYTHONPATH="$CPP_DIR:$PYTHONPATH" '
            f'uv run --project "$CPP_DIR" python -m lib.cicd {args}\n'
            f"{indent}fi"
        )

    text = runner_command.sub(adapt_runner_command, text)
    text = text.replace("CPP checkout not found", "CxPP/CPP runtime not found")
    return text


def _adapt_flow_cicd_helper(skill_dir: Path, source_file: Path, text: str) -> str:
    """Make the bundled finish gate prefer CxPP and provision its dev runtime."""
    if source_file.name != "flow-finish-gate.sh" or not skill_dir.name.startswith("flow-"):
        return text

    upstream_discovery = """# --- Locate the CPP checkout (same search the command docs use) -------------
if [[ -n "${FLOW_GATE_CPP_DIR+x}" ]]; then
    CPP_DIR="$FLOW_GATE_CPP_DIR"
else
    CPP_DIR=""
    for dir in "$HOME/Projects/claude-power-pack" /opt/claude-power-pack "$HOME/.claude-power-pack"; do
        if [[ -d "$dir" && -f "$dir/CLAUDE.md" ]]; then
            CPP_DIR="$dir"
            break
        fi
    done
fi
"""
    codex_discovery = """# --- Locate the CxPP runner, retaining CPP as compatibility fallback --------
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Bare helper invocation cannot prefix uv with an environment assignment. Keep
# caller configuration when present; otherwise use a cache location that is
# writable in restricted agent sandboxes as well as normal shells.
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/codex-power-pack-uv-cache}"
if [[ -n "${FLOW_GATE_CPP_DIR+x}" ]]; then
    CPP_DIR="$FLOW_GATE_CPP_DIR"
else
    CPP_DIR=""
    for dir in \\
        "$SCRIPT_DIR/../../../.." \\
        "$SCRIPT_DIR/../../../../.." \\
        "$HOME/Projects/codex-power-pack" \\
        /opt/codex-power-pack \\
        "$HOME/.codex-power-pack" \\
        "$HOME/Projects/claude-power-pack" \\
        /opt/claude-power-pack \\
        "$HOME/.claude-power-pack"; do
        if [[ -d "$dir/lib/cicd" && ( -f "$dir/AGENTS.md" || -f "$dir/CLAUDE.md" ) ]]; then
            CPP_DIR="$dir"
            break
        fi
    done
fi

CICD_RUNTIME_KIND=""
if [[ -n "$CPP_DIR" ]]; then
    if [[ -f "$CPP_DIR/AGENTS.md" ]]; then
        CICD_RUNTIME_KIND="cxpp"
    else
        CICD_RUNTIME_KIND="cpp-compat"
    fi
fi

# Keep the source helper's runner command shape, including its targeted-rerun
# environment contract, and add only CxPP's dependency selection.  An argv
# array works for both the summary and piped runner commands without moving the
# CPP_GATE_RERUN_FAILED assignment across a shell control-flow boundary.
CICD_UV_ARGS=(--project "$CPP_DIR")
if [[ "$CICD_RUNTIME_KIND" == "cxpp" ]]; then
    CICD_UV_ARGS+=(--extra dev)
fi
"""
    if upstream_discovery not in text:
        return text
    text = text.replace(upstream_discovery, codex_discovery, 1)
    text = text.replace("CPP checkout not found", "CxPP/CPP runtime not found")

    text = text.replace(
        'uv run --project "$CPP_DIR" python -m lib.cicd',
        'uv run "${CICD_UV_ARGS[@]}" python -m lib.cicd',
    )
    return text


def _adapt_flow_ci_status(skill_dir: Path, source_file: Path, text: str) -> str:
    """Require the CxPP CI helper to identify one repo, checkout, and SHA."""
    if skill_dir.name != "flow-auto" or source_file.name != "flow-ci-status.sh":
        return text

    text = text.replace(
        "flow-ci-status.sh [SHA] [--path <checkout>] [--repo <owner/name>]",
        "flow-ci-status.sh SHA --path <checkout> --repo <owner/name>",
    )
    start = '[[ -n "$CHECK_PATH" ]] || CHECK_PATH="$PWD"\n'
    replacement = """[[ -n "$SHA" ]] || die_usage "SHA is required"
[[ -n "$CHECK_PATH" ]] || die_usage "--path is required"
[[ -n "$REPO" ]] || die_usage "--repo is required"
"""
    if start not in text:
        raise IntegrityError("flow-ci-status source no longer has the reviewed identity block")
    text = text.replace(start, replacement, 1)
    repo_default = r"""if [[ -z "$REPO" ]]; then
    REPO="$("$GH_BIN" repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
fi
if [[ -z "$REPO" ]]; then
    ORIGIN="$(git -C "$CHECK_PATH" remote get-url origin 2>/dev/null)"
    # git@host:owner/name.git  or  https://host/owner/name(.git)
    REPO="$(sed -E 's#^.*[:/]([^/:]+/[^/]+?)(\.git)?$#\1#' <<<"${ORIGIN:-}")"
    [[ "$REPO" == "$ORIGIN" ]] && REPO=""
fi
if [[ -z "$REPO" ]]; then
    echo "flow-ci-status: could not resolve owner/name for $CHECK_PATH (fail-open)" >&2
    emit
fi
"""
    if repo_default not in text:
        raise IntegrityError("flow-ci-status source no longer has the reviewed repo fallback")
    return text.replace(repo_default, "", 1)


def _adapt_flow_merge_helper(skill_dir: Path, source_file: Path, text: str) -> str:
    """Keep native merge checks fail-closed and bind them to one reviewed head."""
    if source_file.name != "gh-pr-merge.sh" or skill_dir.name not in {
        "flow-auto",
        "flow-merge",
    }:
        return text

    retry = re.compile(
        r"elif \[\[ \$merge_exit -ne 0 && \$ADMIN_OPT_IN -eq 0 \]\] && "
        r"is_protection_block && is_repo_admin; then\n"
        r"(?P<body>.*?)\n"
        r"    run_squash --admin \$\{BASE_FLAGS\+\"\$\{BASE_FLAGS\[@\]\}\"\}\n",
        re.DOTALL,
    )
    replacement = """elif [[ $merge_exit -ne 0 && $ADMIN_OPT_IN -eq 0 ]] && is_protection_block; then
    echo "error: PR #$PR_NUMBER was blocked by an administrative protection rule;" \
         "refusing an automatic --admin retry." >&2
    echo "       A repository owner may explicitly re-run this helper with --admin" \
         "after reviewing the failed or unknown protection state." >&2
"""
    text, count = retry.subn(replacement, text, count=1)
    if count != 1:
        raise IntegrityError("gh-pr-merge source no longer has the reviewed admin-retry block")

    base_retry_header = re.compile(
        r"# Base moved at squash time \(issue #502\):\n.*?(?=# Branch protection)",
        re.DOTALL,
    )
    base_retry_header_replacement = """# Base moved at squash time (issue #502):
#   A sibling merge can advance the base in the poll-to-merge race window. Native
#   CxPP treats that rejection as a clean stop instead of retrying after only a
#   refetch and mergeability poll. Re-run the helper to repeat the complete
#   head/base/status/review clearance before another exact-head attempt.
#
"""
    text, count = base_retry_header.subn(base_retry_header_replacement, text, count=1)
    if count != 1:
        raise IntegrityError("gh-pr-merge source no longer has the reviewed base-retry header")

    observed_checks = re.compile(
        r"# Neither mechanism could be read \(issue #610\), so nothing is KNOWN to be\n"
        r".*?^wait_for_observed_checks\(\) \{\n.*?^\}\n",
        re.MULTILINE | re.DOTALL,
    )
    observed_replacement = r'''# Neither required-context mechanism could be read (issue #610). Native CxPP
# may use the PR rollup as evidence, but unreadable or empty evidence is UNKNOWN
# and therefore a clean stop. A red state or a state that remains pending is also
# a hard stop; the merge request is never used as a substitute status-check gate.
wait_for_observed_checks() {
    local attempts="${GH_PR_MERGE_CHECK_ATTEMPTS:-60}"
    local delay="${GH_PR_MERGE_CHECK_DELAY:-10}"
    local i line name state pending failed observed announced=0

    for ((i = 1; i <= attempts; i++)); do
        pending=""
        failed=""
        if ! observed=$(check_states); then
            echo "error: required contexts and the PR status rollup are unreadable for" \
                 "PR #$PR_NUMBER; refusing to merge with unknown CI state." >&2
            return 1
        fi
        if [[ -z "$observed" ]]; then
            echo "error: required contexts are unreadable and PR #$PR_NUMBER reports no" \
                 "status checks; refusing to treat missing CI evidence as green." >&2
            return 1
        fi
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            name="${line%%|*}"
            state="${line##*|}"
            case "${state^^}" in
                SUCCESS|NEUTRAL|SKIPPED)
                    ;;
                FAILURE|ERROR|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE)
                    failed+="${name} (${state}) "
                    ;;
                *)
                    pending+="${name} (${state}) "
                    ;;
            esac
        done <<<"$observed"

        if [[ -n "$failed" ]]; then
            echo "error: status check(s) are RED on PR #$PR_NUMBER: ${failed}" >&2
            echo "       Required contexts could not be enumerated (issue #610), but a red" \
                 "check is authoritative on its own - fix CI and push again." >&2
            return 1
        fi
        if [[ -z "$pending" ]]; then
            (( announced )) && echo "note: reported check(s) are green; merging." >&2
            return 0
        fi
        if (( i < attempts )); then
            if (( announced == 0 )); then
                echo "note: required status-check contexts are not enumerable for PR" \
                     "#$PR_NUMBER - waiting on the check(s) the PR itself reports:" \
                     "${pending}" >&2
                announced=1
            fi
            sleep "$delay"
        fi
    done

    echo "error: status check(s) are still pending or unknown on PR #$PR_NUMBER" \
         "after $attempts check(s): ${pending}" >&2
    echo "       Not merging without terminal green CI evidence." >&2
    return 1
}
'''
    text, count = observed_checks.subn(observed_replacement, text, count=1)
    if count != 1:
        raise IntegrityError("gh-pr-merge source no longer has the reviewed observed-check wait")

    base_metadata = r'''# Resolve the PR base once for every feature that needs it. A failed or empty
# metadata read remains fail-open at each caller; GitHub is the final arbiter.
PR_BASE_BRANCH=$("$GH_BIN" pr view "$PR_NUMBER" --json baseRefName --jq '.baseRefName' 2>/dev/null)
'''
    head_guard = base_metadata + r'''
# Bind every pre-merge decision to the exact PR head checked out locally. Capture
# once before the status/review gates, verify it again immediately before merge,
# and pass GitHub's atomic expected-head predicate to close the final race.
EXPECTED_HEAD_SHA=$("$GH_BIN" pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid' 2>/dev/null)
LOCAL_HEAD_SHA=$("$GIT_BIN" rev-parse HEAD 2>/dev/null)
if [[ ! "$EXPECTED_HEAD_SHA" =~ ^[0-9a-f]{40}$ || "$LOCAL_HEAD_SHA" != "$EXPECTED_HEAD_SHA" ]]; then
    echo "error: cannot bind PR #$PR_NUMBER to the checked-out head; expected a" \
         "matching 40-character headRefOid, got PR='${EXPECTED_HEAD_SHA:-unreadable}'" \
         "local='${LOCAL_HEAD_SHA:-unreadable}'." >&2
    exit 1
fi

verify_expected_head() {
    local current_pr_head current_local_head
    current_pr_head=$("$GH_BIN" pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid' 2>/dev/null) || return 1
    current_local_head=$("$GIT_BIN" rev-parse HEAD 2>/dev/null) || return 1
    [[ "$current_pr_head" =~ ^[0-9a-f]{40}$ ]] || return 1
    [[ "$current_pr_head" == "$EXPECTED_HEAD_SHA" && "$current_local_head" == "$EXPECTED_HEAD_SHA" ]]
}
'''
    if text.count(base_metadata) != 1:
        raise IntegrityError("gh-pr-merge source no longer has the reviewed base metadata read")
    text = text.replace(base_metadata, head_guard, 1)

    run_squash = re.compile(
        r"# Attempt the squash, retrying \(bounded\) only when the base moved under us at\n"
        r".*?^run_squash\(\) \{\n.*?^\}\n",
        re.MULTILINE | re.DOTALL,
    )
    run_squash_replacement = r'''# Attempt one exact-head squash. A base-move rejection is a clean stop: a fresh
# helper run must repeat the full head/base/status/review clearance before trying
# again, so a partial automatic retry can never merge a differently gated tree.
run_squash() {
    # $@: extra gh flags (--delete-branch in the primary repo)
    local errfile
    errfile=$(mktemp)
    if ! verify_expected_head; then
        echo "error: PR #$PR_NUMBER or the local checkout changed after pre-merge" \
             "validation; refusing to merge a different head." >&2
        merge_exit=1
        LAST_MERGE_ERR="PR head changed after pre-merge validation"
        rm -f "$errfile"
        return
    fi

    "$GH_BIN" pr merge "$PR_NUMBER" --squash \
        --match-head-commit "$EXPECTED_HEAD_SHA" "$@" 2>"$errfile"
    merge_exit=$?
    cat "$errfile" >&2
    LAST_MERGE_ERR=$(cat "$errfile")
    if [[ $merge_exit -ne 0 ]] && grep -q "Base branch was modified" "$errfile"; then
        echo "error: base branch moved at squash time; refusing an automatic retry" \
             "without repeating the full merge clearance." >&2
    fi
    rm -f "$errfile"
}
'''
    text, count = run_squash.subn(run_squash_replacement, text, count=1)
    if count != 1:
        raise IntegrityError("gh-pr-merge source no longer has the reviewed squash retry")

    old_retry_hooks = (
        "#   GH_PR_MERGE_BASE_RETRY_ATTEMPTS  squash retries on \"Base branch was modified\" (default: 2)\n"
        "#   GH_PR_MERGE_BASE_RETRY_DELAY     seconds before each such retry (default: 2)\n"
    )
    if text.count(old_retry_hooks) != 1:
        raise IntegrityError("gh-pr-merge source no longer has the reviewed retry hooks")
    text = text.replace(
        old_retry_hooks,
        "#   A base-move rejection is not retried automatically; re-run after regating.\n",
        1,
    )
    text = text.replace(
        "an admin override is applied automatically\n"
        "#                    only for the residual ADMINISTRATIVE protection family",
        "administrative protection is reported without retry; an explicit owner\n"
        "#                    invocation is required for any --admin override",
    )
    return text


def _adapt_deferred_native_boundaries(
    skill_dir: Path, source_file: Path, text: str
) -> str:
    """Keep unshipped Wave/spec capabilities out of the published native surface."""
    if skill_dir.name == "flow-auto" and source_file.name == "reference.md":
        capability = re.compile(
            r"## Capability contract \(issue #783\)\n.*?(?=\n## Instructions\n)",
            re.DOTALL,
        )
        text = capability.sub(
            "## Native capability boundary\n\n"
            "CPP delegated-driver capability identities are harness-specific and are not a "
            "native CxPP runtime contract. Native capability discovery, registration, and "
            "packaging remain explicit inputs to #200/#201/#202; this skill does not advertise "
            "those unshipped packages. Capability does not bypass the Step 3 necessity gate.\n",
            text,
            count=1,
        )
        text = text.replace(
            "<SKILL_DIR>/scripts/flow-ci-status.sh <merge-sha> --path /path/to/main/repo --wait",
            "<SKILL_DIR>/scripts/flow-ci-status.sh <merge-sha> --path /path/to/main/repo --repo owner/name --wait",
        )

    if skill_dir.name == "flow-help" and source_file.name == "reference.md":
        plugin_cache = re.compile(
            r"- \*\*Using a retired CPP plugin cache\*\* \(#662\):.*?"
            r"`\$flow-repair` remains compatible with the cache during migration\.\n",
            re.DOTALL,
        )
        text = plugin_cache.sub(
            "- **Migrating from a retired CPP plugin cache** (#662): remove the old Claude "
            "installation through its own plugin manager, then use `$cxpp-init` or "
            "`$cxpp-update` to install the native CxPP bundle.\n",
            text,
            count=1,
        )
        text = re.sub(
            r"^\| `(?:\$|/)flow-(?:register|wave)[^\n]*\n",
            "",
            text,
            flags=re.MULTILINE,
        )

    if skill_dir.name == "flow-eli5" and source_file.name == "reference.md":
        standalone_install = re.compile(
            r"This gate also ships standalone as \*\*eli5-gate\*\*\n.*?"
            r"issues for the gate itself belong there, not in CPP\.\n",
            re.DOTALL,
        )
        text = standalone_install.sub(
            "This gate also ships standalone as **eli5-gate** "
            "(https://github.com/cooneycw/eli5-gate). Claude users should follow that "
            "project's installation guidance; CxPP supplies the native `$flow-eli5` package. "
            "That repository remains canonical for the gate core, and improvement issues for "
            "the core belong there.\n",
            text,
            count=1,
        )
        text = text.replace(
            "and neither does `$flow-auto_codex`",
            "and neither does any separately reviewed wrapper",
        )

    if skill_dir.name == "flow-finish" and source_file.name == "reference.md":
        graduation = re.compile(
            r"When this PR closes a specification's last task, treat it as a graduation\n"
            r"candidate\..*?automatic network-coupled quality gate\.\n",
            re.DOTALL,
        )
        text, count = graduation.subn(
            "Specification graduation remains a separately reviewed native lifecycle; "
            "this refresh does not publish or invoke a graduation-ledger mutator.\n",
            text,
            count=1,
        )

    if skill_dir.name == "flow-doctor" and source_file.name == "flow-helpers-install.sh":
        deferred_helpers = {
            "flow-wave-registry.sh",
            "flow-wave-mailbox.sh",
            "flow-wave-lexicon.sh",
            "flow-wave-plan.py",
            "flow-driver-capability.sh",
            "flow-ci-status.sh",
            "flow-pr-watch.sh",
            "delegated-run-check.sh",
            "cpp-commands-link.sh",
            "install-drift.sh",
        }
        text = "\n".join(
            line for line in text.splitlines() if line.strip() not in deferred_helpers
        ) + ("\n" if text.endswith("\n") else "")
        text = text.replace("legacy plugin cache", "installed Codex plugin bundle")
        text = text.replace("legacy-cache", "plugin")
        text = text.replace("retired flow cache", "installed flow plugin")
        text = text.replace("retired cache", "installed plugin cache")
    return text


def _adapt_flow_claude_review(skill_dir: Path, source_file: Path, text: str) -> str:
    """Add CxPP's bounded cross-model escalation to Codex flow:auto."""
    if skill_dir.name != "flow-auto" or source_file.name != "reference.md":
        return text
    original = """If implementation hits a blocker that cannot be resolved:
- **STOP** and report the blocker.
- Suggest manual intervention."""
    if original in text:
        return text.replace(original, _CLAUDE_REVIEW_ESCALATION, 1)
    return text


def _adapt_flow_resolver(text: str) -> str:
    """Make CPP's resolver use Codex's plain-git visible-worktree lane."""
    text = text.replace(
        "GIT_LANE=$CROSS_REPO\n[ -n \"${FLOW_WORKTREE_BASE:-}\" ] && GIT_LANE=1",
        "# Codex has no EnterWorktree tool: every lane uses plain git.\nGIT_LANE=1",
    )
    text = text.replace(
        'echo "$TARGET_REPO/.claude/worktrees/$1"',
        'echo "$(dirname "$TARGET_REPO")/$(basename "$TARGET_REPO")-$1"',
    )
    text = text.replace(
        "<target repo>/.claude/worktrees/<branch>",
        "<target repo parent>/<repo>-<branch>",
    )
    text = text.replace(".claude/worktrees", "visible sibling worktrees")
    return text


def _adapt_github_text(skill_dir: Path, source_file: Path, text: str) -> str:
    """Keep shared GitHub skills repository-neutral on the CxPP surface."""
    if not skill_dir.name.startswith("github-"):
        return text
    text = text.replace("cooneycw/claude-power-pack", '"$REPO"')
    if source_file.name == "SKILL.md" and _GITHUB_REPO_PREAMBLE not in text:
        marker_end = text.find("\n\n")
        if marker_end != -1:
            text = text[: marker_end + 2] + _GITHUB_REPO_PREAMBLE + text[marker_end + 2 :]
    return text


def _adapt_codex_runtime_text(skill_dir: Path, source_file: Path, text: str) -> str:
    """Remove operational Claude state/runtime paths from the Codex payload."""
    if source_file.suffix not in {".md", ".sh"}:
        return text

    text = text.replace(".claude/cicd_tasks.yml", ".codex/cicd_tasks.yml")
    text = text.replace(".claude/cicd.yml", ".codex/cicd.yml")
    text = text.replace(".claude/deploy.log", ".codex/deploy.log")
    text = text.replace(".claude/secrets.yml", ".codex/secrets.yml")

    if skill_dir.name.startswith("cicd-"):
        text = text.replace(
            '$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH',
            '$PWD:$HOME/Projects/codex-power-pack:$PYTHONPATH',
        )
        text = text.replace(
            '$CPP_DIR/lib:$PYTHONPATH',
            '$HOME/Projects/codex-power-pack:$PYTHONPATH',
        )

    if skill_dir.name == "secrets-help":
        text = text.replace(
            '$HOME/Projects/claude-power-pack/lib:$PYTHONPATH',
            '$HOME/Projects/codex-power-pack:$PYTHONPATH',
        )

    if skill_dir.name == "self-improvement-deployment" and source_file.name == "reference.md":
        text = text.replace(
            "cp ~/Projects/claude-power-pack/templates/Makefile.example Makefile",
            "cp ~/Projects/codex-power-pack/templates/Makefile.example Makefile",
        )
        text = text.replace(
            "Reference template: `~/Projects/claude-power-pack/templates/Makefile.example`",
            "Reference template: `~/Projects/codex-power-pack/templates/Makefile.example`",
        )
        text = text.replace(
            'PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$HOME/Projects/claude-power-pack/lib"',
            'PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$HOME/Projects/codex-power-pack"',
        )
    return text


def _adapt_invocation_text(skill_dir: Path, source_file: Path, text: str) -> str:
    """Normalize generated user guidance to native Codex skill selection."""
    if source_file.suffix != ".md":
        return text

    text = text.replace("/claude-md-lint", "$agents-md-lint")
    text = text.replace("$claude-md-lint", "$agents-md-lint")
    text = text.replace("Audit CLAUDE.md", "Audit AGENTS.md")

    if skill_dir.name == "flow-auto" and source_file.name == "SKILL.md":
        text = re.sub(
            r'^description:.*$',
            f'description: "{FLOW_AUTO_DESCRIPTION}"',
            text,
            count=1,
            flags=re.MULTILINE,
        )

    if skill_dir.name == "project-help" and source_file.name == "SKILL.md":
        text = re.sub(
            r'^description:.*$',
            'description: "Explain which project skill owns scaffolding, orientation, and next-work triage"',
            text,
            count=1,
            flags=re.MULTILINE,
        )
        heading = text.find("# Project Commands")
        if heading != -1:
            text = text[:heading] + _CODEX_PROJECT_HELP_BODY

    if skill_dir.name == "evaluate-help" and source_file.name == "SKILL.md":
        text = text.replace(
            "Use `./scripts/speckit-tasks-to-issues.sh` to create GitHub issues from the generated tasks.",
            "Hand approved Spec Kit artifacts to `$spec-sync`; evaluate does not own or bundle\n"
            "an issue compiler.",
        )
        text = text.replace(
            "- `scripts/speckit-tasks-to-issues.sh` - Turn a spec `tasks.md` into GitHub issues",
            "- `$spec-sync` - Separately preview and compile approved artifacts into GitHub issues",
        )

    skill_names = {
        path.name
        for path in skill_dir.parent.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    } | LOCAL_SKILL_DIRS

    def replace_namespaced(match: re.Match[str]) -> str:
        candidate = f"{match.group(1)}-{match.group(2)}"
        selected = LEGACY_SKILL_REPLACEMENTS.get(candidate, candidate)
        return f"${selected}" if selected in skill_names else match.group(0)

    text = re.sub(
        r"(?<![A-Za-z0-9./])/(?!/)([a-z][a-z0-9_-]+):([a-z][a-z0-9_-]+)",
        replace_namespaced,
        text,
    )
    if skill_names:
        bare = re.compile(
            r"(?<![A-Za-z0-9./])/(?!/)("
            + "|".join(re.escape(name) for name in sorted(skill_names, key=len, reverse=True))
            + r")(?![A-Za-z0-9_-])"
        )
        text = bare.sub(lambda match: f"${match.group(1)}", text)
    return text


def _adapted_source_payloads(
    skill_dir: Path,
    immutable_payloads: dict[str, PreparedPayload] | None = None,
) -> dict[str, PreparedPayload]:
    _assert_no_symlinks(skill_dir, label=f"source skill {skill_dir.name}")
    files: dict[str, PreparedPayload] = {}
    if immutable_payloads is None:
        source_payloads = {
            path.relative_to(skill_dir).as_posix(): PreparedPayload(
                path.read_bytes(), path.stat().st_mode & 0o777
            )
            for path in skill_dir.rglob("*")
            if path.is_file() and not _is_python_cache(path)
        }
    else:
        source_payloads = immutable_payloads
    for rel, source_payload in sorted(source_payloads.items()):
        source_file = skill_dir / rel
        _safe_relative_path(rel, label=f"source skill {skill_dir.name}")
        if skill_dir.name == "evaluate-help" and rel == "scripts/speckit-tasks-to-issues.sh":
            continue
        try:
            text = source_payload.content.decode()
        except UnicodeDecodeError:
            files[rel] = source_payload
            continue
        if rel == "scripts/flow-start-resolve.sh":
            text = _adapt_flow_resolver(text)
        text = _adapt_flow_text(skill_dir, source_file, text)
        text = _adapt_flow_cicd_helper(skill_dir, source_file, text)
        text = _adapt_flow_cicd_runtime(skill_dir, source_file, text)
        text = _adapt_flow_ci_status(skill_dir, source_file, text)
        text = _adapt_flow_merge_helper(skill_dir, source_file, text)
        text = _adapt_flow_claude_review(skill_dir, source_file, text)
        text = _adapt_github_text(skill_dir, source_file, text)
        text = _adapt_codex_runtime_text(skill_dir, source_file, text)
        text = _adapt_invocation_text(skill_dir, source_file, text)
        text = _adapt_deferred_native_boundaries(skill_dir, source_file, text)
        files[rel] = PreparedPayload(text.encode(), source_payload.mode)
    return files


def _adapted_source_files(skill_dir: Path) -> dict[str, bytes]:
    return {
        rel: payload.content
        for rel, payload in _adapted_source_payloads(skill_dir).items()
    }


def _write_skill_payload(dest: Path, payloads: dict[str, PreparedPayload]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    for rel, payload in payloads.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload.content)
        target.chmod(payload.mode)


def _plugin_payload_destinations(skill_name: str) -> list[Path]:
    if not PLUGINS_ROOT.is_dir():
        raise IntegrityError(f"plugin root is missing at {PLUGINS_ROOT}")
    return sorted(
        (
            plugin_dir / "skills" / skill_name
            for plugin_dir in PLUGINS_ROOT.iterdir()
            if plugin_dir.is_dir()
        ),
        key=lambda path: len(path.parts),
    )


def _sync_plugin_payload(
    skill_name: str,
    prepared_plugin: PreparedPlugin | None = None,
    *,
    prevalidated: bool = False,
) -> None:
    """Mirror one skill, preserving only the plugin-owned openai.yaml metadata."""
    source = SKILLS_ROOT / skill_name
    if not prevalidated:
        prepared_plugin = _validate_refresh_destinations({skill_name})[skill_name]
    if prepared_plugin is None:
        return
    destination, metadata = prepared_plugin
    if not destination.is_dir():
        raise IntegrityError(f"expected plugin package is missing: {destination}")
    shutil.rmtree(destination)
    for source_file in sorted(
        path for path in source.rglob("*") if path.is_file() and not _is_python_cache(path)
    ):
        rel = source_file.relative_to(source)
        if rel.as_posix() == "agents/openai.yaml":
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
    if metadata is not None:
        metadata_path = destination / "agents" / "openai.yaml"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_bytes(metadata.content)
        metadata_path.chmod(metadata.mode)


def _prepare_source_payloads(
    cpp_root: Path,
    *,
    commit: str | None = None,
    policy: AdoptionPolicy | None = None,
) -> tuple[list[Path], dict[str, dict[str, PreparedPayload]], dict[str, bytes]]:
    source_root = cpp_root / PIN_PULL_SOURCE
    _assert_no_symlinks(source_root, label="source payload")
    src_dirs = _source_skill_dirs(cpp_root)
    if not src_dirs:
        raise IntegrityError(f"no generated skills under {cpp_root}")
    immutable_by_skill = _git_source_payloads(cpp_root, commit) if commit else None

    by_skill: dict[str, dict[str, PreparedPayload]] = {}
    for src_dir in src_dirs:
        _safe_relative_path(src_dir.name, label="source skill directory")
        immutable = immutable_by_skill[src_dir.name] if immutable_by_skill else None
        payloads = _adapted_source_payloads(src_dir, immutable)
        if not payloads:
            raise IntegrityError(f"source skill {src_dir.name} has no payload files")
        by_skill[src_dir.name] = payloads

    if policy is not None:
        by_skill = _apply_adoption_policy(by_skill, policy)
        src_dirs = [src_dir for src_dir in src_dirs if src_dir.name in by_skill]

    flattened: dict[str, bytes] = {}
    for skill_name, payloads in sorted(by_skill.items()):
        for rel, payload in payloads.items():
            combined = f"{skill_name}/{rel}"
            if combined in flattened:
                raise IntegrityError(f"duplicate prepared source path: {combined}")
            flattened[combined] = payload.content
    return src_dirs, by_skill, flattened


def _current_generated_payloads() -> dict[str, bytes]:
    _assert_destination_tree_safe(SKILLS_ROOT, label="generated skills")
    return {_rel(path): path.read_bytes() for path in _generated_files()}


def _current_generated_prepared_payloads() -> dict[str, PreparedPayload]:
    _assert_destination_tree_safe(SKILLS_ROOT, label="generated skills")
    return {
        _rel(path): PreparedPayload(
            path.read_bytes(), 0o755 if path.stat().st_mode & 0o111 else 0o644
        )
        for path in _generated_files()
    }


def _payload_drift(expected: dict[str, bytes], actual: dict[str, bytes]) -> list[str]:
    drift: list[str] = []
    for rel in sorted(set(expected) - set(actual)):
        drift.append(f"missing generated payload: {rel}")
    for rel in sorted(set(actual) - set(expected)):
        drift.append(f"extra generated payload: {rel}")
    for rel in sorted(set(expected) & set(actual)):
        if expected[rel] != actual[rel]:
            drift.append(f"generated payload differs from adapted source: {rel}")
    return drift


def _prepared_payload_drift(
    expected: dict[str, PreparedPayload], actual: dict[str, PreparedPayload]
) -> list[str]:
    drift: list[str] = []
    for rel in sorted(set(expected) - set(actual)):
        drift.append(f"missing generated payload: {rel}")
    for rel in sorted(set(actual) - set(expected)):
        drift.append(f"extra generated payload: {rel}")
    for rel in sorted(set(expected) & set(actual)):
        if expected[rel].content != actual[rel].content:
            drift.append(f"generated payload differs from adapted source: {rel}")
        if bool(expected[rel].mode & 0o111) != bool(actual[rel].mode & 0o111):
            drift.append(f"generated payload executable mode differs from adapted source: {rel}")
    return drift


def _manifest_drift(manifest: dict[str, str], actual: dict[str, bytes]) -> list[str]:
    drift: list[str] = []
    for rel in sorted(set(manifest) - set(actual)):
        drift.append(f"manifest path missing from generated payload: {rel}")
    for rel in sorted(set(actual) - set(manifest)):
        drift.append(f"generated payload missing from manifest: {rel}")
    for rel in sorted(set(manifest) & set(actual)):
        digest = hashlib.sha256(actual[rel]).hexdigest()
        if manifest[rel] != digest:
            drift.append(f"manifest digest mismatch: {rel}")
    return drift


def _packaged_skill_inventory(skill_names: set[str]) -> dict[str, Path | None]:
    """Resolve expected packages from the checked-in, versioned skill contract."""
    contract_path = REPO_ROOT / ".agents" / "skill-contracts.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"cannot read package inventory at {contract_path}") from exc
    records = contract.get("skills")
    if not isinstance(records, list):
        raise IntegrityError("package inventory has no skills list")

    inventory: dict[str, Path | None] = {}
    for record in records:
        if not isinstance(record, dict) or record.get("name") not in skill_names:
            continue
        name = record["name"]
        if name in inventory:
            raise IntegrityError(f"package inventory has duplicate skill: {name}")
        package = record.get("package")
        if not isinstance(package, dict):
            raise IntegrityError(f"package inventory record is malformed: {name}")
        state = package.get("state")
        if state == "unpackaged":
            inventory[name] = None
            continue
        path_value = package.get("path")
        if state != "packaged" or not isinstance(path_value, str):
            raise IntegrityError(f"package inventory state is malformed: {name}")
        _safe_relative_path(path_value, label=f"package inventory path for {name}")
        destination = REPO_ROOT / path_value
        if not destination.resolve(strict=False).is_relative_to(PLUGINS_ROOT.resolve()):
            raise IntegrityError(f"package inventory path escapes plugin root: {name}")
        if destination.name != name:
            raise IntegrityError(f"package inventory path names the wrong skill: {name}")
        inventory[name] = destination

    missing = sorted(skill_names - set(inventory))
    if missing:
        raise IntegrityError(f"package inventory is missing generated skills: {missing}")
    return inventory


def _payload_set_digest(payloads: dict[str, PreparedPayload]) -> str:
    """Digest paths, bytes, and normalized executable modes unambiguously."""
    entries = [
        {
            "path": path,
            "sha256": hashlib.sha256(payloads[path].content).hexdigest(),
            "executable": bool(payloads[path].mode & 0o111),
        }
        for path in sorted(payloads)
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _tracked_file_bytes(commit: str, path: Path, *, label: str) -> bytes:
    """Read one CxPP file from Git and prove the checkout supplies those bytes."""
    try:
        rel = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise IntegrityError(f"{label}: path escapes the CxPP repository") from exc
    _safe_relative_path(rel, label=label)
    committed = _git_bytes(REPO_ROOT, "show", f"{commit}:{rel}")
    try:
        checked_out = path.read_bytes()
    except OSError as exc:
        raise IntegrityError(f"{label}: cannot read checked-out file") from exc
    if checked_out != committed:
        raise IntegrityError(f"{label}: checked-out bytes differ from CxPP commit")
    return committed


def _tracked_file_mode(commit: str, rel: str, *, label: str) -> int:
    """Return one committed file's normalized executable mode."""
    raw = _git_bytes(REPO_ROOT, "ls-tree", "-z", commit, "--", rel)
    entries = [entry for entry in raw.split(b"\0") if entry]
    if len(entries) != 1:
        raise IntegrityError(f"{label}: expected exactly one tracked file")
    metadata, separator, raw_path = entries[0].partition(b"\t")
    try:
        mode, object_type, _ = metadata.decode("ascii").split()
        tracked_path = raw_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise IntegrityError(f"{label}: malformed Git tree entry") from exc
    if not separator or object_type != "blob" or tracked_path != rel:
        raise IntegrityError(f"{label}: unexpected Git tree entry")
    if mode not in {"100644", "100755"}:
        raise IntegrityError(f"{label}: unsupported Git file mode {mode}")
    return 0o755 if mode == "100755" else 0o644


def _object(value: object, *, label: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise IntegrityError(f"{label}: expected an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise IntegrityError(f"{label}: field mismatch: missing={missing}, extra={extra}")
    return value


def _sha1(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
        raise IntegrityError(f"{label}: expected a 40-character lowercase Git identity")
    return value


def _sha256_value(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise IntegrityError(f"{label}: expected a 64-character lowercase SHA-256")
    return value


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous JSON objects before any policy dictionary exists."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IntegrityError(f"adoption policy has duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_adoption_policy(*, required: bool = True) -> AdoptionPolicy | None:
    """Load the reviewed one-time #196 decision from committed Git objects.

    Refresh and exact-pin publication never trust working-tree policy or retained
    payload bytes.  The checkout is compared to HEAD as a separate hidden-edit
    guard, while the consumed bytes and executable modes come from Git objects.
    """
    _assert_publication_file_safe(ADOPTION_POLICY_PATH, label="adoption policy")
    if not ADOPTION_POLICY_PATH.is_file():
        if required:
            raise IntegrityError("adoption policy is missing")
        return None

    head = _git_output(REPO_ROOT, "rev-parse", "HEAD")
    policy_bytes = _tracked_file_bytes(head, ADOPTION_POLICY_PATH, label="adoption policy")
    policy_rel = ADOPTION_POLICY_PATH.relative_to(REPO_ROOT).as_posix()
    policy_mode = _tracked_file_mode(head, policy_rel, label="adoption policy")
    if policy_mode != 0o644:
        raise IntegrityError("adoption policy must have Git mode 100644")
    checked_policy_mode = 0o755 if ADOPTION_POLICY_PATH.stat().st_mode & 0o111 else 0o644
    if checked_policy_mode != policy_mode:
        raise IntegrityError("adoption policy checked-out mode differs from CxPP commit")
    try:
        raw = json.loads(
            policy_bytes.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("adoption policy is not valid UTF-8 JSON") from exc

    root = _object(
        raw,
        label="adoption policy",
        keys={
            "schema_version",
            "kind",
            "source",
            "historical_audit",
            "counts",
            "boundaries",
            "dispositions",
        },
    )
    if root["schema_version"] != 1 or root["kind"] != "cxpp-selective-cpp-adoption":
        raise IntegrityError("adoption policy schema/kind is unsupported")

    source = _object(
        root["source"],
        label="adoption policy source",
        keys={"repo", "commit", "tree", "codex_skills_tree"},
    )
    if source["repo"] != CPP_REPO_URL:
        raise IntegrityError("adoption policy source repository is not the fixed CPP repository")
    source_commit = _sha1(source["commit"], label="adoption policy source commit")
    if source_commit != ADOPTION_TARGET_COMMIT:
        raise IntegrityError("adoption policy does not name the reviewed #196 target commit")
    source_tree = _sha1(source["tree"], label="adoption policy source tree")
    source_skills_tree = _sha1(
        source["codex_skills_tree"], label="adoption policy source skills tree"
    )

    audit = _object(
        root["historical_audit"],
        label="adoption policy historical audit",
        keys={
            "report_sha256",
            "generated_at",
            "cxpp_commit",
            "cxpp_tree",
            "baseline_pin_commit",
            "baseline_manifest_sha256",
            "baseline_overlay_sha256",
            "baseline_adapted_payload_sha256",
            "target_adapted_payload_sha256",
            "changes",
        },
    )
    _sha256_value(audit["report_sha256"], label="historical report digest")
    if not isinstance(audit["generated_at"], str) or not REPORT_TIMESTAMP_RE.fullmatch(
        audit["generated_at"]
    ):
        raise IntegrityError("historical report timestamp is malformed")
    _sha1(audit["cxpp_commit"], label="historical CxPP commit")
    _sha1(audit["cxpp_tree"], label="historical CxPP tree")
    _sha1(audit["baseline_pin_commit"], label="historical baseline PIN")
    for field in (
        "baseline_manifest_sha256",
        "baseline_overlay_sha256",
        "baseline_adapted_payload_sha256",
        "target_adapted_payload_sha256",
    ):
        _sha256_value(audit[field], label=f"historical {field}")
    audit_identities = {key: audit[key] for key in ADOPTION_AUDIT_IDENTITIES}
    if audit_identities != ADOPTION_AUDIT_IDENTITIES:
        raise IntegrityError("historical audit identity does not match accepted #207 evidence")

    changes = _object(
        audit["changes"],
        label="historical audit changes",
        keys={"added", "changed", "removed"},
    )
    change_kind: dict[str, str] = {}
    for kind in ("added", "changed", "removed"):
        values = changes[kind]
        if not isinstance(values, list) or not all(isinstance(path, str) for path in values):
            raise IntegrityError(f"historical audit {kind}: expected a path list")
        if values != sorted(values) or len(values) != len(set(values)):
            raise IntegrityError(f"historical audit {kind}: paths must be sorted and unique")
        for path in values:
            _safe_relative_path(path, label=f"historical audit {kind} path")
            if path in change_kind:
                raise IntegrityError(f"historical audit duplicates path across change kinds: {path}")
            change_kind[path] = kind
    changes_digest = hashlib.sha256(
        json.dumps(changes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if changes_digest != ADOPTION_CHANGE_SET_SHA256:
        raise IntegrityError("historical audit path set does not match accepted #207 evidence")

    boundaries = _object(
        root["boundaries"],
        label="adoption policy boundaries",
        keys={
            "excluded_source_skills",
            "native_collisions",
            "missing_plugin_destinations",
            "reviewed_exclusions",
        },
    )
    for field in ("excluded_source_skills", "native_collisions", "reviewed_exclusions"):
        values = boundaries[field]
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise IntegrityError(f"adoption policy boundary {field}: expected a string list")
        if values != sorted(values) or len(values) != len(set(values)):
            raise IntegrityError(f"adoption policy boundary {field}: values must be sorted and unique")
    missing_destinations = boundaries["missing_plugin_destinations"]
    if not isinstance(missing_destinations, list):
        raise IntegrityError(
            "adoption policy boundary missing_plugin_destinations: expected a list"
        )
    missing_skills: list[str] = []
    for index, value in enumerate(missing_destinations):
        record = _object(
            value,
            label=f"adoption policy missing destination {index}",
            keys={"skill", "reason"},
        )
        if not isinstance(record["skill"], str) or not isinstance(record["reason"], str):
            raise IntegrityError("adoption policy missing destination fields must be strings")
        missing_skills.append(record["skill"])
    if missing_skills != sorted(missing_skills) or len(missing_skills) != len(
        set(missing_skills)
    ):
        raise IntegrityError("adoption policy missing destinations must be sorted and unique")
    if boundaries != ADOPTION_BOUNDARIES:
        raise IntegrityError("adoption policy boundary does not match reviewed CxPP inventory")

    counts = _object(
        root["counts"],
        label="adoption policy counts",
        keys={"adopt", "adapt", "defer"},
    )
    dispositions_raw = root["dispositions"]
    if not isinstance(dispositions_raw, list):
        raise IntegrityError("adoption policy dispositions must be a list")

    dispositions: dict[str, AdoptionDisposition] = {}
    decision_map: dict[str, str] = {}
    retained_payloads: dict[str, dict[str, str]] = {}
    actual_counts = {action: 0 for action in ADOPTION_COUNTS}
    for index, value in enumerate(dispositions_raw):
        entry = _object(
            value,
            label=f"adoption disposition {index}",
            keys={"path", "source_change", "action", "owner", "reason", "overlay"},
        )
        path = entry["path"]
        source_change = entry["source_change"]
        action = entry["action"]
        owner = entry["owner"]
        reason = entry["reason"]
        if not isinstance(path, str):
            raise IntegrityError(f"adoption disposition {index}: path must be a string")
        _safe_relative_path(path, label=f"adoption disposition {index} path")
        if path in dispositions:
            raise IntegrityError(f"adoption policy has duplicate disposition: {path}")
        if source_change != change_kind.get(path):
            raise IntegrityError(f"adoption disposition source change mismatch: {path}")
        if not isinstance(action, str) or action not in ADOPTION_COUNTS:
            raise IntegrityError(f"adoption disposition has invalid action: {path}")
        if not isinstance(owner, str) or not owner.strip():
            raise IntegrityError(f"adoption disposition has no owner: {path}")
        if not isinstance(reason, str) or not reason.strip():
            raise IntegrityError(f"adoption disposition has no reason: {path}")

        retained: PreparedPayload | None = None
        overlay = entry["overlay"]
        if overlay is not None:
            overlay_record = _object(
                overlay,
                label=f"adoption disposition overlay {path}",
                keys={"path", "sha256", "mode"},
            )
            if action != "defer":
                raise IntegrityError(f"only a deferred path may carry a retention overlay: {path}")
            overlay_path = overlay_record["path"]
            if not isinstance(overlay_path, str):
                raise IntegrityError(f"retention overlay path must be a string: {path}")
            _safe_relative_path(overlay_path, label=f"retention overlay for {path}")
            expected_overlay = (RETAIN_OVERLAY_ROOT / path).relative_to(REPO_ROOT).as_posix()
            if overlay_path != expected_overlay:
                raise IntegrityError(f"retention overlay does not map one-to-one to source path: {path}")
            overlay_file = REPO_ROOT / overlay_path
            _assert_publication_file_safe(overlay_file, label=f"retention overlay for {path}")
            content = _tracked_file_bytes(head, overlay_file, label=f"retention overlay for {path}")
            digest = _sha256_value(
                overlay_record["sha256"], label=f"retention overlay digest for {path}"
            )
            if hashlib.sha256(content).hexdigest() != digest:
                raise IntegrityError(f"retention overlay digest mismatch: {path}")
            mode_value = overlay_record["mode"]
            if mode_value not in {"100644", "100755"}:
                raise IntegrityError(f"retention overlay has unsupported mode: {path}")
            mode = _tracked_file_mode(head, overlay_path, label=f"retention overlay for {path}")
            if mode != (0o755 if mode_value == "100755" else 0o644):
                raise IntegrityError(f"retention overlay mode mismatch: {path}")
            checked_mode = 0o755 if overlay_file.stat().st_mode & 0o111 else 0o644
            if checked_mode != mode:
                raise IntegrityError(f"retention overlay checked-out mode differs from CxPP commit: {path}")
            retained = PreparedPayload(content, mode)
            retained_payloads[path] = {"sha256": digest, "mode": mode_value}

        if action == "defer" and source_change in {"changed", "removed"} and retained is None:
            raise IntegrityError(f"deferred historical payload has no retention overlay: {path}")
        dispositions[path] = AdoptionDisposition(
            path, source_change, action, owner.strip(), reason.strip(), retained
        )
        decision_map[path] = action
        actual_counts[action] += 1

    if set(dispositions) != set(change_kind):
        missing = sorted(set(change_kind) - set(dispositions))
        extra = sorted(set(dispositions) - set(change_kind))
        raise IntegrityError(f"adoption disposition coverage mismatch: missing={missing}, extra={extra}")
    if counts != actual_counts or actual_counts != ADOPTION_COUNTS:
        raise IntegrityError(
            "adoption disposition count mismatch: "
            f"declared={counts}, actual={actual_counts}, reviewed={ADOPTION_COUNTS}"
        )
    decision_digest = hashlib.sha256(
        json.dumps(decision_map, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if decision_digest != ADOPTION_DECISIONS_SHA256:
        raise IntegrityError(
            "adoption path/action decisions do not match the reviewed #196 disposition map"
        )
    retained_digest = hashlib.sha256(
        json.dumps(retained_payloads, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if retained_digest != ADOPTION_RETAINED_PAYLOADS_SHA256:
        raise IntegrityError(
            "retained payload bytes/modes do not match reviewed historical evidence"
        )

    return AdoptionPolicy(
        source_commit,
        source_tree,
        source_skills_tree,
        dispositions,
        hashlib.sha256(policy_bytes).hexdigest(),
        audit,
        boundaries,
    )


def _validate_policy_source(
    policy: AdoptionPolicy, cpp_root: Path, commit: str, source_tree: str
) -> None:
    if commit != policy.source_commit or source_tree != policy.source_tree:
        raise IntegrityError("adoption policy target does not match the requested source commit/tree")
    skills_tree = _git_output(
        cpp_root, "rev-parse", f"{commit}:{PIN_PULL_SOURCE.rstrip('/')}"
    )
    if skills_tree != policy.source_skills_tree:
        raise IntegrityError("adoption policy target codex/skills tree does not match source")


def _apply_adoption_policy(
    by_skill: dict[str, dict[str, PreparedPayload]], policy: AdoptionPolicy
) -> dict[str, dict[str, PreparedPayload]]:
    projected = {name: dict(payloads) for name, payloads in by_skill.items()}
    for path, disposition in sorted(policy.dispositions.items()):
        skill_name, separator, rel = path.partition("/")
        if not separator:
            raise IntegrityError(f"adoption disposition has no skill directory: {path}")
        payloads = projected.setdefault(skill_name, {})
        if disposition.action == "defer":
            if disposition.retained is None:
                payloads.pop(rel, None)
            else:
                payloads[rel] = disposition.retained
        elif disposition.source_change == "removed":
            if rel in payloads:
                raise IntegrityError(f"approved source removal still exists at selected target: {path}")
        elif rel not in payloads:
            raise IntegrityError(f"approved source payload is absent at selected target: {path}")

    empty = [name for name, payloads in projected.items() if not payloads]
    for name in empty:
        del projected[name]
    return projected


def _validate_reporting_baseline() -> tuple[
    Pin,
    str,
    str,
    dict[str, PreparedPayload],
    str,
    str,
    AdoptionPolicy | None,
]:
    """Prove every CxPP input named in an upstream report belongs to HEAD."""
    resolved_root = REPO_ROOT.resolve()
    top_level = Path(_git_output(REPO_ROOT, "rev-parse", "--show-toplevel")).resolve()
    if top_level != resolved_root:
        raise IntegrityError("CxPP path must name the Git worktree root")
    head = _git_output(REPO_ROOT, "rev-parse", "HEAD")
    tree = _git_output(REPO_ROOT, "rev-parse", "HEAD^{tree}")
    if not COMMIT_RE.fullmatch(head) or not COMMIT_RE.fullmatch(tree):
        raise IntegrityError("CxPP HEAD or tree is not an immutable SHA-1 identity")

    _assert_destination_tree_safe(SKILLS_ROOT, label="generated skills")
    _assert_publication_file_safe(PIN_PATH, label="report PIN input")
    _assert_publication_file_safe(MANIFEST_PATH, label="report manifest input")
    contract_path = REPO_ROOT / ".agents" / "skill-contracts.json"
    _assert_publication_file_safe(contract_path, label="report package inventory input")
    _assert_publication_file_safe(OVERLAY_PATH, label="report overlay input")

    overlay = _tracked_file_bytes(head, OVERLAY_PATH, label="report overlay input")
    _tracked_file_bytes(head, PIN_PATH, label="report PIN input")
    manifest_bytes = _tracked_file_bytes(
        head, MANIFEST_PATH, label="report manifest input"
    )
    _tracked_file_bytes(head, contract_path, label="report package inventory input")

    pin = read_pin()
    policy = _load_adoption_policy(required=pin.commit == ADOPTION_TARGET_COMMIT)
    manifest = read_manifest()
    if not manifest:
        raise IntegrityError("report baseline manifest is empty")
    actual = _current_generated_payloads()
    drift = _manifest_drift(manifest, actual)
    drift.extend(
        f"generated marker violation: {item}" for item in _marker_violations()
    )
    prepared_actual: dict[str, PreparedPayload] = {}
    for rel in sorted(actual):
        tracked_rel = f"{PIN_PULL_DESTINATION}{rel}"
        committed = _git_bytes(REPO_ROOT, "show", f"{head}:{tracked_rel}")
        if actual[rel] != committed:
            raise IntegrityError(
                f"report baseline payload differs from CxPP commit: {rel}"
            )
        path = SKILLS_ROOT / rel
        checked_mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
        committed_mode = _tracked_file_mode(
            head, tracked_rel, label=f"report baseline payload {rel}"
        )
        if checked_mode != committed_mode:
            raise IntegrityError(
                f"report baseline payload mode differs from CxPP commit: {rel}"
            )
        prepared_actual[rel] = PreparedPayload(actual[rel], checked_mode)

    plugin_drift, _ = _plugin_payload_drift(prepared_actual)
    drift.extend(plugin_drift)
    if drift:
        raise IntegrityError(f"report baseline has {len(drift)} integrity mismatch(es)")

    current_skills = {rel.partition("/")[0] for rel in actual}
    _packaged_skill_inventory(current_skills)
    return (
        pin,
        head,
        tree,
        prepared_actual,
        hashlib.sha256(overlay).hexdigest(),
        hashlib.sha256(manifest_bytes).hexdigest(),
        policy,
    )


def _source_skill_names_from_commit(cpp_root: Path, commit: str) -> set[str]:
    """List source skill names from the immutable tree, including omissions."""
    raw_tree = _git_bytes(
        cpp_root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        commit,
        "--",
        PIN_PULL_SOURCE.rstrip("/"),
    )
    names: set[str] = set()
    for raw_entry in raw_tree.split(b"\0"):
        if not raw_entry:
            continue
        _, separator, raw_path = raw_entry.partition(b"\t")
        if not separator:
            raise IntegrityError("CPP source inventory contains a malformed entry")
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise IntegrityError("CPP source inventory contains a non-UTF-8 path") from exc
        if not path.startswith(PIN_PULL_SOURCE):
            raise IntegrityError("CPP source inventory escapes codex/skills")
        rel = _safe_relative_path(
            path[len(PIN_PULL_SOURCE) :], label="CPP source inventory path"
        )
        skill_name, separator, skill_rel = rel.partition("/")
        if separator and skill_rel == "SKILL.md":
            names.add(skill_name)
    return names


def _missing_new_plugin_destinations(skill_names: set[str]) -> list[dict[str, str]]:
    """Describe new source skills that adoption cannot yet place in a plugin."""
    contract_path = REPO_ROOT / ".agents" / "skill-contracts.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"cannot read package inventory at {contract_path}") from exc
    records = contract.get("skills")
    if not isinstance(records, list):
        raise IntegrityError("package inventory has no skills list")

    selected: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise IntegrityError("package inventory contains a malformed record")
        name = record.get("name")
        if not isinstance(name, str):
            raise IntegrityError("package inventory contains a malformed skill name")
        if name not in skill_names:
            continue
        if name in selected:
            raise IntegrityError(f"package inventory has duplicate skill: {name}")
        selected[name] = record

    missing: list[dict[str, str]] = []
    for name in sorted(skill_names):
        record = selected.get(name)
        if record is None:
            missing.append({"skill": name, "reason": "no-contract-record"})
            continue
        package = record.get("package")
        if not isinstance(package, dict):
            raise IntegrityError(f"package inventory record is malformed: {name}")
        state = package.get("state")
        if state == "unpackaged":
            missing.append({"skill": name, "reason": "declared-unpackaged"})
            continue
        path_value = package.get("path")
        if state != "packaged" or not isinstance(path_value, str):
            raise IntegrityError(f"package inventory state is malformed: {name}")
        _safe_relative_path(path_value, label=f"package inventory path for {name}")
        destination = REPO_ROOT / path_value
        if not destination.resolve(strict=False).is_relative_to(PLUGINS_ROOT.resolve()):
            raise IntegrityError(f"package inventory path escapes plugin root: {name}")
        if destination.name != name:
            raise IntegrityError(f"package inventory path names the wrong skill: {name}")
        if not destination.is_dir():
            missing.append(
                {
                    "skill": name,
                    "reason": "package-destination-missing",
                    "path": path_value,
                }
            )
    return missing


def _plugin_payload_drift(
    actual: dict[str, PreparedPayload],
) -> tuple[list[str], int]:
    """Compare every inventory-declared package, exempting only UI metadata."""
    _assert_destination_tree_safe(PLUGINS_ROOT, label="plugin payloads")
    by_skill: dict[str, dict[str, PreparedPayload]] = {}
    for rel, payload in actual.items():
        skill_name, separator, skill_rel = rel.partition("/")
        if not separator:
            raise IntegrityError(f"generated payload has no skill directory: {rel}")
        by_skill.setdefault(skill_name, {})[skill_rel] = payload

    drift: list[str] = []
    packaged_skills = 0
    inventory = _packaged_skill_inventory(set(by_skill))
    for skill_name, destination in sorted(inventory.items()):
        if destination is None:
            continue
        expected = by_skill[skill_name]
        if not destination.is_dir():
            drift.append(f"plugin package missing: {destination.relative_to(REPO_ROOT)}")
            continue
        packaged_skills += 1
        _assert_no_symlinks(destination, label=f"plugin skill {skill_name}")
        packaged = {
            path.relative_to(destination).as_posix(): PreparedPayload(
                path.read_bytes(), 0o755 if path.stat().st_mode & 0o111 else 0o644
            )
            for path in destination.rglob("*")
            if path.is_file()
            and path.relative_to(destination).as_posix() != "agents/openai.yaml"
            and not _is_python_cache(path)
        }
        expected = {rel: payload for rel, payload in expected.items() if rel != "agents/openai.yaml"}
        for rel in sorted(set(expected) - set(packaged)):
            drift.append(f"plugin payload missing: {skill_name}/{rel}")
        for rel in sorted(set(packaged) - set(expected)):
            drift.append(f"plugin payload extra: {skill_name}/{rel}")
        for rel in sorted(set(expected) & set(packaged)):
            if expected[rel].content != packaged[rel].content:
                drift.append(f"plugin payload differs: {skill_name}/{rel}")
            if bool(expected[rel].mode & 0o111) != bool(packaged[rel].mode & 0o111):
                drift.append(f"plugin payload executable mode differs: {skill_name}/{rel}")
    return drift, packaged_skills


def _validate_refresh_destinations(
    skill_names: set[str],
) -> dict[str, PreparedPlugin | None]:
    if not PLUGINS_ROOT.is_dir():
        raise IntegrityError(f"plugin root is missing at {PLUGINS_ROOT}")
    _assert_destination_tree_safe(SKILLS_ROOT, label="generated skills")
    _assert_destination_tree_safe(PLUGINS_ROOT, label="plugin payloads")
    _assert_destination_tree_safe(VENDOR_DIR, label="provenance directory")
    _assert_publication_file_safe(PIN_PATH, label="PIN publication")
    _assert_publication_file_safe(MANIFEST_PATH, label="manifest publication")

    prepared: dict[str, PreparedPlugin | None] = {}
    for skill_name, destination in _packaged_skill_inventory(skill_names).items():
        if destination is None:
            prepared[skill_name] = None
            continue
        if not destination.is_dir():
            raise IntegrityError(
                f"expected plugin package is missing for {skill_name}: {destination}"
            )
        metadata_path = destination / "agents" / "openai.yaml"
        _assert_publication_file_safe(
            metadata_path, label=f"plugin metadata for {skill_name}"
        )
        metadata: PreparedPayload | None = None
        if metadata_path.is_file():
            try:
                metadata = PreparedPayload(
                    metadata_path.read_bytes(), metadata_path.stat().st_mode & 0o777
                )
            except OSError as exc:
                raise IntegrityError(
                    f"cannot freeze plugin metadata for {skill_name}"
                ) from exc
        prepared[skill_name] = PreparedPlugin(destination, metadata)
    return prepared


def run_pin_check(cpp_root: Path) -> int:
    """Verify immutable source, overlay, generated, manifest, and plugin parity."""
    try:
        pin = read_pin()
        manifest = read_manifest()
        if not manifest:
            raise IntegrityError("manifest is empty")
        head, tree = _validate_source_checkout(
            cpp_root, commit=pin.commit, repo=pin.repo
        )
        policy = _load_adoption_policy(required=pin.commit == ADOPTION_TARGET_COMMIT)
        if policy is not None:
            _validate_policy_source(policy, cpp_root, pin.commit, tree)
        _, expected_by_skill, _ = _prepare_source_payloads(
            cpp_root, commit=pin.commit, policy=policy
        )
        expected = {
            f"{skill_name}/{rel}": payload
            for skill_name, payloads in expected_by_skill.items()
            for rel, payload in payloads.items()
        }
        actual = _current_generated_prepared_payloads()
        drift = _prepared_payload_drift(expected, actual)
        drift.extend(
            _manifest_drift(
                manifest, {rel: payload.content for rel, payload in actual.items()}
            )
        )
        plugin_drift, packaged_skills = _plugin_payload_drift(actual)
        drift.extend(plugin_drift)
        marker_drift = _marker_violations()
        drift.extend(f"generated marker violation: {item}" for item in marker_drift)
        if drift:
            for item in drift:
                print(f"PIN-INTEGRITY: {item}")
            raise IntegrityError(f"{len(drift)} integrity mismatch(es)")
    except IntegrityError as exc:
        print(f"codex-skills-sync: exact-pin check failed: {exc}", file=sys.stderr)
        print("CODEX_PIN_CHECK: fail")
        return 1

    overlay_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest_digest = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    print(f"PIN_REPO={pin.repo}")
    print(f"PIN_COMMIT={pin.commit}")
    print(f"SOURCE_HEAD={head}")
    print(f"SOURCE_TREE={tree}")
    print(f"OVERLAY_SHA256={overlay_digest}")
    print(f"MANIFEST_SHA256={manifest_digest}")
    print(f"PAYLOAD_FILES={len(actual)}")
    print(f"PACKAGED_SKILLS={packaged_skills}")
    if policy is not None:
        print(f"ADOPTION_POLICY_SHA256={policy.policy_sha256}")
        print(f"DECLARED_DEFERRALS={ADOPTION_COUNTS['defer']}")
    print("CODEX_PIN_CHECK: ok")
    return 0


def run_source_check(cpp_root: Path) -> int:
    """Fail when the adopted generated payload differs from a CPP checkout."""
    try:
        source_head = _git_output(cpp_root, "rev-parse", "HEAD")
        pin = read_pin()
        policy = None
        if source_head == pin.commit == ADOPTION_TARGET_COMMIT:
            policy = _load_adoption_policy()
        _, _, expected = _prepare_source_payloads(cpp_root, policy=policy)
        actual = _current_generated_payloads()
    except IntegrityError as exc:
        print(f"codex-skills-sync: source check failed: {exc}", file=sys.stderr)
        return 2

    stale = sorted(rel for rel in set(expected) | set(actual) if expected.get(rel) != actual.get(rel))
    if stale:
        for rel in stale:
            print(f"UPSTREAM-DRIFT: .codex/skills/{rel}")
        print(
            "codex-skills-sync: vendored skills differ from the supplied CPP source;"
            " run --refresh with that checkout",
            file=sys.stderr,
        )
        return 1
    print(f"codex-skills-sync: {len(actual)} vendored file(s) current with {cpp_root}")
    return 0


def _upstream_report(
    cpp_root: Path,
    ref: str,
    *,
    generated_at: str,
) -> dict[str, object]:
    """Build a complete immutable comparison without publishing any bytes."""
    if not REPORT_TIMESTAMP_RE.fullmatch(generated_at):
        raise IntegrityError("report timestamp must be UTC with second precision")
    try:
        datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise IntegrityError("report timestamp is not a valid UTC time") from exc
    (
        pin,
        cxpp_head,
        cxpp_tree,
        actual_prepared,
        overlay_digest,
        manifest_digest,
        policy,
    ) = _validate_reporting_baseline()
    actual = {rel: payload.content for rel, payload in actual_prepared.items()}
    target_head, target_tree = _validate_source_checkout(
        cpp_root, commit=ref, repo=CPP_REPO_URL
    )
    target_skills_tree = _git_output(
        cpp_root, "rev-parse", f"{ref}:{PIN_PULL_SOURCE.rstrip('/')}"
    )
    if not COMMIT_RE.fullmatch(target_skills_tree):
        raise IntegrityError("target codex/skills tree has no immutable SHA-1 identity")
    _, by_skill, _ = _prepare_source_payloads(cpp_root, commit=ref)
    expected_prepared = {
        f"{skill_name}/{rel}": payload
        for skill_name, payloads in by_skill.items()
        for rel, payload in payloads.items()
    }
    expected = {
        rel: payload.content for rel, payload in expected_prepared.items()
    }

    added = sorted(set(expected) - set(actual))
    removed = sorted(set(actual) - set(expected))
    changed = sorted(
        rel
        for rel in set(expected_prepared) & set(actual_prepared)
        if expected_prepared[rel] != actual_prepared[rel]
    )
    current_skills = {rel.partition("/")[0] for rel in actual}
    target_skills = set(by_skill)
    all_source_skills = _source_skill_names_from_commit(cpp_root, ref)
    exclusions = [
        {
            "family": family,
            "skills": sorted(
                name for name in all_source_skills if name.startswith(f"{family}-")
            ),
        }
        for family in sorted(PULL_EXCLUDE_FAMILIES)
    ]
    native_collisions = sorted(all_source_skills & LOCAL_SKILL_DIRS)
    missing_destinations = _missing_new_plugin_destinations(
        target_skills - current_skills
    )
    drift_count = len(added) + len(removed) + len(changed)
    excluded_skill_count = sum(
        1
        for family in PULL_EXCLUDE_FAMILIES
        for name in all_source_skills
        if name.startswith(f"{family}-")
    )
    declared_deferrals = []
    if policy is not None:
        declared_deferrals = [
            {
                "path": disposition.path,
                "source_change": disposition.source_change,
                "retention": "overlay" if disposition.retained is not None else "omitted",
                "owner": disposition.owner,
                "reason": disposition.reason,
            }
            for disposition in policy.dispositions.values()
            if disposition.action == "defer"
        ]

    return {
        "schema_version": 2,
        "complete": True,
        "generated_at": generated_at,
        "status": "drift" if drift_count else "current",
        "cxpp": {"commit": cxpp_head, "tree": cxpp_tree},
        "baseline": {
            "pin_commit": pin.commit,
            "manifest_sha256": manifest_digest,
            "adapted_payload_sha256": _payload_set_digest(actual_prepared),
            "files": len(actual),
        },
        "target": {
            "repo": CPP_REPO_URL,
            "commit": target_head,
            "tree": target_tree,
            "codex_skills_tree": target_skills_tree,
            "adapted_payload_sha256": _payload_set_digest(expected_prepared),
            "files": len(expected),
        },
        "overlay": {
            "path": OVERLAY_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": overlay_digest,
        },
        "adoption": {
            "policy_path": (
                ADOPTION_POLICY_PATH.relative_to(REPO_ROOT).as_posix()
                if policy is not None
                else None
            ),
            "policy_sha256": policy.policy_sha256 if policy is not None else None,
            "target_commit": policy.source_commit if policy is not None else None,
            "historical_report_sha256": (
                policy.historical_audit["report_sha256"] if policy is not None else None
            ),
            "counts": ADOPTION_COUNTS if policy is not None else {key: 0 for key in ADOPTION_COUNTS},
            "declared_deferrals": declared_deferrals,
        },
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "drift": drift_count,
            "excluded_source_skills": excluded_skill_count,
            "native_collisions": len(native_collisions),
            "missing_plugin_destinations": len(missing_destinations),
            "declared_deferrals": len(declared_deferrals),
        },
        "changes": {"added": added, "removed": removed, "changed": changed},
        "omissions": {
            "excluded_families": exclusions,
            "native_collisions": native_collisions,
            "new_skills_missing_plugin_destinations": missing_destinations,
        },
    }


def run_source_report(
    cpp_root: Path,
    ref: str,
    *,
    generated_at: str | None = None,
) -> int:
    """Emit a canonical latest-upstream report; drift is data, not failure."""
    timestamp = generated_at or (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    try:
        report = _upstream_report(cpp_root, ref, generated_at=timestamp)
        canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
    except (IntegrityError, OSError, UnicodeError) as exc:
        print(f"codex-skills-sync: upstream report failed: {exc}", file=sys.stderr)
        print("CODEX_UPSTREAM_REPORT: fail")
        return 2

    counts = report["counts"]
    cxpp = report["cxpp"]
    baseline = report["baseline"]
    target = report["target"]
    assert isinstance(counts, dict)
    assert isinstance(cxpp, dict)
    assert isinstance(baseline, dict)
    assert isinstance(target, dict)
    print(f"CXPP_COMMIT={cxpp['commit']}")
    print(f"PIN_COMMIT={baseline['pin_commit']}")
    print(f"TARGET_CPP_SHA={target['commit']}")
    print(f"UPSTREAM_STATUS={report['status']}")
    print(
        "UPSTREAM_COUNTS="
        f"added:{counts['added']},removed:{counts['removed']},"
        f"changed:{counts['changed']},drift:{counts['drift']}"
    )
    print(f"DECLARED_DEFERRALS={counts['declared_deferrals']}")
    print(f"REPORT_SHA256={digest}")
    print(f"REPORT_JSON={canonical}")
    print("CODEX_UPSTREAM_REPORT: ok")
    return 0


def run_refresh(cpp_root: Path, ref: str) -> int:
    # All fallible integrity validation precedes the first destination write.
    # Publication spans several directories and is deliberately not described as
    # crash-atomic; this guarantee is specifically about validation failures.
    try:
        policy = _load_adoption_policy(required=ref == ADOPTION_TARGET_COMMIT)
        _, source_tree = _validate_source_checkout(
            cpp_root, commit=ref, repo=CPP_REPO_URL
        )
        if policy is not None:
            _validate_policy_source(policy, cpp_root, ref, source_tree)
        src_dirs, prepared_by_skill, _ = _prepare_source_payloads(
            cpp_root, commit=ref, policy=policy
        )
        prepared_manifest = {
            f"{skill_name}/{rel}": hashlib.sha256(payload.content).hexdigest()
            for skill_name, payloads in prepared_by_skill.items()
            for rel, payload in payloads.items()
        }
        prepared_plugins = _validate_refresh_destinations(set(prepared_by_skill))
    except IntegrityError as exc:
        print(f"codex-skills-sync: refresh validation failed: {exc}", file=sys.stderr)
        return 2

    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    wanted = {d.name for d in src_dirs}

    # Prune generated skill dirs that no longer exist upstream (keep CxPP-owned skill dirs).
    for existing in _skill_dirs():
        if existing.name in LOCAL_SKILL_DIRS:
            continue
        if existing.name not in wanted:
            shutil.rmtree(existing)
            print(f"codex-skills-sync: pruned {existing.name} (no longer generated upstream)")

    for src_dir in src_dirs:
        dest = SKILLS_ROOT / src_dir.name
        _write_skill_payload(dest, prepared_by_skill[src_dir.name])
        _sync_plugin_payload(
            src_dir.name, prepared_plugins[src_dir.name], prevalidated=True
        )

    _write_pin(ref)
    print(
        f"codex-skills-sync: pulled {len(src_dirs)} skill(s) from {CPP_REPO_URL}@{ref[:12]}"
    )
    MANIFEST_PATH.write_text(format_manifest(prepared_manifest), encoding="utf-8")
    print(
        f"codex-skills-sync: snapshot {len(prepared_manifest)} file(s) ->"
        f" {MANIFEST_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vendor + drift-gate the CPP-generated Codex skills (pull model)."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail on drift (default)")
    mode.add_argument("--write", action="store_true", help="re-snapshot the drift manifest")
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="mirror <cpp-root>/codex/skills/ -> .codex/skills/, update PIN + manifest",
    )
    mode.add_argument(
        "--source-check",
        action="store_true",
        help="compare vendored skills with <cpp-root> after Codex runtime adaptations",
    )
    mode.add_argument(
        "--pin-check",
        action="store_true",
        help="verify the exact pinned source, generated tree, manifest, and plugin payloads",
    )
    mode.add_argument(
        "--pin-ref",
        action="store_true",
        help="print the strictly validated immutable PIN commit for safe CI checkout",
    )
    mode.add_argument(
        "--latest-ref",
        action="store_true",
        help="resolve CPP main once and print its strictly validated immutable commit",
    )
    mode.add_argument(
        "--source-report",
        action="store_true",
        help="report latest-source drift without mutating the reviewed baseline",
    )
    parser.add_argument(
        "--cpp-root",
        type=Path,
        help=(
            "path to a claude-power-pack checkout "
            "(with --refresh/--source-check/--pin-check/--source-report)"
        ),
    )
    parser.add_argument(
        "--ref",
        default="",
        help="exact CPP commit (with --refresh/--source-report)",
    )
    args = parser.parse_args(argv)

    if args.refresh:
        if args.cpp_root is None:
            parser.error("--refresh requires --cpp-root")
        if not args.ref:
            parser.error("--refresh requires --ref with the exact source commit")
        return run_refresh(args.cpp_root.expanduser(), args.ref)
    if args.source_check:
        if args.cpp_root is None:
            parser.error("--source-check requires --cpp-root")
        return run_source_check(args.cpp_root.expanduser())
    if args.pin_check:
        if args.cpp_root is None:
            parser.error("--pin-check requires --cpp-root")
        return run_pin_check(args.cpp_root.expanduser())
    if args.source_report:
        if args.cpp_root is None:
            parser.error("--source-report requires --cpp-root")
        if not args.ref:
            parser.error("--source-report requires --ref with the exact target commit")
        return run_source_report(args.cpp_root.expanduser(), args.ref)
    if args.pin_ref:
        try:
            print(read_pin().commit)
        except IntegrityError as exc:
            print(f"codex-skills-sync: invalid PIN: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.latest_ref:
        try:
            print(_resolve_latest_cpp_commit())
        except IntegrityError as exc:
            print(f"codex-skills-sync: latest CPP resolution failed: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.write:
        return run_write()
    return run_check()


if __name__ == "__main__":
    sys.exit(main())
