# Project Plugin Marketplace E2E

Issue #77 proves the first native Codex plugin distribution rail for Codex Power
Pack using the `project` family.

## Scaffold

- Marketplace catalog: `.agents/plugins/marketplace.json`
- Plugin root: `plugins/project/`
- Manifest: `plugins/project/.codex-plugin/plugin.json`
- Packaged skills:
  - `plugins/project/skills/project-help/`
  - `plugins/project/skills/project-init/`

The scaffold was created with the built-in `plugin-creator` helper and then
validated with:

```bash
python3 /home/cooneycw/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/project
```

Result:

```text
Plugin validation passed: .../plugins/project
```

## Fresh Config Local Transcript

This transcript uses a throwaway Codex home to prove the marketplace shape,
plugin install, and installed skill payload without touching the user's normal
Codex config.

```bash
mkdir -p /tmp/cxpp-plugin-e2e-local
CODEX_HOME=/tmp/cxpp-plugin-e2e-local \
  codex plugin marketplace add "$PWD" --json
```

Result:

```json
{
  "marketplaceName": "codex-power-pack",
  "installedRoot": ".../codex-power-pack",
  "alreadyAdded": false
}
```

```bash
CODEX_HOME=/tmp/cxpp-plugin-e2e-local \
  codex plugin list --available --json
```

Result excerpt:

```json
{
  "available": [
    {
      "pluginId": "project@codex-power-pack",
      "name": "project",
      "marketplaceName": "codex-power-pack",
      "version": "0.1.0",
      "installPolicy": "AVAILABLE",
      "authPolicy": "ON_INSTALL"
    }
  ]
}
```

```bash
CODEX_HOME=/tmp/cxpp-plugin-e2e-local \
  codex plugin add project@codex-power-pack --json
```

Result:

```json
{
  "pluginId": "project@codex-power-pack",
  "name": "project",
  "marketplaceName": "codex-power-pack",
  "version": "0.1.0",
  "installedPath": "/tmp/cxpp-plugin-e2e-local/plugins/cache/codex-power-pack/project/0.1.0",
  "authPolicy": "ON_INSTALL"
}
```

Installed skill payload:

```text
.codex-plugin/plugin.json
skills/project-help/SKILL.md
skills/project-init/SKILL.md
skills/project-init/reference.md
skills/project-init/scripts/speckit-tasks-to-issues.sh
```

Codex prints a warning when `CODEX_HOME` is under `/tmp` because it refuses to
create helper aliases there. The plugin marketplace add/list/install operations
still succeed.

## Git-Backed Install Path

Release-quality installs should pin the marketplace source to an immutable commit
SHA or signed release tag, per `docs/security/threat-model.md`.

```bash
codex plugin marketplace add cooneycw/codex-power-pack \
  --ref <release-tag-or-commit-sha> \
  --sparse .agents \
  --sparse plugins/project

codex plugin add project@codex-power-pack
```

The marketplace entry includes a `pinning` block that marks this requirement and
points installers to `codex plugin marketplace add --ref` as the resolving step.
