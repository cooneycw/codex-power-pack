# AGENTS.md Configuration & Optimization

*From Codex Best Practices - r/ClaudeCode community wisdom*

## Optimized Prompts (+5-10% on SWE Bench) (53 upvotes)

**From "Optimized AGENTS.md prompt instructions":**

**Key Finding:** You can significantly improve performance by optimizing AGENTS.md

## Recommendations

1. **Experiment with System Prompts**
   - Don't accept defaults
   - Test different prompt formulations
   - Measure results on your specific use cases

2. **Include Project-Specific Context**
   - Architecture decisions
   - Coding standards
   - Common patterns in your codebase

3. **Be Explicit About Constraints**
   - What NOT to do
   - Token budgets
   - Performance requirements

## AGENTS.md Tips (30 upvotes)

**From "AGENTS.md tips" thread:**

1. **Structure Matters**
   - Use clear sections
   - Prioritize most important info at top
   - Use markdown formatting effectively

2. **Include Examples**
   - Show desired code style
   - Provide example workflows
   - Demonstrate edge cases

3. **Set Expectations**
   - Define quality bars
   - Specify test requirements
   - Clarify documentation needs

4. **Update Regularly**
   - AGENTS.md should evolve with your project
   - Add learnings from mistakes
   - Remove outdated guidance

## AGENTS.md Template

```markdown
# Project Name

## Overview
Brief project description

## Key Conventions
- Language/framework version
- Code style preferences
- Testing requirements

## Architecture
- High-level structure
- Key patterns used
- Important files/directories

## Commands
- Build: `npm run build`
- Test: `npm test`
- Lint: `npm run lint`

## What NOT to Do
- Don't modify X directly
- Avoid pattern Y
- Never commit Z

## Resources
- Link to docs
- Link to related projects
```

## Progressive Disclosure in AGENTS.md

Keep AGENTS.md focused on essentials. Use on-demand loading for details:

```markdown
## On-Demand Documentation

- `/load-best-practices` - Community wisdom
- `/load-api-docs` - API documentation
- Ask about specific topics to load relevant skills
```

## Hierarchy of AGENTS.md Files

Codex reads AGENTS.md from multiple locations:

1. **User-level:** `~/.codex/AGENTS.md` - Personal preferences
2. **Parent directories:** Inherited by child projects
3. **Project-level:** `./AGENTS.md` - Project-specific

## Best Practices Summary

- Keep it concise (under 500 lines)
- Most important info first
- Use clear section headers
- Include concrete examples
- Specify what NOT to do
- Update as project evolves

---

*Triggers: AGENTS.md, configuration, project setup, conventions*
