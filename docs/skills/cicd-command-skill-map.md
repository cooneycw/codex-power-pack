# CI/CD Trigger to Skill Map

This file maps slash-style CI/CD triggers to Codex prompts and skill packages.

| Trigger | Prompt Entrypoint | Skill Package |
|---|---|---|
| `/cicd:check` | `.codex/prompts/cicd/check.md` | `.codex/skills/cicd-check/SKILL.md` |
| `/cicd:container` | `.codex/prompts/cicd/container.md` | `.codex/skills/cicd-container/SKILL.md` |
| `/cicd:health` | `.codex/prompts/cicd/health.md` | `.codex/skills/cicd-health/SKILL.md` |
| `/cicd:help` | `.codex/prompts/cicd/help.md` | `.codex/skills/cicd-help/SKILL.md` |
| `/cicd:infra-discover` | `.codex/prompts/cicd/infra-discover.md` | `.codex/skills/cicd-infra-discover/SKILL.md` |
| `/cicd:infra-init` | `.codex/prompts/cicd/infra-init.md` | `.codex/skills/cicd-infra-init/SKILL.md` |
| `/cicd:infra-pipeline` | `.codex/prompts/cicd/infra-pipeline.md` | `.codex/skills/cicd-infra-pipeline/SKILL.md` |
| `/cicd:init` | `.codex/prompts/cicd/init.md` | `.codex/skills/cicd-init/SKILL.md` |
| `/cicd:pipeline` | `.codex/prompts/cicd/pipeline.md` | `.codex/skills/cicd-pipeline/SKILL.md` |
| `/cicd:smoke` | `.codex/prompts/cicd/smoke.md` | `.codex/skills/cicd-smoke/SKILL.md` |

Canonical inventory: `.codex/prompts/cicd/*.md` and `.codex/skills/cicd-*/`.
