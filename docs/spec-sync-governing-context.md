# Governing context from Spec Sync

`spec-sync-context/v1` is derivative context on the existing issue body and printed
read evidence. It is not a requirements database, an approval store, a clean-analysis
record, a worker acknowledgement or an eligible native-wave assignment input.
The issue contract and existing judge remain authoritative. A source change does not
itself supersede an accepted decision or establish whether a change is material.

## Producer and immutable inputs

The sole compiler is `spec-sync/scripts/spec_sync.py`. Its sibling
`spec_context.py` reads immutable objects, extracts source text, manages the governing
region and checks context. The compiler passes its parsed task/group selection;
the helper does not implement another grouping compiler or write GitHub issues.

Compilation reads regular Git blob **bytes**, without text-mode newline conversion
or stripping stdout. Raw SHA256 values bind the actual reviewed spec, plan and tasks
objects. The feature paths must be relative to the trusted checkout, exist locally,
contain no symlink/escape, and have regular-file objects in the full immutable commit.
Individual objects/local files are limited to 2 MiB; Git reads have a 20-second budget.
The issue body is limited to 128 KiB and metadata to 32 KiB. Overlarge identities fail;
they are never shortened to fit. The trusted GitHub origin identifies the source;
`--repo` must match it. Cross-repository attestation is explicitly unsupported and
refused before writes rather than linking a local commit under another repository.

Working spec/plan must match immutable bytes exactly. Tasks may match exactly or be
the precisely recognized deterministic ledger transformation. With existing ledger
markers, only the single valid envelope is replaced, preserving prefix and suffix
bytes. Without a ledger, the historical writer applies UTF-8 `rstrip()` once, appends
exactly `\n\n## Issue Sync Ledger\n\n`, the canonical ledger and one final newline.
This narrowly recognized writer behavior is **not** general source normalization.
Duplicate, reversed or damaged markers, content/task lines inside a ledger, unrelated
heading removal, and changes elsewhere are refused. Existing reviewed ledgers are
validated too. Mapping identity, granularity, exact group tasks, issue number and URL
must agree with parsed source and complete issue inventory. If a task-set revision
leaves a historical mapping, its exact old task set must be independently verified
against the existing context and its immutable source; coherent refresh still requires
the reviewed path. Canonical row/state text
must reproduce the deterministic writer. State observations can be historical and
are updated from the inventory on convergence.

Results distinguish reviewed `before_sha256`, observed `after_sha256`, exact versus
verified ledger-successor comparison, and actual `writer_before_sha256` /
`writer_after_sha256` with deterministic successor evidence. Raw source hashes remain
raw even when a local ledger successor is accepted. `task_source_sha256` is the raw
reviewed task-source digest, not a replacement for any accepted #199 ledger binding.
All three local snapshots are rechecked before the first mutation, before subsequent
operations and immediately before ledger replacement. A local change detected after
remote success retains successful operation evidence and refuses the remaining step.
`--analysis-clean` remains a caller assertion; it is not fabricated official analysis.

## Focused extraction and evidence schema

Story ownership comes from explicit source story headings and parser-produced task
story declarations. Functional requirement rows are scoped only by a declared
`User Story` / `User Stories` column. Identifiers appearing incidentally in prose do
not confer requirement ownership. Selected groups aggregate their declared stories;
unrelated story sections/requirement rows are excluded. Global constraints, non-goals,
nonfunctional requirements and relevant/shared plan decisions retain source locations
and rationale. Shared plan material is labeled for applicability review.

The extract budget is 8 KiB. Missing/duplicate story declarations, unsupported or
unmapped requirements, unclassified sections and capped text are disclosed, together
with the paths/line locations to read. These states mean incomplete evidence, never
"no constraints" or proof of completeness. The consumer must resolve material ambiguity
under the existing authority, without imposing schemas/spec work on ordinary issues.

Metadata keys are exact and versioned: `schema`, `source_repository`,
`target_repository`, `tasks_path`, full `identity`, parser-produced `group`
(id, granularity, task IDs, story IDs, wording, checkpoint and source lines),
`artifact_commit`, `artifacts` (paths and raw SHA256s), `task_source_sha256`,
`locations`, `unresolved`, `scoped_sha256`, `previous_snapshot`,
`previous_artifact_commit`, `observed_revision`, `snapshot` and `integrity`.
Canonical metadata is UTF-8 JSON with sorted keys, compact separators, NFC strings,
no duplicate normalized keys, and only supported scalar/container values. Raw artifact
hashing and material byte comparison never apply NFC or newline normalization.
`snapshot` hashes canonical metadata excluding snapshot/integrity; `integrity`
hashes canonical metadata including snapshot, one newline and the visible region's
UTF-8 bytes. Neither checksum proves authorship, permission or approval.

## Ownership, refresh and recovery

One explicit context region owns the **entire** generated governing view: Outcome,
Tasks, story traceability, Acceptance checkpoint, sourced constraints, source coverage
and immutable artifact links. The #222 dependency region is separate and entirely
outside it. Duplicated, nested, crossed, damaged or edited regions refuse refresh.
Every byte outside these regions is preserved, including human decisions and old
receipts. Dependencies and governing context are composed into one body edit from the
freshly revalidated full original. Quality/mapping instructions remain outside the
owned governing region.

A default rerun with changed governing source refuses synchronization before **any**
create, dependency repair or ledger update. It cannot leave old Tasks/Acceptance/links
looking current while publishing changes from a newer snapshot. Review
`--refresh-context --dry-run`, then use the existing `--approve` path for the coherent
update. All groups are preflighted; the preview includes the proposed whole context,
old binding and dependency changes. Before an edit the compiler refetches the exact
issue identity/body/state and refuses conflicts. Partial writes and uncertain responses
retain successful actions and the failed operation; reconcile actual issue state by
stable identity before retry. Same-snapshot reruns preserve the revision chain and
converge without duplicate writes.

`--revision-reference` records an existing decision/reference to inspect. It grants
nothing. A material revision requires the existing judge's decision first; the new
view binds actual changed text/raw objects and the previous snapshot plus full
artifact commit. That predecessor permits verification of a historical ledger task
set on recovery; it grants no authority. An old human
approval or receipt stays tied to its old binding, including after a fresh checker
process reconstructs the source. Do not edit its fields to claim approval of the new
snapshot. Cache maintenance is never reported as acceptance approval.

Legacy unmarked issues remain usable for ordinary flow analysis. The compiler cannot
attest their current synchronization or infer that old headings are compiler-owned.
An opt-in refresh offers a concrete proposed managed replacement and refuses automatic
adoption: review the **complete body**, preserve human decisions, deliberately remove
or mark superseded generated sections as historical, then explicitly reconcile the
new owned region and re-preview. Never append a competing current-looking view.

## Installed ordinary-flow consumer

The generated flow-auto Step 2 snippet fetches a full body with explicit repository
into a unique temporary file, checks successful fetch, and executes the helper from
the absolute directory of the loaded installed flow package. It has no runtime import
of the spec plugin/compiler/project libraries and no project/global helper fallback.
For generated issues, select repository, issue, trusted checkout, tasks path, group and
exact task IDs independently from the assignment/reviewed mapping. The body cannot
choose arbitrary source paths or substitute another selected group/task set.

The checker reports actual retrieved paths/raw hashes, reconstructed governing **text**,
checkout byte differences, old/current snapshot bindings and observed revision references.
It also prints all bounded issue text outside the generated context, so human decisions
and old receipt bindings remain visible after restart. Ordinary/legacy reports print
the full issue body; redirecting the fetch to a temporary file must not hide the contract.
It verifies task wording against the cited immutable source lines and requires the
expected selection; it does not certify the compiler's complete grouping/analysis.
Failed fetch/checker execution is unreliable context, never an absent/current result.
Malformed generated markers do not downgrade to ordinary absent context. Read omitted
source locations before planning when material, and reconstruct again after resume or
compaction when a prior read may be stale. Offline execution proves this retrieval path,
not that a live agent understood or followed the procedure.

## Bounded source adoption and remaining acceptance

The global CPP PIN stays `f64a654f76ea8d26a33eb33f785f6e1065a823b6`.
The single raw flow-auto reference backport reproduces CPP858/PR866 commit
`cb166008d40aa9f63503b971f3c33551e09fe9e5` before native adaptation:

| Source | Git blob (compatibility identity) | Raw SHA256 | Bytes |
|---|---|---|---:|
| Before | `d4b0e860ad51a0ac428f89bfbfa797f5317b6c2c` | `a98d6f05d37220a9fee3051c80d4262959ca029fb3e2c9d8b9c1dbd16ba57708` | 65144 |
| After | `6ab2e7379284c906d16b722ec977c15a1aebb5e9` | `3e76614b58563813bdb3e8a204538ff25632117386223c3e1654ef57a9c4c799` | 69029 |

Exact new bytes pass once; unknown raw input refuses publication. Git SHA1 uses
`usedforsecurity=False`; SHA256 provides the separate integrity witness. The reviewed
raw delta is embedded in the overlay, not loaded from mutable test evidence. The
CxPP-specific substitution uses group/full-identity/raw-object context evidence and
an installed native helper instead of CPP's per-task 12-hex working-tree helper.
Existing native/runtime adaptations remove the CPP capability table. #221's GitHub
raw guard, #196 policy/audits and all 26 deferred/retained payloads are preserved.
Retire/update this narrow recipe only after reviewing upstream convergence; this is
not a claim of whole-tree source-PIN equivalence or a general adoption mechanism.

The single native helper source is hash/Git-mode-bound (100644/100755) in the overlay
and normally mirrored
into spec and generated flow packages. Publication prevalidates it before writes.
Immutable reports additionally compare bytes/mode to committed CxPP HEAD, rejecting
untracked or dirty dependencies even if an edited hash constant matches them. Checkout
umask read/write bits are not Git mode; any executable-bit change remains a mismatch.

The accepted #197/#199 contracts and original 22-case corpus are unchanged. This
producer/ordinary-flow repair supplies derivative retrieval evidence, not the complete
#199 package. #201 owns admission, generation, policy/hold and rebinding; #206 remains
parked; #203/#226 own live/pilot judgment evidence. All six #223 criteria have offline
producer/ordinary-consumer scenarios, but native compaction/live acceptance remains
explicitly outstanding. Merging this repair does not by itself justify closing #223.
