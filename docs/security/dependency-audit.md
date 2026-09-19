# Dependency advisory audit

`make dep-audit` first proves that the live scanner can distinguish a committed
known-vulnerable pin from a nonempty clean pin, then audits this repository, then
runs the existing Bandit command over `lib` and `scripts`, even if either advisory
stage fails. The aggregate target fails if either scanner fails. It needs Python 3.11+,
`uv`, `pip-audit`, `bandit`, and access to PyPI's advisory service. CI installs
those tools in its dependency-audit job. Ordinary `make verify` stays offline
with respect to this audit: it exercises interpretation controls and a real
offline export regression. Verification requires `uv`, `make`, and `git` as in CI;
it does not require `pip-audit` or contact the advisory feed.

The reusable security adapter and CLI share `lib/security/dependency_audit.py`.
Neither may substitute the scanner's installed environment for the target's
dependencies. The CLI exits **0 clean, 1 advisory, 2 unknown**. The adapter records
advisories as findings and unknown scans as errors, never as passed/skipped.
This does not change the separate severity policy in `lib.security.check_gate`.

## Population and boundaries

- Discover owned `uv.lock` files recursively. Report the source count, prune list,
  each audited source, and every examined package/version. Pruned directories are
  `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `vendor`, `controls`,
  `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, and `.ci-bin`. Directory symlinks
  are not followed; symlinked dependency source files are rejected.
- Export each lock with all extras and groups, `--locked --offline`, and
  `--no-emit-workspace`. Unlike `--frozen`, `--locked` also refuses a stale lock;
  it cannot resolve a new lock. Compare lock bytes before/after and compare the
  exported package/version set against an independent lock census. A partial or
  empty export cannot silently clear a nonempty lock.
- Query **all platform variants** by removing environment markers from exact
  pins. Use `--no-deps --disable-pip --strict`: no installation, package builds,
  or target dependency execution. Alternate versions of one package are queried
  in separate batches. This is advisory coverage, not a claim that Windows
  packages were installed or tested on Linux.
- Support public PyPI registry pins. Private registries, URLs, git dependencies,
  and non-workspace local dependencies are unknown, not silently omitted.
  Workspace source projects are excluded from third-party advisory querying;
  their code remains the responsibility of source analysis and tests.
- Explicitly pinned root `requirements.txt` is also audited when present,
  including alongside root/nested owned locks. Includes, ranges, hashes, URLs and
  index options fail closed. The caller must supply the full resolved dependency
  closure; this path establishes coverage of the listed pins, not completeness
  relative to an unrelated manifest or installed environment.
- Without either, a PEP 621 project explicitly declaring `dependencies=[]` and
  no optional/group/dynamic dependencies can report **explicitly dependency-free**.
  Unknown tool tables (including legacy uv, Poetry, PDM, Hatch and Rye dependency
  declarations) prevent that claim; known lint/test configuration tables are allowed.
  An empty requirements file or an undeclared/dynamic project is not that proof.
  Build-system tools and unowned/deployed environments are not inferred as part
  of runtime/dev dependencies.

The verdict is explicitly limited to **owned locks and root requirements**, not
whole-repository dependency coverage. Independent nested manifests without an
audited population are enumerated as `DEP-AUDIT-OUTSIDE-SCOPE` (adapter: `skipped`
with the same scope qualification). In this repository these include the
separately distributable `lib/creds`, `lib/cicd`, and `lib/security` pyprojects.
Their optional dependencies are not all in the root CI lock and are **not
certified clean**. Adding reproducible locks for those distributions is separate
work, not silently resolved or installed by this audit. A nested-only project
with no supported population reports unknown, never "not a Python project".

Projects using setup.py, Poetry or Pipenv without a supported lock/requirements
population now report an explicit adapter error. The old ambient-environment
fallback was not evidence about those projects. The security CLI's existing
severity-only exit policy is unchanged; adapter consumers must inspect `errors`.
Finding paths now identify the actual source (for example `lib/example/uv.lock`);
path-scoped suppressions written for the old `pyproject.toml` placeholder may no
longer match. Review such rules explicitly; the audit does not migrate them.

Reports must contain exactly the expected package/version population and valid
advisory records. Skips, malformed JSON, inconsistent exit statuses, unavailable
tools, and timeouts are unknown. Each export is bounded to 120 seconds and each
scanner batch to 180 seconds. Inputs use private temporary directories and are
removed after the scanner returns; concurrent runs do not share a requirements
file. Raw scanner errors are not echoed because they may contain credentials.

## Controls and maintenance

`controls/dependency-audit` registers an advisory case, a clean nonempty case,
and an incomplete-coverage case. A digest-pinned always-clean mutation proves
these controls can reject blindness. These constructed captures exercise the
same interpretation path as live results, but do not establish live lock
discovery or advisory-feed reachability. Unit regressions cover the exporter,
independent census, discovery, adapter and subprocess inputs.

The live probe queries `pyyaml==5.1` (must find an advisory) and
`iniconfig==2.3.0` (must examine it and find none). It never installs either.
A newly disclosed advisory against the good pin intentionally stops the probe;
review and replace that fixture, do not suppress the advisory. New project
findings need explicit follow-up disposition. This repair adds no suppression
ledger and does not upgrade project dependencies.

```sh
make dep-audit
python3 scripts/dependency-audit.py --from-capture controls/dependency-audit/cases/bad-incomplete/audit.json
make negative-controls
```

Adapted from CPP #961/#1043 and #1044/#1052, with a shared native core, an
independent lock/export census and preservation of CxPP's Bandit stage (#278).
