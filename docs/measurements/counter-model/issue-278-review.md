# Issue #278 counter-model review record

Two read-only Claude Code reviews ran before this delivery (implementer: Codex).
Both returned CHANGES REQUESTED. This is the preserved second transcript, not a
clean-review claim. The native reviewer did not expose an exact model identifier.
The installed receipt parser rejects the numbered `(Medium-high)` headings as
unparseable, so the companion receipt records `skipped/reviewer-unavailable`
under its existing vocabulary. That parser result does NOT mean no review ran.
No third review was attempted; final fixes and base integration were verified
locally and by CI, not independently re-reviewed.

## Implementer dispositions after the second pass

- Prior six blocking findings: reviewer verified fixes (see transcript table).
- Finding 1: accepted the reviewer's scoped alternative. CLI enumerates independent
  unaudited manifests and qualifies its verdict; adapter reports exclusions and
  nested-only projects as unknown. Regressions cover actual library manifests.
  Creating new library locks is separate work, recorded in Nit Store #227:
  https://github.com/cooneycw/codex-power-pack/issues/227#issuecomment-5741577005
- Finding 2: distinct missing-tool, timeout and OS-execution errors implemented and
  tested. `is_available()` remains as a compatibility helper, not a gating premise.
- Finding 3: all discovered source files reject symlinks; fallback regression added.
- Finding 4: docs explicitly state the offline uv/make/git test prerequisites.
- Findings 5–6: suppression-path migration documented; changelog added.
- Finding 7: strict version-spelling mismatch has an UNKNOWN regression.
- Existing general security CLI error-only exit policy is explicitly outside this
  population repair and recorded in Nit Store #227:
  https://github.com/cooneycw/codex-power-pack/issues/227#issuecomment-5741540241

The transcript mentions #286 once while discussing scope; this review was for
#278, before the separate upgrade issue was delivered. Its suggestions are review
data, not authorization to expand the approved outcome.

## Preserved second-pass transcript

## Claude Code review

## Verdict

**CHANGES REQUESTED** — the six previously-reported blockers all check out as fixed; one substantive coverage gap remains that is the same failure class this issue repairs.

## Summary

I re-verified each claimed fix against the tree:

| Prior finding | Status |
|---|---|
| JSON captures gitignored | **Fixed.** `.gitignore:76` negation works (no parent dir is excluded; `*.json` at :48 is file-only), and `tests/test_dependency_audit.py:288-296` proves it with `git check-ignore --no-index`, which is the right flag for staged fixtures. |
| Bandit skipped on audit failure | **Fixed.** `Makefile:104-111` captures `audit_status` via `A && B \|\| audit_status=$?`, always runs Bandit, then prefers the audit status. `tests/test_dependency_audit.py:263-280` exercises all four probe/audit/bandit combinations with PATH shims (expected `2` is make's own failure code — correct). |
| Legacy tool dev-dependencies falsely "empty" | **Fixed.** `dependency_audit.py:131` conservative allowlist; 7 parametrized regressions incl. `[tool.uv] dev-dependencies`, pdm, hatch, rye, poetry. |
| Root `requirements.txt` hidden by root lock | **Fixed.** `dependency_audit.py:107-112` plus `test_root_requirements_not_hidden_by_nested_lock`. |
| Confusing export mismatch | **Fixed.** `dependency_audit.py:170-175` reports missing/extra sets. |
| Mutation assertion | **Fixed and correct.** Tracing `scripts/check-negative-controls.py:413-448`: gate=anchor is GOOD on the BAD case and all anchors are GOOD, so `UNRESOLVED` is exactly what the register returns. The `#: NEGATIVE-CONTROL: dependency-audit` directive matches `REGISTRATION_RE` (:100) and resolves under `controls/`. |
| Legacy security-CLI exit policy ignores `errors` | Confirmed out of scope: `cli.py:37/45/53` keys only on `has_blockers`, `errors` are display-only (`output/novice.py:69`). Documented, not claimed fixed — acceptable for #286. |

I could not execute anything, so anchor-digest verification, the live `uv export` test, and PyPI reachability are unverified by me (they are covered by tests that will run in CI).

## Findings

### 1. (Medium-high) Three in-repo declared dependency populations are silently outside the audited population, and the gate still prints clean

`discover()` (`lib/security/dependency_audit.py:91-116`) walks only for `uv.lock` and then consults **root-level** `requirements.txt` / `pyproject.toml`. Nested manifests without a lock are neither audited nor turned into `Unknown`.

That is not hypothetical here:

- `lib/creds/pyproject.toml:12-25` declares `python-dotenv`, `boto3`, `fastapi`, `uvicorn`, `cryptography`, `pyyaml`.
- `lib/cicd/pyproject.toml:10-14` declares `pydantic`, `pyyaml`.
- `lib/security/pyproject.toml:12-14` declares `pyyaml`.
- Root `pyproject.toml` has **no** `[tool.uv.workspace]`, and `uv.lock` contains no `boto3`/`fastapi`/`uvicorn`/`cryptography`/`python-dotenv` entries and no workspace table (verified by grep).

So `make dep-audit` on this repository reports `sources=1 discovery=owned-lock-walk`, audits only the root lock, and exits 0 "clean" while five third-party packages declared by shipped, separately-distributable projects (hatchling build-system, `[project.scripts]` console entry points) were never queried and never flagged UNKNOWN. `docs/security/dependency-audit.md` states the population is "owned `uv.lock` files recursively" plus root requirements, but it never says nested declared populations are dropped without notice, and nothing in the CLI output scopes the clean verdict. Ironically, the fail-closed machinery already exists — `population()` on `lib/creds/pyproject.toml` would raise `Unknown("declared dependencies require uv.lock…")` — discovery just never hands it that file.

The adapter has the mirror defect: a project whose only manifests are nested is reported `"pip-audit (not a Python project)"` (`lib/security/modules/pip_audit.py:26-31`), a false skip rather than an error.

Pick one, in preference order: (a) extend discovery to nested `pyproject.toml`/`requirements.txt` and let unlocked ones fail closed to UNKNOWN; (b) keep the scope but *enumerate the excluded manifests in the report* ("not audited: lib/creds/pyproject.toml — declared deps, no lock") and say so in the doc, so exit 0 cannot be read repository-wide. Either way add a regression asserting this repo's nested manifests are accounted for, otherwise the next added subproject re-opens the hole silently.

### 2. (Low-medium) Missing tool is now an ambiguous error, and `is_available()` is dead code

`scan()` no longer calls `is_available()` (`lib/security/modules/pip_audit.py:12`), so an uninstalled pip-audit (or uv) surfaces as `pip-audit UNKNOWN (uv.lock): pip-audit unavailable or exceeded 180s` — conflating "not installed" with "timed out". Because the CLI exit policy ignores `errors` (finding-table row above), the message text is the only signal a user gets, and it contradicts `plugins/security/skills/security-scan/SKILL.md:14-17` ("when those tools are installed… reports missing optional tools rather than pretending they ran"). Distinguish the two in `run()` (e.g. pre-check `shutil.which(command[0])` and say "not installed"); keep both as errors, not skips.

### 3. (Low) Symlink policy is asymmetric

`discover()` rejects a symlinked `uv.lock` (`dependency_audit.py:104-105`) but appends root `requirements.txt`/`pyproject.toml` with no such check (:108-111). A symlinked root requirements file escapes the owned-file contract the lock branch enforces. One `is_symlink()` guard closes it; the doc's "symlinked lockfiles are rejected" should then read "source files".

### 4. (Low) Host coupling understated for `make verify`

`tests/test_dependency_audit.py:65-72` shells out to real `uv export` against the real lock, and `:263-280` shells out to real `make`. Both run under ordinary `pytest`/`make verify`. CI's verify image has `uv`, `make` and `git`, so CI is fine, but `docs/security/dependency-audit.md` ("Ordinary `make verify` stays offline with respect to this audit: it exercises the interpretation controls instead") reads as tool-free. Either amend the doc or, consistent with the register's UNAVAILABLE philosophy, skip with an explicit named reason rather than erroring — do not skip silently.

### 5. (Low) Suppression paths change meaning

`Finding.file_path` moves from the literal `"requirements.txt"`/`"pyproject.toml"` to the discovered source path (`pip_audit.py:41`). Existing `.codex/security.yml` suppressions matched by `Suppression.matches` (`models.py:80-87`) on the old path stop matching. The direction is safe (more findings shown), but it is an undocumented user-visible break; note it in the doc and `CHANGELOG.md`.

### 6. (Nit) `CHANGELOG.md` not updated

`make dep-audit` semantics and the pip-audit adapter contract both changed user-visibly; no test enforces a changelog entry, but the repo keeps one and it already references pip-audit.

### 7. (Nit) No regression for version-string canonicalization

If pip-audit echoes a canonicalized version that differs from the lock string (post/local segments, epochs), `validate()` (:200) raises `audit incomplete` and the whole gate goes UNKNOWN. Correct direction, but untested; one parametrized case would pin the intended behavior so a future "relax the comparison" change has to be deliberate.

## Red cases

Concrete inputs that would flip my verdict:

- **→ PASS:** root `pyproject.toml` gains `[tool.uv.workspace] members = ["lib/*"]` and `uv.lock` gains `boto3`/`fastapi`/`uvicorn`/`cryptography`/`python-dotenv` registry entries. Finding 1 dissolves; everything else is a nit.
- **→ PASS:** `discover()` appends nested `pyproject.toml`/`requirements.txt` (letting `population()` fail closed), **or** `report()` prints an explicit "not audited" list for them and the doc states the exclusion. Either makes exit 0 an honest, scoped claim.
- **→ CHANGES REQUESTED regardless of Finding 1:** a `lib/*/uv.lock` appearing later without the nested-manifest question settled — the same blind spot would re-open with no diff to this gate.
- **→ BLOCKED:** `sha256` in `controls/dependency-audit/control.json` not matching `anchors/constructed-blind.py` bytes (register returns UNRESOLVED at `check-negative-controls.py:355-358`), or `git check-ignore` reporting the capture fixtures ignored on a fresh checkout. I could not execute these; if the maintainer's `make verify` shows either, the control proves nothing and the PR is blocked on fixture repair, not on Finding 1.
- **→ BLOCKED:** CI's `pip install uv` resolving a uv that renamed/removed `--no-emit-workspace`, making every `population()` call return UNKNOWN (exit 2) on the real lock. `test_real_repository_export_is_nonempty_and_immutable` catches this wherever `uv` exists, so a green CI run rules it out.

## Recommended next steps

1. Resolve Finding 1 — audit nested declared populations or print/document the exclusion explicitly, plus a regression over this repo's own manifests.
2. Restore precise "not installed" messaging (Finding 2) and remove or use `is_available()`.
3. Add the requirements/pyproject symlink guard (Finding 3).
4. Reconcile the doc with the tests' host requirements (Finding 4), and record Findings 5-6 in doc/CHANGELOG.
5. Confirm locally that `make verify` (negative-controls + new tests) and `make dep-audit` are green, since anchor provenance and the live probe are the two things this review could not execute.

