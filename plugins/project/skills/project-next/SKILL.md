---
name: project-next
description: Recommend the most important repository action now and the next new issue that is safe to start. Use for project backlog triage or deciding what to work on; do not use for a narrow Git question or when the user already selected an issue.
---

# Project Next

Run the bundled deterministic recommendation engine and report its output. The
engine, rather than model judgment, owns classification, ranking, and selection.
This workflow is read-only: never create issues, branches, worktrees, or edits.

## Arguments

- Optional repository path or project name. Resolve an existing path first,
  then `$HOME/Projects/<name>`, then the current repository.
- Default output is compact. Preserve `--brief`, `--compact`, `--full`, and
  `--json` when requested.

## Runtime

Resolve `SKILL_DIR` as the directory containing this loaded `SKILL.md`. Select
the first existing entry point:

1. `SKILL_DIR/../../../scripts/project-next.py` for a CxPP checkout skill;
2. `SKILL_DIR/../../scripts/project-next.py` for an installed project plugin.

Run:

```bash
python3 <entry-point> <resolved-repository> <mode>
```

The collector makes one batched issue query and one batched pull-request query,
then inspects git worktrees, local/remote branches, and optional `.specify/`
tasks. Do not replace, reinterpret, or silently complete the engine's selection
with an LLM-generated recommendation.

Exit `0` means the inventory is complete. Exit `2` with rendered output means
the inventory is incomplete: report the warnings and the `resolve_inventory`
top action; do not claim a globally safe next issue. A missing runtime or an
error without structured output is a hard failure with an actionable reinstall
or repository/authentication suggestion.

## Behavioral invariants

- `top_action` and `next_startable_issue` are separate decisions.
- Only `available` issues can be named as safe to start.
- In-flight, blocked, cyclic, and uncertain issues remain non-startable.
- Failing checks or requested review changes on active work outrank broad new
  work.
- Unsynchronized spec tasks are surfaced but are not treated as GitHub issues.
- Structured JSON and brief/compact/full renderers use contract version `1.3`.
- Compact output shows at most three safe candidates with structured rank evidence,
  a deterministic rationale, and a copyable `$flow-auto <issue>` command.
- Full output adds categorized and tiered backlog state, Spec Kit readiness,
  recent worktree commits, and evidence-based cleanup candidates. Renderers only
  format engine-owned fields; they never reclassify or re-rank issues.
- Dependencies are parsed from lead-in phrases with their punctuation and Markdown
  intact (`**Depends on:** #12`, `Blocked by: #12, #13`, `(depends on T004)`).
  Ordinary sequencing prose such as "run this after the release" is not a blocker,
  and code blocks declare nothing.
- Spec Kit synchronization is trusted only through `spec-sync:v1` Issue Sync
  ledger mappings. Missing, stale, or ambiguous mappings remain explicit
  uncertainty and never make represented work appear safely startable. Task IDs
  additionally resolve dependency references through issue titles, which is not
  synchronization evidence.
- A warning, not a silent fallback, reports a backlog whose labels match no
  configured ranking vocabulary; report it so the user can add `.project-next.json`.
- Untracked files alone are never "work in progress"; only tracked modifications
  produce `continue_work`.
