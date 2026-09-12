"""Offline producer, recovery and installed-consumer acceptance evidence for #223."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_spec_sync import FORWARD_TASKS, GitHubFixture, spec_sync, write_artifacts

context = spec_sync.context
ROOT = Path(__file__).resolve().parents[1]
CONTEXT_FIXTURE = json.loads((ROOT / "tests/fixtures/spec-sync-governing-context.json").read_text())
SOURCE = CONTEXT_FIXTURE["spec"]
PLAN = CONTEXT_FIXTURE["plan"]
TASKS = FORWARD_TASKS.replace(
    "Implement `src/consumer.py`; depends on T002.", "Propose a queue in `src/consumer.py`; depends on T002."
)


def fixture(root: Path, tasks: bytes | None = None, spec: bytes | None = None, plan: bytes | None = None):
    path = write_artifacts(root, TASKS)
    path.write_bytes(TASKS.encode() if tasks is None else tasks)
    (path.parent / "spec.md").write_bytes(SOURCE.encode() if spec is None else spec)
    (path.parent / "plan.md").write_bytes(PLAN.encode() if plan is None else plan)
    github = GitHubFixture(root)
    return path, github


def commit(root: Path) -> str:
    spec_sync.subprocess_runner(["git", "add", "."], root)
    spec_sync.subprocess_runner(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=f@example.test", "commit", "-m", "reviewed revision"], root
    )
    return spec_sync.subprocess_runner(["git", "rev-parse", "HEAD"], root)


def consumer_issue(github):
    return next(issue for issue in github.issues if ":stage-1 -->" in issue["body"])


def test_selected_governing_context_and_full_raw_evidence(tmp_path):
    path, github = fixture(tmp_path)
    result = github.run(path)
    issue = consumer_issue(github)
    body = issue["body"]
    for required in (
        "frozen screen",
        "within one second",
        "single container",
        "PostgreSQL",
        "Propose a queue",
        "UNRESOLVED:",
        "FR-003",
    ):
        assert required in body
    for unrelated in ("Unrelated deletion", "Delete everything"):
        assert unrelated not in body
    data, _, _, _ = context.unpack(body)
    for name, record in data["artifacts"].items():
        raw = subprocess.check_output(
            ["git", "cat-file", "blob", f"{result['artifact_commit']}:{record['path']}"], cwd=tmp_path
        )
        assert record["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["ledger_evidence"]["deterministic_successor"]
    assert result["ledger_evidence"]["writer_after_sha256"] == context.sha(path.read_bytes())
    report = context.check(
        body, tmp_path, "example/repo", issue["number"], path.relative_to(tmp_path).as_posix(), "stage-1", ["T001"]
    )
    assert "within one second" in report["governing_text"]
    assert report["state"] == "changed"  # Precisely reports the local ledger bytes too.
    assert "retrieval only" in report["authority"]


@pytest.mark.parametrize("suffix", [b"", b"\n", b"\r\n", b" \t\n\n"])
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_raw_bytes_and_precise_ledger_successor(tmp_path, suffix, newline):
    raw = b" \t" + TASKS.encode().rstrip(b"\n").replace(b"\n", newline) + suffix
    source = (" \n" + SOURCE + " café e\u0301 \t").encode().replace(b"\n", newline)
    path, github = fixture(tmp_path, tasks=raw, spec=source, plan=PLAN.encode().replace(b"\n", newline) + suffix)
    first = github.run(path)
    successor = path.read_bytes()
    assert first["ledger_evidence"]["before_sha256"] == context.sha(raw)
    assert context.unpack(consumer_issue(github)["body"])[0]["artifacts"]["spec"]["sha256"] == context.sha(source)
    second = github.run(path)
    assert second["ledger_evidence"]["comparison"] == "verified-ledger-successor"
    assert path.read_bytes() == successor and len(github.mutations) == 2
    # A reviewed snapshot containing a ledger has an exact, idempotent successor too.
    commit(tmp_path)
    github.run(path, refresh_context=True)
    final = path.read_bytes()
    github.run(path)
    assert path.read_bytes() == final


@pytest.mark.parametrize("name", ["spec", "plan", "tasks"])
@pytest.mark.parametrize(
    "change", [lambda b: b + b"\n", lambda b: b.replace(b"\n", b"\r\n"), lambda b: b" " + b, lambda b: b.rstrip(b"\n")]
)
def test_material_byte_mismatch_refuses_before_any_write(tmp_path, name, change):
    path, github = fixture(tmp_path)
    target = path.with_name(name + ".md")
    target.write_bytes(change(target.read_bytes()))
    with pytest.raises(context.ContextError, match="differs|differ"):
        github.run(path)
    assert github.mutations == []


@pytest.mark.parametrize("damage", ["duplicate", "reverse", "task-inside", "outside", "mapping", "heading", "damaged"])
def test_ledger_cannot_hide_source_or_mapping_changes(tmp_path, damage):
    path, github = fixture(tmp_path)
    github.run(path)
    before = len(github.mutations)
    raw = path.read_bytes()
    if damage == "duplicate":
        raw += context.LEDGER_START.encode()
    elif damage == "reverse":
        raw = (
            raw.replace(context.LEDGER_START.encode(), b"TEMP")
            .replace(context.LEDGER_END.encode(), context.LEDGER_START.encode())
            .replace(b"TEMP", context.LEDGER_END.encode())
        )
    elif damage == "task-inside":
        raw = raw.replace(context.LEDGER_END.encode(), b"- [ ] T999 Hidden `src/x.py`.\n" + context.LEDGER_END.encode())
    elif damage == "outside":
        raw = raw.replace(b"Propose a queue", b"Replace acceptance")
    elif damage == "mapping":
        raw = raw.replace(b"| #100 |", b"| #999 |")
    elif damage == "heading":
        raw = raw.replace(b"## Issue Sync Ledger", b"## Unrelated human section")
    else:
        raw = raw.replace(b"ledger:start", b"ledger:damaged")
    path.write_bytes(raw)
    with pytest.raises(context.ContextError):
        github.run(path)
    assert len(github.mutations) == before and path.read_bytes() == raw


def test_cross_region_revision_refuses_then_converges_and_preserves_decisions(tmp_path):
    path, github = fixture(tmp_path)
    github.run(path)
    issue = consumer_issue(github)
    old = context.unpack(issue["body"])[0]
    human = f"\r\nHuman approval names old snapshot {old['snapshot']}.  \r\n"
    issue["body"] = human + issue["body"] + human
    # Restore reviewed tasks to exclude the local ledger, then revise real acceptance/dependencies.
    reviewed = context.read_object(tmp_path, old["artifact_commit"], path.relative_to(tmp_path).as_posix())
    path.write_bytes(
        reviewed.replace(b"; depends on T002", b"").replace(b"Consumer passes.", b"Progress responds within 500ms.")
    )
    (path.parent / "spec.md").write_text(SOURCE.replace("one second", "500 milliseconds"))
    new_commit = commit(tmp_path)
    count, local = len(github.mutations), path.read_bytes()
    with pytest.raises(context.ContextError, match="governing snapshot changed"):
        github.run(path)
    assert len(github.mutations) == count and path.read_bytes() == local
    preview = github.run(
        path, dry_run=True, refresh_context=True, revision_reference="issue comment: existing judge decision"
    )
    assert preview["preview"][0]["action"] == "would-edit"
    github.run(path, refresh_context=True, revision_reference="issue comment: existing judge decision")
    assert issue["body"].startswith(human) and issue["body"].endswith(human)
    managed = context.unpack(issue["body"])[0]
    assert managed["previous_snapshot"] == old["snapshot"] and managed["artifact_commit"] == new_commit
    assert "within 500ms" in issue["body"] and "No cross-group prerequisites." in issue["body"]
    assert "- Blocked by" not in issue["body"]
    assert old["snapshot"] in issue["body"]  # Old receipt remains old.
    assert github.run(path)["actions"][0]["action"] == "skip"


@pytest.mark.parametrize(
    "damage", ["visible", "duplicate", "nested-dependency", "crossed", "missing", "bad-meta", "legacy"]
)
def test_owned_region_refuses_damaged_or_ambiguous_body(tmp_path, damage):
    path, github = fixture(tmp_path)
    github.run(path)
    issue = consumer_issue(github)
    body = issue["body"]
    if damage == "visible":
        body = body.replace("within one second", "never show progress")
    elif damage == "duplicate":
        body += context.START
    elif damage == "nested-dependency":
        body = body.replace(context.END, spec_sync.managed_dependencies("No cross-group prerequisites.") + context.END)
    elif damage == "crossed":
        body = body.replace(context.END, "") + context.END
    elif damage == "missing":
        body = body.replace(context.START, "")
    elif damage == "bad-meta":
        body = body.replace('"schema":', '"schema":"forged","schema":')
    else:
        body = "## Tasks\nOld human decision\n" + re.search(r"<!-- spec-sync:v1:.*? -->", body).group()
    issue["body"] = body
    before = len(github.mutations)
    with pytest.raises(context.ContextError):
        github.run(path, refresh_context=True)
    assert len(github.mutations) == before and issue["body"] == body


def test_cross_repository_attestation_refused(tmp_path):
    path, github = fixture(tmp_path)
    with pytest.raises(context.ContextError, match="cross-repository attestation"):
        github.run(path, repo="other/target")
    assert github.mutations == []


@pytest.mark.parametrize("attack", ["repo", "group", "task-ids", "path", "symlink", "object", "wording"])
def test_checker_uses_expected_selection_and_trusted_source(tmp_path, attack):
    path, github = fixture(tmp_path)
    github.run(path)
    issue = consumer_issue(github)
    body, repository, group, ids = issue["body"], "example/repo", "stage-1", ["T001"]
    selected = path.relative_to(tmp_path).as_posix()
    if attack == "repo":
        repository = "attacker/repo"
    elif attack == "group":
        group = "stage-2"
    elif attack == "task-ids":
        ids = ["T002"]
    elif attack == "path":
        selected = "../escape/tasks.md"
    elif attack == "symlink":
        path.unlink()
        path.symlink_to(path.with_name("spec.md"))
    else:
        data, visible, a, b = context.unpack(body)
        if attack == "object":
            data["artifact_commit"] = "f" * 40
        else:
            data["group"]["task_text"] = "Invented authority"
        data["snapshot"] = context.sha(context.canonical({k: v for k, v in data.items() if k != "snapshot"}))
        body = body[:a] + context.pack(data, visible) + body[b:]
    with pytest.raises(context.ContextError):
        context.check(body, tmp_path, repository, issue["number"], selected, group, ids)


def test_installed_published_snippet_in_foreign_checkout(tmp_path):
    project = tmp_path / "foreign"
    path, github = fixture(project)
    github.run(path)
    issue = consumer_issue(github)
    installed = tmp_path / "installed" / "flow-auto"
    shutil.copytree(ROOT / "plugins/flow/skills/flow-auto", installed)
    reference = (installed / "reference.md").read_text()
    segment = reference[reference.index("**Generated governing context") :]
    snippet = re.search(r"```bash\n(.*?)\n\s*```", segment, re.S).group(1)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        (
            "#!/bin/sh\n"
            '[ "$1 $2 $3 $4 $5 $6 $7 $8 $9" = "issue view 101 --repo exam'
            'ple/repo --json body --jq .body" ] || exit 4\n'
            '[ "${FAIL_FETCH:-}" != yes ] || exit 5\n'
            'cat "$BODY_STUB"\n'
        )
    )
    gh.chmod(0o755)
    body = tmp_path / "issue.md"
    body.write_text(issue["body"])
    env = dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        FLOW_SKILL_DIR=str(installed),
        ISSUE_NUM=str(issue["number"]),
        REPO="example/repo",
        TARGET_REPO=str(project),
        FLOW_CONTEXT_TASKS=path.relative_to(project).as_posix(),
        FLOW_CONTEXT_GROUP="stage-1",
        FLOW_CONTEXT_TASK_IDS="T001",
        BODY_STUB=str(body),
    )
    result = subprocess.run(["bash", "-c", snippet], cwd=project, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "within one second" in result.stdout and "retrieval only" in result.stdout
    failed = subprocess.run(
        ["bash", "-c", snippet], cwd=project, env=dict(env, FAIL_FETCH="yes"), capture_output=True, text=True
    )
    assert failed.returncode != 0 and '"state"' not in failed.stdout
    (installed / "scripts/spec_context.py").unlink()
    missing = subprocess.run(["bash", "-c", snippet], cwd=project, env=env, capture_output=True, text=True)
    assert missing.returncode != 0 and "no project/global fallback" in missing.stderr


def test_focused_budget_discloses_missing_sources_and_ordinary_absence(tmp_path):
    path, github = fixture(tmp_path, spec=(SOURCE + "\n## Global constraints\n" + "Bounded " * 2000).encode())
    github.run(path)
    body = consumer_issue(github)["body"]
    assert "EXTRACT CAPPED" in body and "completeness is not established" in body
    assert context.check("A small ordinary bug.", tmp_path, "example/repo", 1, None, None)["state"] == "absent"
    with pytest.raises(context.ContextError, match="malformed"):
        context.check(context.START, tmp_path, "example/repo", 1, None, None)


@pytest.mark.parametrize("response_loss", [False, True])
def test_refresh_response_loss_retains_successes_and_reconstructs_after_restart(tmp_path, response_loss):
    path, github = fixture(tmp_path)
    github.run(path)
    old = consumer_issue(github)["body"]
    path.with_name("spec.md").write_text(SOURCE.replace("one second", "two seconds"))
    commit(tmp_path)
    github.fail = ("edit", 2, response_loss)
    with pytest.raises(spec_sync.SynchronizationError) as failed:
        github.run(path, refresh_context=True, revision_reference="old decision reference is not new authority")
    assert failed.value.result["actions"][0]["action"] == "edited"
    assert failed.value.result["failed_operation"]["outcome"] == "uncertain"
    github.fail = None
    github.run(path, refresh_context=True, revision_reference="old decision reference is not new authority")
    issue = consumer_issue(github)
    assert issue["body"] != old and "two seconds" in issue["body"]
    body_file = tmp_path / "receipt.md"
    body_file.write_text(issue["body"])
    result = subprocess.run(
        [
            "python3",
            str(ROOT / ".codex/skills/spec-sync/scripts/spec_context.py"),
            "--body-file",
            str(body_file),
            "--repo",
            "example/repo",
            "--issue",
            str(issue["number"]),
            "--checkout",
            str(tmp_path),
            "--tasks",
            path.relative_to(tmp_path).as_posix(),
            "--group",
            "stage-1",
            "--task-ids",
            "T001",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert "two seconds" in report["governing_text"] and report["previous_snapshot"]
    assert "never reinterpret approval" in report["authority"]
    assert "old decision reference" in report["observed_revision"]


@pytest.mark.parametrize("field,value", [("stories", ["us-2"]), ("checkpoint", "Provider passes.")])
def test_rehashed_metadata_cannot_substitute_another_story_or_checkpoint(tmp_path, field, value):
    path, github = fixture(tmp_path)
    github.run(path)
    issue = consumer_issue(github)
    data, visible, a, b = context.unpack(issue["body"])
    data["group"][field] = value
    data["snapshot"] = context.sha(context.canonical({k: v for k, v in data.items() if k != "snapshot"}))
    body = issue["body"][:a] + context.pack(data, visible) + issue["body"][b:]
    with pytest.raises(context.ContextError, match="story selection|checkpoint"):
        context.check(
            body, tmp_path, "example/repo", issue["number"], path.relative_to(tmp_path).as_posix(), "stage-1", ["T001"]
        )


def test_nfc_metadata_never_normalizes_raw_task_hashes(tmp_path):
    raw = TASKS.replace("Propose a queue", "Propose cafe\u0301 queue").encode()
    path, github = fixture(tmp_path, tasks=raw)
    github.run(path)
    issue = consumer_issue(github)
    report = context.check(
        issue["body"],
        tmp_path,
        "example/repo",
        issue["number"],
        path.relative_to(tmp_path).as_posix(),
        "stage-1",
        ["T001"],
    )
    assert report["retrieved"]["tasks"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert "café queue" in report["governing_text"]


def test_new_prerequisite_and_task_revision_cannot_publish_a_mixed_snapshot(tmp_path):
    path, github = fixture(tmp_path)
    github.run(path)
    # Keep the generated ledger in the reviewed revision, with its verifiable old task set.
    raw = path.read_text().replace("depends on T002", "depends on T003")
    raw = raw.replace(
        "**Checkpoint:** Consumer passes.",
        "- [ ] T004 [US1] Add `src/progress.py`.\n**Checkpoint:** Revised progress passes.",
    )
    raw = raw.replace(
        "\n\n## Issue Sync Ledger",
        "\n\n## Stage 3: New prerequisite\n- [ ] T003 [US1] Add `src/ready.py`.\n"
        "**Checkpoint:** Ready passes.\n\n## Issue Sync Ledger",
    )
    path.write_text(raw)
    commit(tmp_path)
    before, count = path.read_bytes(), len(github.mutations)
    with pytest.raises(context.ContextError, match="governing snapshot changed"):
        github.run(path)
    assert path.read_bytes() == before and len(github.mutations) == count and len(github.issues) == 2
    github.run(path, refresh_context=True)
    issue = consumer_issue(github)
    assert "T004" in issue["body"] and "Revised progress passes." in issue["body"]
    assert "- Blocked by #102" in issue["body"]
    assert len(github.issues) == 3 and "T001, T004" in path.read_text()
    github.run(path)
    assert len(github.issues) == 3


@pytest.mark.parametrize("plan", [b"Approved decision: PostgreSQL only.\r\n", b""])
def test_unstructured_plan_is_retrieved_or_explicitly_disclosed(tmp_path, plan):
    path, github = fixture(tmp_path, plan=plan)
    github.run(path)
    body = consumer_issue(github)["body"]
    assert "Approved decision: PostgreSQL only." in body if plan else "empty source; read" in body
