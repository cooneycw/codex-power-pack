---
description: Generate CI/CD pipelines for infrastructure tiers with approval gates
allowed-tools: Bash(PYTHONPATH=*), Bash(python3:*), Bash(ls:*), Read, AskUserQuestion
---

# /cicd:infra-pipeline - Infrastructure CI/CD Pipelines

Generate separate CI/CD pipelines for each infrastructure tier with appropriate approval gates.

## Instructions

1. **Read configuration** from `.codex/cicd.yml` infrastructure section.

2. **Generate pipelines:**

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd infra-pipeline --path "$(pwd)" --write
```

3. **Report what was generated** and explain the approval model:
   - Foundation: requires environment approval in GitHub (or manual in Woodpecker)
   - Platform: auto-deploy on merge (configurable)
   - App: auto-deploy on merge

## Pipeline Model

Each tier gets its own workflow file, triggered only by changes to that tier's directory:

- `.woodpecker/infra-foundation.yml` - Manual approval required
- `.woodpecker/infra-platform.yml` - Auto-deploy (configurable)
- `.woodpecker/infra-app.yml` - Auto-deploy

### Approval Gates

Foundation tier uses Woodpecker manual approval steps to gate deployments.

## Related

- `/cicd:infra-init` - Scaffold IaC directory structure
- `/cicd:infra-discover` - Audit existing cloud resources
- `/cicd:pipeline` - Application-layer pipeline generation
