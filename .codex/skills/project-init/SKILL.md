---
name: "project-init"
description: "Create a Codex-native Python project with quality gates and optional first commit"
---

# Project Init

Create a small, reproducible Python project from a checked-in scaffold. The
bundled helper writes only the target directory; it does not create a remote
repository, configure global Codex state, or install marketplace plugins.

## Procedure

1. Confirm the project name and destination. The target must be new or empty.
2. Locate this installed skill directory and run:

```bash
python3 <project-init-skill-dir>/scripts/project-scaffold.py <project-name> \
  --path <destination> --git --initial-commit \
  --author-name "<name>" --author-email "<email>"
```

3. In the new project, run `uv sync --extra dev` followed by `make verify`.
   Fix failures before creating a remote repository.
4. If the user explicitly requests GitHub publication, use `gh repo create` or
   the repository-aware GitHub workflow after showing the owner, visibility, and
   proposed remote. Never create or push a remote by default.
5. Offer `$spec-adopt` and `$spec-sync` separately when the project needs a
   specification and confirmed GitHub issue synchronization.

## Output Contract

The helper produces a Python package, tests, `AGENTS.md`, Makefile,
`.codex/cicd.yml`, and a GitHub Actions workflow with gitleaks before dependency
installation. `--initial-commit` creates one local Git commit only.
