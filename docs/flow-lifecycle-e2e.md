# Native Flow Lifecycle Dogfood

This document records the #84 acceptance run using GitHub issue #127.

1. Created #127 with `gh issue create` and marked it as a temporary lifecycle
   acceptance issue.
2. Started work in a visible sibling worktree `../codex-power-pack-issue-127`
   with `git worktree add ... -b issue-127-flow-dogfood` (issue #133: worktrees
   are siblings of the repo, not hidden inside it); the main checkout remained
   untouched.
3. Added this evidence artifact, ran `make verify`, committed it with
   `Closes #127`, pushed the branch, opened a PR, and waited for the same
   gitleaks-first Woodpecker checks used by normal work.
4. Merged the green PR, verified GitHub closed #127, then removed the worktree
   and remote branch.

The lifecycle uses ordinary Git worktrees and GitHub CLI/PR operations; it does
not rely on Claude-specific worktree state or an implicit remote branch delete.
