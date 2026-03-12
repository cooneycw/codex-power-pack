---
description: Overview of AGENTS.md management commands
---

> Trigger parity entrypoint for `/agents-md:help`.
> Backing skill: `agents-md-help` (`.codex/skills/agents-md-help/SKILL.md`).

# AGENTS.md Commands

Audit and manage your project's AGENTS.md governance directives.

## Commands

| Command | Description |
|---------|-------------|
| `/agents-md:lint` | Audit AGENTS.md for CI/CD, Docker, and troubleshooting directives |
| `/agents-md:help` | This help page |

## Why AGENTS.md Governance Matters

AGENTS.md is the primary mechanism for directing Codex agent behavior. Without explicit CI/CD and troubleshooting directives, agents default to ad-hoc approaches that bypass your project's build pipeline.

`/agents-md:lint` checks that your AGENTS.md includes:

| Category | What It Checks |
|----------|----------------|
| CI/CD Protocol | Makefile targets referenced for build/test/deploy |
| Troubleshooting Protocol | Directives to fix CI/CD alongside code |
| Quality Gates | `make lint`, `make test`, `make verify` mentioned |
| Docker Conventions | `make docker-*` targets (if Docker files exist) |
| Deployment Protocol | `make deploy` or deployment workflow |
| Available Commands | Makefile targets listed for reference |

## Scoring

| Score | Rating |
|-------|--------|
| 5-6 / 6 | HEALTHY |
| 3-4 / 6 | NEEDS ATTENTION |
| 0-2 / 6 | UNHEALTHY |

## Quick Start

```bash
# Audit your AGENTS.md
/agents-md:lint

# Fix gaps in your Makefile first
/cicd:check

# Full project health: Makefile + AGENTS.md
/cicd:check && /agents-md:lint
```

## Related

- `/cicd:check` - Validate Makefile targets
- `/cicd:init` - Generate Makefile from detected framework
- `/project:init` - Full project scaffolding (generates AGENTS.md with directives)
