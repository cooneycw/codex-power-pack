---
name: "agents-md-help"
description: "Trigger /agents-md:help for AGENTS.md governance command guidance"
---

# agents-md-help

Use this skill when the user asks for `/agents-md:help`, `agents-md:help`,
AGENTS.md governance guidance, or an overview of the AGENTS.md lint workflow.

## Purpose

AGENTS.md is the Codex instruction surface for a repository. This skill explains
the local `agents-md` family and points users at the lint workflow that checks
whether AGENTS.md tells Codex how to work safely in the project.

## Commands

| Trigger | Purpose |
|---|---|
| `/agents-md:help` | Show this AGENTS.md governance overview. |
| `/agents-md:lint` | Audit AGENTS.md for required CI/CD, boundary, quality-gate, and troubleshooting directives. |

## Guidance

When responding:

1. Keep the answer Codex-native and focused on `AGENTS.md`, `.codex/`, `Makefile`,
   and repository-local workflow boundaries.
2. Explain that `/agents-md:lint` is read-only by default: it reports missing or
   weak directives and proposes exact text only after the report.
3. Mention that generated CPP skill packages are drift-gated separately, while
   `agents-md-*` skills are CxPP-owned native packages.
4. Recommend pairing AGENTS.md lint with `make verify` when changing repository
   governance.

## Output

Provide a concise command overview and then the practical next step:

```markdown
AGENTS.md governance commands:

| Command | What it checks |
|---|---|
| `/agents-md:help` | Overview of AGENTS.md governance commands. |
| `/agents-md:lint` | Audits AGENTS.md for CI/CD, boundaries, troubleshooting, and quality gates. |

Next: run `/agents-md:lint` from the repository root to inspect the current file.
```
