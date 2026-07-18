# Release Process

Codex Power Pack releases are distributed through the repo marketplace and
per-family Codex plugins. Release installs must be reproducible: users install a
reviewed release tag or immutable commit SHA, not a moving branch.

## Versioning

- Use semantic versioning for repository releases.
- Bump the major version for breaking distribution or plugin-shape changes.
- Bump the minor version for new plugin families, new skills, or new supported
  install surfaces that are backwards compatible.
- Bump the patch version for bug fixes, documentation corrections, and
  non-breaking metadata updates.
- Keep each plugin manifest version aligned with the release when the plugin's
  installed payload or user-visible metadata changes.

## Release PR Checklist

Every release PR must include:

1. Marketplace entry diff for `.agents/plugins/marketplace.json`.
2. Plugin manifest diff for every changed `plugins/<family>/.codex-plugin/plugin.json`.
3. Generated skill diff, if `.codex/skills/` or packaged `plugins/<family>/skills/`
   changed.
4. Hook, MCP config, and app config diff, if any plugin bundles those surfaces.
5. `CHANGELOG.md` entries moved from `Unreleased` into the release section.
6. The planned signed release tag and the resolved commit SHA that the tag points
   to.
7. A fresh Codex config upgrade transcript showing marketplace add, plugin add,
   and installed plugin list output.
8. Rollback notes recording the previous plugin ref, new plugin ref, and the
   reason for the upgrade.

Run `make verify` before tagging. If generated skill sources changed, run the
repo drift gates before opening the release PR.

## Tagging

Create release tags from the merge commit that passed verification on `main`.
Prefer a signed release tag:

```bash
git fetch origin main --tags
git checkout main
git pull origin main
git tag -s vX.Y.Z -m "vX.Y.Z"
git rev-parse vX.Y.Z^{commit}
git push origin vX.Y.Z
```

Record the resolved commit SHA in the release notes and upgrade transcript.
Branch refs are only for local development and dogfood. They do not satisfy
release acceptance.

## Installing A Release

Install only the plugin families needed for the current workflow. Include
`.agents` plus every selected `plugins/<family>` path in the sparse checkout.

```bash
codex plugin marketplace add cooneycw/codex-power-pack \
  --ref vX.Y.Z \
  --sparse .agents \
  --sparse plugins/project \
  --sparse plugins/github
codex plugin add project@codex-power-pack
codex plugin add github@codex-power-pack
```

For maximum reproducibility, use the resolved commit SHA instead of the tag:

```bash
codex plugin marketplace add cooneycw/codex-power-pack \
  --ref <immutable-commit-sha> \
  --sparse .agents \
  --sparse plugins/project
codex plugin add project@codex-power-pack
```

The marketplace pinning policy accepts immutable commit SHAs and signed release
tags, resolved through `codex plugin marketplace add --ref`.

## Suite Profiles And Sparse Expansion

The consent-first `/cxpp:init` and `/cxpp:update` skills can expand a pinned
marketplace snapshot using Minimal, Recommended, Full suite, or Custom profiles.
For any profile, the preview and command must include `.agents` plus one
`plugins/<family>` sparse path for every selected or already-preserved family.
The update path takes the union of installed and selected families so expanding
a profile never drops an existing plugin from the snapshot.

Before approval, record the selected plugins, all sparse paths, previous ref,
requested signed release tag or immutable commit SHA, and the requested ref's
resolved commit SHA. Reject floating branches. Installing a suite does not
authorize MCP, credential/provider, hook, exec-policy, or external-service
changes; those use separate consent prompts.

## Upgrade Procedure

1. Read the release notes and `CHANGELOG.md`.
2. Record the currently installed marketplace ref and plugin versions with
   `codex plugin list --json`.
3. Add or update the marketplace source with `codex plugin marketplace add` and
   the new `--ref`.
4. Reinstall only the selected family plugins with `codex plugin add`.
5. Confirm the installed plugin versions and marketplace source with
   `codex plugin list --json`.
6. Run a workflow smoke test for every upgraded family.
7. Attach the upgrade transcript to the release PR or release notes.

The transcript should be created from a fresh Codex config for release
acceptance so cached state does not hide install defects.

## Rollback

Rollback is the same operation with the previous pinned ref:

```bash
codex plugin marketplace add cooneycw/codex-power-pack \
  --ref <previous-plugin-ref> \
  --sparse .agents \
  --sparse plugins/project
codex plugin add project@codex-power-pack
```

Every release note must preserve:

- previous plugin ref
- new plugin ref
- resolved commit SHA for the new ref
- reason for the upgrade
- reason for rollback, if a rollback is performed
