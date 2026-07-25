---
name: claude-code-review
description: "Launch a bounded, read-only Claude Code session through the Claude Agent SDK to review the current issue-branch diff and advise Codex. Use when the user requests a Claude or cross-model code review, or when flow-auto remains stuck after two materially distinct attempts and needs implementation support."
---

# Claude Code Review

Request the Codex-native `claude:code_review` capability. Claude advises; Codex
retains ownership of edits, tests, and lifecycle decisions.

## Run the review

1. Confirm the current directory is the issue worktree, not the default branch.
2. Summarize the blocker without including credentials or raw environment values.
3. Resolve `SKILL_DIR` as the directory containing this `SKILL.md`.
4. Run:

   ```bash
   <SKILL_DIR>/scripts/claude-code-review \
     --cwd "$PWD" \
     --issue "<issue number and concise acceptance criteria>" \
     --blocker "<failed approaches, exact safe error summary, and question>"
   ```

   Add `--base-ref <ref>` only when the automatic base selection is wrong.
5. Relay Claude's verdict and findings with attribution. Verify each finding
   against the code before changing anything.
6. Apply accepted fixes with Codex, rerun the relevant test, and continue the
   parent workflow. Do not ask Claude to edit or commit.

## Guardrails

- Treat this as a bounded escalation, not an autonomous retry loop. Invoke it at
  most once for the same blocker fingerprint unless new evidence materially
  changes the question.
- The runner uses the system `claude` executable and its existing login. Never
  read, print, copy, or pass stored OAuth credentials.
- The SDK session receives only `Read`, `Glob`, and `Grep`; Bash, writes, web
  access, MCP servers, plugins, skills, and subagents are disabled.
- The runner computes the diff locally and sends it as untrusted review data.
- If Claude Code, `uv`, the SDK, or authentication is unavailable, report that
  the escalation is unavailable and continue with Codex's normal blocker path.
