# Project Constitution

> Governing principles and development guidelines for this project.
> All specifications, plans, and implementations must align with these principles.

---

## Core Principles

### P1: Context Efficiency First

All tools, documentation, and workflows must optimize for context window efficiency.

- Use progressive disclosure (metadata → instructions → assets)
- Keep tool descriptions under 200 characters
- Fragment large documents into topic-focused modules
- Lazy-load content only when needed

### P2: Issue-Driven Development

Every implementation starts with a GitHub issue and follows IDD workflow.

- Issues organized as: Epic → Wave → Micro-Issue
- Use git worktrees for parallel development
- Branch naming: `issue-{N}-{description}`
- Commits reference issues: `type(scope): Description (Closes #N)`

### P3: Proportional Issue Contracts

Use the [canonical issue contract](../../docs/agents/issue-contract.md).
A small change can use a short issue body; spec.md, plan.md and tasks.md are not
mandatory for every implementation. Use fuller specifications when uncertainty,
architectural boundaries or coordination warrant them.

- Preserve outcomes, observable acceptance and binding constraints with rationale.
- Investigate assumptions; revise proposed approaches within existing authority.
- Keep older issues usable and investigate material ambiguity without migration.
- For chosen full-spec work, review the spec/plan/tasks and reference governing
  sections from issues instead of copying the specification.

### P4: Test-Driven Quality

Tests validate observable acceptance from the issue contract or governing specification.

- Write tests from the applicable acceptance examples and meaningful failure modes
- Tests must pass independently per feature
- Use pytest with descriptive test names
- No merge without passing tests

### P5: Python for Cross-Platform

Use Python for all scripting that needs to work across platforms.

- Bash scripts only for simple, Linux-only utilities
- Python 3.11+ with type hints
- Use uv for dependency management (pyproject.toml)
- Follow existing `lib/` module patterns

---

## Development Workflow

### Issue-first route
1. State the intended outcome, motivation and observable acceptance in a short issue.
2. Preserve explicit constraints; clarify material uncertainty and record proposals
   as revisable rather than inventing a design requirement.
3. Use `$flow-auto` and its judged plan before implementation. Routine choices
   within that agreement need no repeated approval; changed boundaries do.
4. Implement, validate and report delivered outcomes and any agreed revisions.

### Deliberately selected full-spec route
1. Use `$spec-adopt` when official Spec Kit authoring is wanted, preserving its
   separate installation and workspace-change consent.
2. Produce and review the governing spec, clarify, plan, tasks and analysis using
   the official workflow. Keep the specification authoritative.
3. Preview `$spec-sync` with the reviewed artifact commit; its readiness and
   approval checks remain required for this route.
4. Deliver the resulting scoped issue through `$flow-auto`; reference governing
   spec sections and acceptance evidence in the PR.

---

## Governance

### Compliance
- All PRs must verify alignment with constitution
- Complexity must be justified with rationale
- Violations require explicit documentation

### Amendments
- Constitution changes require discussion
- Document the change and rationale
- Update affected active guidance and governing specifications where needed;
  do not impose a blanket migration on historical issues.

---

## Attribution

This specification workflow is based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).

Adapted for Codex workflows with Issue-Driven Development integration.

---

*Last updated: 2026-09-12*
