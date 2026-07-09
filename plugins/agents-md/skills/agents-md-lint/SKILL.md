---
name: "agents-md-lint"
description: "Trigger /agents-md:lint to audit AGENTS.md governance directives"
---

# agents-md-lint

Use this skill when the user asks for `/agents-md:lint`, `agents-md:lint`, an
AGENTS.md audit, or help checking whether AGENTS.md contains the governance
directives Codex needs for a repository.

This skill is read-only by default. Produce the lint report first. Modify
`AGENTS.md` only when the user explicitly asks you to apply fixes.

## Step 1: Detect Project Context

From the repository root, inspect:

- `AGENTS.md`
- `Makefile`
- `.codex/cicd.yml`
- `.codex/cicd_tasks.yml`
- `Dockerfile`, `docker-compose.yml`, or `docker-compose.yaml`
- language markers such as `pyproject.toml`, `package.json`, `go.mod`, or
  `Cargo.toml`

If `AGENTS.md` is missing, report `UNHEALTHY`, explain that the repository has
no Codex instruction surface, and suggest creating one before applying this lint.

## Step 2: Audit Required Directives

Check `AGENTS.md` for these categories with flexible, case-insensitive matching.
Prefer meaning over exact wording.

| Category | Required | What to look for |
|---|---:|---|
| CI/CD protocol | yes | Makefile targets as the canonical interface for build, lint, test, verify, deploy, audit, or equivalent gates. |
| Runtime boundary | yes | Clear boundaries for what the repo owns versus external services, host-managed tools, credentials, or deployment infrastructure. |
| Troubleshooting protocol | yes | Instructions to fix root causes, update CI/CD alongside code, avoid bypassing gates, and verify after repairs. |
| Quality gates | yes | `make lint`, `make test`, `make typecheck`, `make verify`, or equivalent project gates. |
| Docker conventions | conditional | If Docker files exist, directions to use Makefile targets or documented compose commands consistently. |
| Available commands | recommended | A scannable list of important Makefile targets or project commands. |
| Secret handling | recommended | Explicit prohibition on printing secrets, tokens, passwords, connection strings, or raw environment files. |

## Step 3: Score

Score six core points:

- CI/CD protocol: 1
- Runtime boundary: 1
- Troubleshooting protocol: 1
- Quality gates: 1
- Docker conventions: 1 if Docker files exist; otherwise auto-pass
- Available commands: 1

Track secret handling as a separate `PASS` or `WARN` because it is critical but
common in broader repo instructions.

Ratings:

- `HEALTHY`: 5-6 points and no required category fails
- `NEEDS ATTENTION`: 3-4 points, or 5-6 points with one required miss
- `UNHEALTHY`: 0-2 points, missing `AGENTS.md`, or multiple required misses

## Step 4: Report

Use this format:

```markdown
## AGENTS.md Lint Report

**Project:** {directory name}
**Framework:** {python/node/go/rust/mixed/unknown}
**Makefile:** {yes/no}
**Docker:** {yes/no}
**.codex/cicd.yml:** {yes/no}

### Directive Coverage

| Category | Status | Details |
|---|---|---|
| CI/CD protocol | PASS/FAIL | {evidence or missing directive} |
| Runtime boundary | PASS/FAIL | {evidence or missing directive} |
| Troubleshooting protocol | PASS/FAIL | {evidence or missing directive} |
| Quality gates | PASS/FAIL | {evidence or missing directive} |
| Docker conventions | PASS/FAIL/SKIP | {evidence, missing directive, or no Docker files} |
| Available commands | PASS/WARN | {evidence or recommendation} |
| Secret handling | PASS/WARN | {evidence or recommendation} |

### Score: {N}/6 ({percentage}%)

### Rating: {HEALTHY / NEEDS ATTENTION / UNHEALTHY}

### Suggested Fixes

{one short, exact block per FAIL/WARN}
```

## Step 5: Suggested Fix Blocks

For missing CI/CD protocol:

```markdown
## CI/CD Protocol

- Use Makefile targets for build, lint, test, typecheck, verify, audit, and deploy operations.
- If a target is missing for a repeated workflow, add the target instead of relying on ad hoc commands.
- Treat the Makefile and `.codex/` manifests as the canonical automation surface.
```

For missing runtime boundary:

```markdown
## Runtime Boundary

- Document which services, credentials, and deployment entrypoints are owned by this repository.
- Use host-managed services through documented pointers instead of starting or modifying external infrastructure implicitly.
- Call out any directories or files that are generated, vendored, or owned outside this repo.
```

For missing troubleshooting protocol:

```markdown
## Troubleshooting Protocol

- Reproduce failures through the documented Makefile or `.codex/` workflow before making fixes.
- Fix the application code and the CI/CD or test harness together when the failure exposes a workflow gap.
- After repairs, rerun the smallest relevant gate first, then the full verification gate.
```

For missing quality gates:

```markdown
## Quality Gates

| Target | Purpose |
|---|---|
| `make lint` | Run lint checks. |
| `make test` | Run the test suite. |
| `make typecheck` | Run static type checks when available. |
| `make verify` | Run the full local verification gate. |
```

For missing Docker conventions when Docker files exist:

```markdown
## Docker Conventions

- Prefer Makefile targets for Docker build, start, stop, logs, and status workflows.
- Keep Dockerfile and compose changes aligned with the application and CI/CD gates.
```

For missing available commands:

```markdown
## Available Commands

Run `make help` or inspect the Makefile for the full list. Common gates include
`make lint`, `make test`, `make typecheck`, and `make verify`.
```

For missing secret handling:

```markdown
## Secret Handling

- Never print secrets, tokens, passwords, connection strings, or raw environment file contents.
- Mask sensitive values before writing logs, reports, issues, or pull request comments.
```

## Applying Fixes

Only after the user asks you to apply fixes:

1. Read the current `AGENTS.md`.
2. Append or merge only the missing sections.
3. Keep existing project-specific instructions intact.
4. Show the resulting diff and recommend the relevant verification command.
