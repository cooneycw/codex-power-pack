# Wave 7 Release Validation

This is the aggregate, non-secret acceptance record for issue #163 and the
`v0.2.0` skill-influence release. Raw prompts, Codex event streams, temporary
Codex homes, and disposable project files are not retained.

## Release identity

- Payload version: `0.2.0+codex.20260807012317`
- Planned release tag: `v0.2.0`
- Runtime candidate: `7c1a5c256dbab40623803a160558eba18a9f9722`
- Rollback ref: `5961546c5e0164879348122134ccdd7b76d24cec`
- Final resolved release SHA: recorded in the GitHub `v0.2.0` release after
  this release PR is squash-merged to the CI-green `main` branch

Both installation and rollback acceptance use immutable commit SHAs. The tag
is a human-readable release pointer; its resolved commit is the authoritative
installation ref.

## Skill dogfood

The bounded live lane completed 20 representative sessions at
`2026-08-07T01:37:53Z` with Codex CLI `0.146.1`:

| Result | Count |
|---|---:|
| Passed | 18 |
| Explicit-only cases correctly unavailable | 2 |
| Activation, procedure, runtime, or output failures | 0 |
| Total sessions | 20 |

Direct activation recall, indirect activation recall, and negative precision
were each 100%. The run consumed 289,189 of the 320,000-token ceiling without
exhaustion or unverified accounting. The two unavailable cases were the known
`project-init` host-input limitation; they do not contribute to recall.

The three release-added negative cases proved that natural-language requests
do not silently install persistent routing, trust/enable hooks, or remove
routing/plugins without preview. Deterministic procedure/output coverage is
26/26.

## Implicit-entrypoint decision

The release retains only `$flow-auto` and `$project-next` for implicit
invocation. Both achieved 100% direct and indirect recall in checked cases, and
the combined negative set achieved 100% precision. Adding state-changing
`cxpp`, `project-init`, or Spec Kit skills would increase ambiguity and bypass
their explicit consent boundaries, so those skills remain discoverable through
`$skill-name` and `/skills` only. The two-entry inventory remains below the
4,096-byte metadata budget enforced by `.agents/skill-invocation-policy.json`.

## Marketplace install matrix

`scripts/release_validate.py` created a fresh isolated `CODEX_HOME` for every
scenario and retained only resolved refs, plugin names, versions, and counts.
The runtime candidate and rollback refs above produced:

| Scenario | Families | Result |
|---|---:|---|
| Minimal | 1 (`cxpp`) | passed |
| Recommended | 13 | passed |
| Full | 16 | passed |
| Upgrade: rollback ref → candidate | 13 | passed |
| Rollback: candidate → rollback ref | 13 | passed |

Codex CLI `0.146.1` cannot retarget an existing marketplace source with another
`marketplace add`. The verified transition previews and performs a bounded
`marketplace remove codex-power-pack`, immediately adds the new immutable
snapshot, then reinstalls the preserved family set. Installed plugins are not
removed during the marketplace-source replacement; if the new source fails,
the recorded prior ref is the recovery input.

Run the same matrix against the final release after merge:

```bash
make release-validate \
  CANDIDATE_REF=v0.2.0 \
  ROLLBACK_REF=5961546c5e0164879348122134ccdd7b76d24cec
```

## Spec Kit upgrade and rollback

Official Spec Kit tags resolved as follows:

- `v0.16.0` → `5dce710ce099067c7d3f2ef47a37b9a1c300b327`
- `v0.15.0` → `3b683c2292acbc0e18bd6b6767bb56ab5f6c78a2`

An isolated `uv` tool directory installed v0.15.0, upgraded to v0.16.0, and
rolled back to v0.15.0. Each `specify --version` check matched its requested
immutable release, and the user's ordinary tool installation was unchanged.

## Clean-project composition

A disposable `wave7-release-dogfood` project exercised the released ownership
boundaries:

1. `$project-init` produced a local Python project and explicit local commit;
   `uv sync --extra dev` plus `make verify` passed.
2. GitHub publication and persistent CxPP influence were declined, leaving no
   remote repository, GitHub issue, hook trust, or host configuration side
   effect.
3. The already-installed official Spec Kit v0.16.0 initialized its bundled
   Codex integration without `--force`; `.specify/spec-kit-version.json`
   records the reviewed release and commit.
4. `$spec-sync` compiled the approved two-task fixture into one independently
   deliverable stage in dry-run mode and did not update the ledger or GitHub.
5. `$project-next` reported `sync_spec` and no safe issue, correctly refusing
   to treat an un-published preview as startable work.
6. This issue's own `$flow-auto` run provides the real reviewed worktree, PR,
   merge, CI, and release lifecycle evidence.

The checked-in `tests/skill_evals/test_project_composition.py` fixture covers
the separately approved publication/mapping branch deterministically, including
rich issue bodies, stable mapping, and project-next consumption.

## Legacy issues and exclusions

Issues #135 and #140 were already closed with evidence. The ten deliberate
exclusions remain owned, explained, replaced, and time-bounded in
`.agents/skill-contracts.json`. Follow-up #173 will re-evaluate them using
post-release usage evidence no later than 2026-09-30.
