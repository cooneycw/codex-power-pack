---
name: "project-init"
description: "Create a new local Python project after the user explicitly selects this skill and confirms the destination. Do not use for existing-repository orientation, ordinary edits, GitHub publication, Spec Kit adoption or issue sync, or persistent Codex configuration."
---

# Project Init

Create a small, reproducible Python project from a checked-in scaffold. This is
an explicit-only workflow because it writes a new directory and can optionally
initialize local Git or create one local commit. The bundled helper never
creates a remote repository, configures global Codex state, installs plugins,
adopts Spec Kit, or creates GitHub issues.

## Selection Boundary

Use `$project-init` only when the user explicitly asks for a new local Python
project. Do not select it for:

- orientation or summaries inside an existing repository (`$project-lite`);
- choosing the next issue or cleanup action (`$project-next`);
- GitHub publication or remote creation;
- Spec Kit adoption (`$spec-adopt`) or issue synchronization (`$spec-sync`);
- persistent Codex Power Pack guidance or hooks (`$cxpp-init`); or
- ordinary changes to an existing project.

## Procedure

1. Confirm the project name and destination. Destination approval authorizes
   only the local scaffold; the target must be new or empty.
2. Locate this installed skill directory and run:

```bash
python3 <project-init-skill-dir>/scripts/project-scaffold.py <project-name> \
  --path <destination>
```

3. Add `--git` only when local Git initialization was requested. Add
   `--initial-commit --author-name "<name>" --author-email "<email>"` only when
   the user also requested a first local commit. In the new project, run `uv
   sync --extra dev` followed by `make verify`.
   Fix failures before creating a remote repository.
4. If the user explicitly requests GitHub publication, use `gh repo create` or
   the repository-aware GitHub workflow after showing the owner, visibility, and
   proposed remote. Never create or push a remote by default.
5. Offer `$spec-adopt`, `$spec-sync`, or `$cxpp-init` only as separate,
   reviewable handoffs. Declining any handoff leaves the local scaffold valid.

## Proportional follow-on work

Use the [canonical CxPP issue contract](https://github.com/cooneycw/codex-power-pack/blob/main/docs/agents/issue-contract.md)
for subsequent work: a small fix can stay in a short issue without spec/plan/tasks;
choose fuller specifications when uncertainty or coordination warrants them.
A missing remote reference should be reported, not used to block otherwise
authorized routine work or invent policy. Existing project instructions and
user authority remain binding. The local scaffold stays valid when all optional
handoffs are declined; this guidance does not authorize publication or installs.

## Output Contract

The helper produces a Python package, tests, `AGENTS.md`, Makefile,
`.codex/cicd.yml`, and a GitHub Actions workflow with gitleaks before dependency
installation. `--initial-commit` creates one local Git commit only.
