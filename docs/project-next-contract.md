# Project Next Behavioral Contract

`project-next` is a read-only, deterministic recommendation workflow. Codex
Power Pack owns the executable contract, fixtures, Python core, Codex skill,
and installed project-plugin runtime. Claude Power Pack may retain a
harness-specific collector or renderer, but fidelity changes originate in this
contract and its fixture corpus; a second prompt-only decision policy is not an
authoritative implementation. CPP adoption is tracked by
[claude-power-pack#636](https://github.com/cooneycw/claude-power-pack/issues/636).

## Version and entry points

Contract version `1.2` accepts a structured `RepositoryState` and emits a
structured `RecommendationResult`. Run it from a CxPP checkout with:

```bash
python3 scripts/project-next.py [repository] [--brief|--compact|--full|--json]
```

Installed project plugins use the byte-identical entry point and generated
runtime under `plugins/project/`. `scripts/project_next_sync.py --check` blocks
drift from the authoritative `lib/project_next/` package.

## Input contract

Repository state includes open issues, open pull requests, local and remote
branches, worktrees, recent commits and dirtiness, review/check/merge state,
Spec Kit file readiness and stable ledger mappings, collection warnings, and whether the inventory is
complete. Fixture JSON can supply the same model without git, GitHub, or an LLM.

The live collector performs batched GitHub queries. Authentication, rate-limit,
pagination, fetch, parse, and command failures are recorded. An incomplete
inventory cannot produce a globally safe `next_startable_issue`.

## Classification contract

Every open issue appears in exactly one disjoint set:

- `in_flight`: mapped from an issue branch, worktree, or open pull request;
- `blocked`: has an explicit open dependency, transitive dependency, or cycle;
- `uncertain`: dependency wording or dependency state cannot be resolved;
- `available`: belongs to none of the preceding sets.

Only explicit `Depends on #N`, `Blocked by #N`, `Requires #N`, or `After #N`
relationships are executable dependencies. Ambiguous wording is uncertainty,
not availability. In-flight issues remain in the dependency graph so their
dependents stay blocked.

The engine validates that the sets are exhaustive and non-overlapping. Neither
the top action's `start_issue` variant nor `next_startable_issue` may reference
an in-flight, blocked, or uncertain issue.

## Ranking contract

Available issues use the following stable tuple, in order:

1. security/blocker, or high-priority bug;
2. declared high, medium, then undeclared priority;
3. lower Wave or Phase number;
4. task/bug, quick win, general feature, then planning/epic;
5. explicit quick-win label;
6. stale versus recently updated, using the configured threshold;
7. lower issue number as the final tie-break.

The collected timestamp makes fixture ranking repeatable. Repository policy can
override label aliases, limits, mode, and staleness in `.project-next.json`,
validated against `templates/project-next.schema.json`.

## Top action and next startable issue

`top_action` answers what should happen now. In priority order it restores an
incomplete inventory, fixes failing PR checks, addresses requested changes,
merges a ready PR, continues active work, repairs a known repository gate,
starts the highest-ranked available issue, or synchronizes a specification
task.

`next_startable_issue` is a separate field. It is the highest-ranked available
issue only when the repository inventory is complete. Active work may therefore
be the top action while a different issue is the safe next issue to start.

## Output contract

- `--json` emits the complete versioned result and is authoritative.
- `--brief` shows the top action, next safe issue, and inventory confidence.
- compact mode shows at most three safe candidates. Each candidate carries its
  priority, phase/wave, issue type, quick-win signal, stable rank tuple,
  deterministic rationale, and `$flow-auto` command. Active, blocked,
  uncertain, and critical non-startable work stays visibly separate.
- `--full` adds mutually assigned operational tiers, categorized backlog counts,
  pull requests, Spec Kit file and mapping readiness, worktrees with their
  already-collected recent commits, and cleanup candidates for worktrees or
  branches that do not map to an open issue.

`RecommendationResult` owns all presentation decisions through structured
`candidates`, `backlog_summary`, `backlog_tiers`, `spec_features`,
`worktree_details`, and `cleanup_candidates` fields. Renderers format those
fields and do not parse issue prose, classify work, or re-rank candidates.
Incomplete inventory produces no candidates or startable tiers even when the
partial inventory contains apparently available issues.

Spec Kit work is represented only by the `spec-sync:v1` Issue Sync ledger.
Task-ID searches in issue titles or bodies are not synchronization evidence.
Missing mappings produce `sync_spec`; stale or ambiguous identities produce
`resolve_spec_mapping`. Neither state is silently treated as completed work.

All modes name the `1.2` contract. Missing prerequisites and incomplete state
are explicit failure states; they never become a confident recommendation.
