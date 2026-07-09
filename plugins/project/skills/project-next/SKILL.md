---
name: project-next
description: Analyze a GitHub-backed repository's open issues, pull requests, branches, and worktrees to recommend the next issue or cleanup action. Use when Codex is asked what to work on next, to triage project backlog, or to choose between open GitHub issues.
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
   - Run `gh pr list --state open --json number,title,headRefName,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup,url`.
   - Run `git branch -a --format='%(refname:short) %(upstream:short)'`.
3. Inspect candidate issues:
   - Run `gh issue list --state open --limit 100 --json number,title,labels,assignees,updatedAt,createdAt,url,body`.
   - Prefer story/task issues over epic tracking issues unless the user asks for planning.
   - Treat issues with matching branches, worktrees, or open PRs as in flight.
4. Apply the gate:
   - Recommend finishing or unblocking in-flight work before starting a new issue.
   - Recommend cleanup only when stale branches or worktrees are clearly merged or abandoned.
   - If verification gates are failing or unknown, prefer fixing the gate before starting broad feature work.
5. Report compactly:
   - State the top recommendation first.
   - List the evidence: open PRs, worktrees, relevant branches, and gate status.
   - Include the next 2-4 candidates only when helpful.

## Output Shape

```text
Top pick: #NN Title
Why: <one or two concrete reasons>

Also consider:
- #NN Title - <reason>

Current state:
- PRs: <open PR count and notable blockers>
- Worktrees: <active issue worktrees>
- Branch cleanup: <stale merged branches or none>
- Gates: <known local or CI status>
```
