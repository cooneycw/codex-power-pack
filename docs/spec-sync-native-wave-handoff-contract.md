# Spec Sync to Native Wave Handoff Contract

- Status: Accepted for implementation
- Contract version: `1.0`
- Decision issue: [#199](https://github.com/cooneycw/codex-power-pack/issues/199)
- Native assignment contract: [`native-codex-wave-contract.md`](native-codex-wave-contract.md)
- Scenario corpus: [`spec-sync-native-wave-handoff-scenarios.json`](../tests/fixtures/spec-sync-native-wave-handoff-scenarios.json)
- Runtime consumer: issue [#201](https://github.com/cooneycw/codex-power-pack/issues/201)

## Purpose

`spec-sync` can compile approved Spec Kit stages or stories into stable GitHub
issue mappings. `project-next` 1.3 can classify and rank a complete local
repository inventory. Neither result alone proves that a native wave may assign
the recommended issue. This contract defines the deterministic, fail-closed
handoff between those existing owners and the assignment lifecycle in #201.

The handoff prevents a missing mapping, stale artifact, duplicate claim, cycle,
incomplete inventory, or unresolved repository-qualified blocker from becoming
an assignment input. In particular, `cooneycw/codex-power-pack#44`,
`cooneycw/kyle#44`, and `cooneycw/sage#44` are three different issue identities.
A closed local issue never satisfies a qualified blocker in another repository.

## Authority and fixed boundaries

This contract consumes, and does not replace, three accepted boundaries:

1. The native session, assignment, gate, and recovery contract from #197. The
   exact accepted file is bound by SHA-256
   `779c2aa4f1470ef66c5eb87b0b3bdb1e22386408a633bf5a31a99ff2c307ded5`.
2. The sole `spec-sync` compiler. Its implementation is distributed through the
   generated `.codex/skills/spec-sync/scripts/spec_sync.py` and packaged
   `plugins/spec/skills/spec-sync/scripts/spec_sync.py` surfaces; those are one
   compiler contract, not two independently evolving compilers.
3. The read-only `project-next` behavioral contract version `1.3`, including
   its classification and deterministic ranking entry points.

The partial dependency-grammar convergence recorded by #184 remains unchanged.
Both existing grammars require declaration-position references, strip fenced
and inline code, and tolerate Markdown emphasis and punctuation. Grading,
`uncertain`, `Blockers:` / `Prerequisites:`, ranges, and duplicate spec-task
handling retain the deliberately different behavior documented in
[`project-next-contract.md`](project-next-contract.md). This handoff preserves
the resulting dependency evidence and adds canonical repository identity; it
does not silently make either parser implement the other parser's rules.

This issue does not:

- create, edit, close, or synchronize a GitHub issue;
- recompile a specification or implement another issue compiler;
- change `project-next` collection, classification, ranking, or output 1.3;
- append a native assignment, gate, hold, release, merge, or completion event;
- implement the runtime admission decision owned by #201;
- prove transport, wake, or end-to-end wave behavior owned by #198, #203, or
  #206;
- query or mutate Kyle or Sage during this contract delivery; or
- synchronize the unrelated historical 36-task specification.

## Handoff position

The handoff sits after compilation and recommendation but before assignment:

```text
reviewed spec/plan/tasks
        |
        v
sole spec-sync compiler ---> Issue Sync ledger
                                  |
complete project-next 1.3 state -> candidate + local classification
                                  |
qualified dependency inventory --+
                                  v
                 handoff/v1 conformance package
                                  |
                         #201 admission check
                                  |
                    native assignment event or refusal
```

A `project-next` candidate is necessary local evidence, not sufficient global
assignment evidence. The #201 consumer must receive and validate the handoff as
one immutable package. If validation cannot establish every required fact, it
must emit no assignment input and must not try to repair the source artifacts
or infer a blocker state.

## Canonical identity

### Specification mapping identity

The compiler remains authoritative for the mapping identity:

```text
spec-sync:v1:<owner/repository>:<repository-relative-tasks-path>:<group-id>
```

`group-id` is the compiler-produced stage, story, or explicitly requested task
group. A mapping binds exactly one stable identity to one canonical issue key
and an exact, ordered task-ID set. Every selected task occurs in exactly one
group. Every selected group occurs in exactly one ledger row. Duplicate group,
task, stable-identity, or issue claims are invalid; consumers do not choose a
winner.

The stable mapping identity contains no observation time, collection time,
worker identity, or current issue state. Those facts can change while the
mapping continues to identify the same compiled group.

### Issue identity

An issue key is serialized as lowercase `owner/repository#number`, after the
repository owner and name have been resolved by a trusted collector. The
number is a positive decimal integer without leading signs. An unqualified
`#number` may be resolved relative to its source repository only before the
handoff is serialized; the serialized dependency graph never contains an
unqualified issue number.

Equality compares the complete key, not the numeric suffix. A dependency on
`cooneycw/kyle#44` may be satisfied only by state evidence whose key is exactly
`cooneycw/kyle#44`. Evidence for `cooneycw/codex-power-pack#44` is irrelevant
to that edge even if the local issue is closed.

## Required package

One `spec-sync-native-wave-handoff/v1` package contains all of the following.
No field named `complete`, `ready`, or `startable` can substitute for the
underlying evidence.

### 1. Contract bindings

- schema identifier and contract version;
- #197 contract path and exact SHA-256;
- `spec-sync` identity version `spec-sync:v1` and implementation surface;
- `project-next` contract version `1.3`; and
- #184 partial-convergence marker and the #201 consumer identifier.

A version or hash mismatch invalidates the package. A consumer that supports a
newer version must still reject unknown fields that affect identity,
dependencies, inventory scope, or admission until that version is explicitly
negotiated.

### 2. Immutable artifact snapshot

The artifact snapshot binds:

- canonical source repository;
- one full 40-hex Git commit containing the reviewed artifacts;
- repository-relative paths and SHA-256 digests for `spec.md`, `plan.md`, and
  `tasks.md` at that commit;
- the official consistency-analysis result, tool/version, and result digest;
  and
- the selected group granularity and exact task set.

The files must exist at the bound commit and their bytes must match their
digests. Working-tree contents, a branch name, or a moving ref such as `main`
is not immutable provenance. A clean-analysis Boolean supplied by a caller is
not enough without the bound analysis record.

### 3. Issue Sync mappings

Each mapping carries its compiler-produced stable identity, granularity,
group ID, ordered task IDs, canonical issue key, and ledger-source digest. The
package also carries the complete selected task set so omission can be detected.

The mapping set is valid only when:

- each selected task is claimed once;
- each selected group and stable identity is claimed once;
- each mapping's repository, tasks path, and group reconstruct its exact
  `spec-sync:v1` identity;
- each mapped issue key is unique within the selected synchronization; and
- the ledger source is derived from the same immutable `tasks.md` snapshot or
  from its one idempotent write-back successor explicitly linked by digest.

Missing, ambiguous, stale, or duplicate mappings produce no assignment input.
Re-running the compiler's ledger write with the same mapping set must be
byte-idempotent and must not create another issue identity.

### 4. Dependency graph

The graph contains the exact task edges, group edges, and canonical issue edges
used for admission. Each edge records its source artifact or issue declaration
and its canonicalized endpoints. Internal task ordering may collapse inside a
group; cross-group and issue blockers may not disappear during that collapse.

The graph must be acyclic after task-to-group and group-to-issue projection. A
self-edge, missing endpoint, duplicate task ownership, or strongly connected
component with more than one node invalidates the package. The consumer may
not break a cycle by ordering its members heuristically.

### 5. Complete issue inventory

Inventory completeness is evidence, not a Boolean assertion. The snapshot
defines two collection modes:

- `full-repository` for the source repository: the exact `state=all` query,
  configured limit, every page or terminal cursor, collector version, and
  response digest must prove that project-next's local issue inventory was not
  truncated; and
- `referenced-keys` for an external repository: every exact qualified blocker
  key used by the dependency graph must have a successful key-specific state
  lookup and state-evidence digest. Listing every unrelated issue in that
  external repository is not required.

The snapshot binds:

- the canonical repository scope and collection mode for every repository;
- one collection revision and the consumer/base revision for which it was
  collected;
- each repository query, terminal-pagination evidence, collector identity, and
  source-provided revision or response digest;
- normalized issue records keyed by full `owner/repository#number`, including
  `OPEN`, `CLOSED`, or `UNKNOWN` and the evidence digest for that exact key;
- a canonical inventory digest over the normalized scope, queries, revisions,
  terminal proofs, keys, states, and evidence digests; and
- observational `collected_at`, policy `max_age_seconds`, and derived
  `fresh_until` fields used only for freshness validation.

The scope is the source repository plus the transitive set of repositories
named by qualified blockers. Completeness fails when a scoped repository or
required key is absent, a page is truncated, the terminal cursor is missing, a
query failed, the canonical digest does not recompute, or an external lookup
has no evidence. `complete: true`, a timestamp, or a caller's assertion cannot
cure any of those failures.

### 6. Candidate and local recommendation evidence

The package records the candidate's canonical issue key and the complete
`project-next` 1.3 result digest. The result must classify the candidate as
available and select it as `next_startable_issue` under complete local
inventory. Classification and ranking are replayed through the existing
`classify_repository` and `recommend` entry points; the handoff does not
reimplement them.

Local availability does not override the qualified dependency graph. A
candidate that project-next ranks first remains suppressed when the handoff has
an `OPEN` or `UNKNOWN` external blocker or cannot prove the external key's
state.

### 7. Disposition and assignment input

The producer records either:

- `eligible`, with an immutable `assignment_input` containing the candidate
  key, mapping identity, artifact snapshot ID, dependency digest, inventory
  digest, handoff digest, and required policy/contract versions; or
- `rejected`, with a stable reason code, structural witness, and
  `assignment_input: null`.

This `assignment_input` is data for #201. It is not itself an assignment, gate,
or authority grant. #201 must implement the normative admission checks before
the current coordinator generation can append a native `queued` event.

## Determinism and freshness

### Stable same-input digest

The handoff digest is lowercase SHA-256 over RFC 8785-style canonical JSON of:

- contract and source-contract versions/hashes;
- immutable artifact snapshot fields and file digests;
- sorted mapping rows and selected task IDs;
- sorted canonical dependency edges;
- candidate key and the project-next 1.3 result digest; and
- inventory scope, collection/base revisions, normalized query/terminal proof,
  exact issue states, state-evidence digests, and canonical inventory digest.

Maps are sorted by stable identity, task IDs naturally by canonical string, and
issue/dependency records by complete canonical key. Duplicate keys are rejected
before hashing. Observational `observed_at`, `collected_at`, `fresh_until`, log
sequence, and transport metadata are excluded. Therefore a same-input rerun at
a different observation time has the same stable mapping identity and handoff
digest.

A changed artifact commit or file digest, mapping, dependency edge, candidate,
project-next result, inventory scope, issue state, state-evidence revision, or
inventory digest intentionally creates a different handoff digest. A new
inventory observation with byte-identical normalized evidence does not.

### Consumer invalidation and recollection

Before appending an assignment, #201 invalidates the package and requires a new
collection when any of these is true:

- current time is later than `fresh_until` under the recorded policy;
- the consumer/base revision differs from the bound revision;
- the artifact, ledger, dependency, project-next result, or repository scope
  digest differs from the bound value;
- a webhook, ETag, source revision, or other trusted signal says a referenced
  issue may have changed;
- the coordinator changes the candidate, lane, assignment requirements, or
  policy in a way that changes admission evidence; or
- any required external key has missing, contradictory, `OPEN`, or `UNKNOWN`
  evidence.

Recollection creates a new inventory evidence record. If normalized evidence
changes, it also creates a new inventory and handoff digest and requires a new
admission decision. If recollection is unavailable, the worker remains locally
suppressed and no assignment event is appended.

## Fail-closed reason codes

| Reason | Required structural witness | Result |
|---|---|---|
| `artifact_mismatch` | bound commit/path/digest differs from observed immutable bytes | no assignment input |
| `mapping_missing` | selected task or group has no ledger row | no assignment input |
| `mapping_ambiguous` | one task/group resolves to multiple rows | no assignment input |
| `mapping_stale` | identity reconstructs to another repository/path/group | no assignment input |
| `duplicate_group_claim` | one stable identity or group maps to multiple issue keys | no assignment input |
| `duplicate_task_claim` | one task occurs in multiple selected groups | no assignment input |
| `dependency_cycle` | explicit directed edges form a cycle | no assignment input |
| `inventory_incomplete` | missing scope/key/query page/terminal proof or failed collection | no assignment input |
| `inventory_stale` | freshness or consumer/base revision no longer matches | no assignment input |
| `inventory_digest_mismatch` | normalized evidence does not hash to the declared digest | no assignment input |
| `blocker_open` | exact canonical blocker key has `OPEN` evidence | no assignment input |
| `blocker_unknown` | exact key is absent, contradictory, or `UNKNOWN` | no assignment input |
| `qualified_key_collision` | evidence matches only the numeric suffix or another repository | no assignment input |

An exact canonical blocker with current `CLOSED` evidence satisfies only that
edge. It does not make another open/unknown edge eligible and does not imply
that the candidate is otherwise ready.

## Conformance evidence and ownership

The scenario corpus is reviewed contract conformance evidence. Tests inspect
the structural facts that make each case valid or invalid, call the actual
`spec-sync` stage/story grouping and ledger functions, and replay unchanged
project-next classification/ranking entry points. Expected labels never prove
their own result.

The corpus is not a production admission reducer and not live proof. Issue #201
must implement and test every normative admission decision before assignment.
Issues #198 and #206 own delivery evidence and wake implementation, and #203
owns live three-worker acceptance. The unrelated historical 36-task
specification remains explicitly excluded from the selected artifact set and
is not synchronized by this contract.
