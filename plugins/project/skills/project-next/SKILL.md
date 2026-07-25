---
name: project-next
description: Analyze a GitHub-backed repository's open issues, pull requests, branches, and worktrees to recommend the next unclaimed issue or cleanup action. Use when Codex is asked what to work on next, to triage project backlog, or to choose between open GitHub issues.
---

# Project Next

Produce a prioritized next-step report for the current repository.

## Procedure

1. Resolve the repository:
   - Run `git status --short --branch`.
   - Run `gh repo view --json nameWithOwner,defaultBranchRef,url`.
   - If the repository cannot be resolved, ask for the repo name.
2. Inspect active work:
   - Run `git worktree list --porcelain`.
   - Run `gh pr list --state open --json number,title,body,headRefName,closingIssuesReferences,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup,url`.
   - Run `git branch -a --format='%(refname:short) %(upstream:short)'`.
   - For each non-default worktree, record its path and branch. Map it to an issue using, in order:
     1. An issue number in an `issue-<N>-*` branch name.
     2. An open PR whose `headRefName` exactly matches the worktree branch, using the PR's `closingIssuesReferences`.
     3. An explicit issue reference in the matching PR title or body.
   - Do not guess from similar wording. Report any unmapped worktree and inspect its status and recent commits with `git -C <path> status --short` and `git -C <path> log --oneline -5`.
3. Inspect candidate issues:
   - Run `gh issue list --state open --limit 100 --json number,title,labels,assignees,updatedAt,createdAt,url,body`.
   - Prefer story/task issues over epic tracking issues unless the user asks for planning.
4. Materialize the selection sets before ranking:
   - `IN_FLIGHT_ISSUES`: every open issue mapped to a non-default worktree, matching local or remote branch, or open PR.
   - `DEPENDENCY_MAP`: explicit `depends on`, `blocked by`, `after`, or `requires` relationships between open issues.
   - `BLOCKED_ISSUES`: issues with an open dependency. Keep in-flight issues in this graph so their dependents remain blocked.
   - `AVAILABLE_ISSUES`: all open issues not in `IN_FLIGHT_ISSUES` or `BLOCKED_ISSUES`.
   - Account for every open issue exactly once. If a classification is uncertain, report it instead of silently treating the issue as available.
5. Apply the hard gate:
   - Choose a "next issue to start" only from `AVAILABLE_ISSUES`.
   - Never place an issue from `IN_FLIGHT_ISSUES` or `BLOCKED_ISSUES` in the top pick or startable alternatives.
   - Show in-flight issues separately as work to continue, review, unblock, or clean up.
   - Recommend cleanup only when stale branches or worktrees are clearly merged or abandoned.
   - If verification gates are failing or unknown, prefer fixing the gate before starting broad feature work.
   - Before reporting, validate that the top pick and every startable alternative are in `AVAILABLE_ISSUES`.
6. Report compactly:
   - State the top recommendation first.
   - List the evidence: open PRs, worktrees, relevant branches, and gate status.
   - Include the next 2-4 candidates only when helpful.

## Output Shape

```text
Top pick: #NN Title
Why: <one or two concrete reasons>

Other available issues:
- #NN Title - <reason>

Active work (not startable):
- #NN Title - <worktree or PR evidence>

Blocked (not startable):
- #NN Title - blocked by #MM

Current state:
- PRs: <open PR count and notable blockers>
- Worktrees: <active issue worktrees>
- Unmapped worktrees: <paths and branches, or none>
- Branch cleanup: <stale merged branches or none>
- Gates: <known local or CI status>
```
