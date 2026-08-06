# Spec-Driven Development

*From Codex Best Practices - r/ClaudeCode community wisdom*

## Why Spec-Driven Development? (107 upvotes)

**From "Why we shifted to Spec-Driven Development":**

**Problem:** As features multiply, consistency and quality suffer

**Solution:** Spec-Driven Development (SDD)

## The SDD Approach

1. **Write Detailed Specs First**
   - Before any code
   - Include edge cases
   - Define success criteria

2. **Review Specs, Not Just Code**
   - Easier to fix design issues before coding
   - Specs are cheaper to iterate than code
   - Gets team alignment early

3. **Use Specs as Reference**
   - Claude can check code against spec
   - Automated verification possible
   - Clear acceptance criteria

4. **Iterate on Specs**
   - Specs are living documents
   - Update based on learnings
   - Version control specs like code

## Spec-First → Sandbox → Production

**From 685 upvote post + community:**

1. **Write Spec**
   - Detailed requirements
   - Edge cases
   - Success criteria

2. **Sandbox Testing** (use Sonnet)
   - Separate directory for experiments
   - Verify key parts work
   - Try uncertain approaches

3. **Implementation** (Opus for complex, Sonnet for standard)
   - Cut-and-dry based on verified plan
   - Minimal decisions needed
   - Fast execution

4. **Review & Refine**
   - Test against spec
   - Iterate if needed
   - Git commit

## Tools

- **GitHub Spec Kit** - MIT licensed spec framework
  - https://github.com/github/spec-kit
  - https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- Custom spec frameworks
- Markdown-based specs in repo

## Community Debate

**When SDD works best:**
- Complex, multi-person projects
- Features with many edge cases
- When team alignment is critical

**When SDD may be overkill:**
- Solo developers on small features
- Rapid prototyping phase
- Well-understood changes

## Spec Template

```markdown
# Feature: [Name]

## Summary
One-sentence description

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Edge Cases
- Edge case 1: Expected behavior
- Edge case 2: Expected behavior

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Out of Scope
- Thing we're not doing
```

## Integration with Codex

Install the `spec` family plugin, then use `$spec-adopt` in the target project.
It presents the pinned official `v0.16.0` installation for approval, records
the reviewed release and commit, and initializes with `specify init --here
--integration codex`. It will not use `--force` until the exact affected paths
have been shown and explicitly approved.

After adoption, `$spec-adopt` can separately offer the packaged
`cxpp-issue-sync` official extension. Its optional `after_tasks` hook previews
readiness and issue groups; declining it leaves official authoring unchanged.

Use the official workflow to produce and analyze a feature's `spec.md`,
`plan.md`, and `tasks.md`. Then run `$spec-sync` with the reviewed artifact SHA
to validate readiness and preview label-free stage/story issues. Task
granularity is opt-in. Confirm the dry-run before GitHub or ledger writes. The
sync deliberately requires no GitHub MCP server and adds no labels or adapter.

Each rich issue carries immutable artifact links, dependencies, acceptance,
quality commands, and a hidden stable identity suitable for `$flow-auto
<issue-number>`. Open and closed issues are idempotent, and successful writes
update the task ledger consumed by `project-next`.

---

*Triggers: spec driven, specification, SDD, planning, requirements*
