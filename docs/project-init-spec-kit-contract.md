# Project Init and Spec Kit Composition Contract

- Status: Accepted
- Decision issue: [#166](https://github.com/cooneycw/codex-power-pack/issues/166)
- Parent specification: [Wave 7 skill influence and behavioral fidelity](../.specify/specs/wave-7-skill-influence-fidelity/spec.md)
- Executable contract: [`.agents/project-init-spec-kit-contract.json`](../.agents/project-init-spec-kit-contract.json)

## Context

CxPP currently presents two incompatible project-creation products. The native
`project-init` skill and its tested helper create a deterministic local Python
project, optionally initialize local Git, and optionally create one local
commit. Generated `project-help`, the project plugin manifest, and agent
metadata instead advertise a multi-language, zero-to-GitHub orchestrator that
also installs Power Pack state and initializes Spec Kit.

Issue compilation has a similar ownership problem. The original CPP helper is
copied into generated evaluate, project-init, and project-next payloads and then
copied again into CxPP source and plugin payloads. The newer `spec-sync` copy is
safer about preview and consent, but both implementations assume one issue per
task and produce a one-line body. Neither contract is sufficient input for an
independently executed `flow-auto` lifecycle.

This record chooses the product boundaries before Wave 7 changes runtime
behavior. The checked-in JSON instance is normative; this document explains
the decisions for reviewers.

## Audit Findings

The audit covered:

- the native `.codex/skills/project-init/` skill and scaffold helper;
- `plugins/project/skills/project-init/agents/openai.yaml`;
- generated `project-help` and the project plugin manifest;
- native `spec-adopt` and `spec-sync` skills and their plugin metadata;
- CPP's `.claude/commands/project/init.md` orchestration workflow;
- every `speckit-tasks-to-issues.sh` payload in CxPP and the sibling CPP
  checkout.

Thirteen helper payloads were found: eight in CxPP and five in CPP. Eleven are
byte-identical copies of the original helper; the two `spec-sync` copies are
byte-identical to each other. The executable contract records every path and
observed SHA-256 digest so Stage 3 can retire the duplicates without relying on
another ad hoc inventory.

The contradictions are product claims, not missing convenience:

| Surface | Advertised promise | Verified behavior | Owner |
|---------|--------------------|-------------------|-------|
| `project-help`, project metadata, plugin manifest | Multi-language scaffold through pushed GitHub repository | Local Python scaffold; optional local Git and commit | #159 |
| generated CPP workflow | Toolkit installation, hooks, Spec Kit scaffold, placeholder first spec, immediate issue sync | None of these are part of the native CxPP helper | #159 |
| duplicated issue helpers | Useful issue per task and safe repeat runs | Thin one-line bodies; malformed task-like lines can be ignored; title-based dedup only | #160 |
| `spec-adopt` | Durable official Spec Kit adoption | Install follows a moving Git branch | #160 |

## Decision 1: Project Init Is a Safe Local Scaffold

`project-init` has one default outcome: create a new local Python project in a
reviewed target directory. It is explicit-only because it writes several files
and may create a Git repository or commit when those options are separately
requested. No activation request may silently widen the operation into GitHub
publication, Spec Kit installation, issue creation, plugin installation,
AGENTS.md influence, hook installation, permission changes, or trust decisions.

Publication, adoption, synchronization, and persistent influence are handoffs,
not hidden phases of project-init:

| User intent | Owning workflow | Project-init boundary |
|-------------|-----------------|-----------------------|
| Create a new local Python project | `$project-init` | Positive route; confirm destination and optional local Git/commit |
| Orient within an existing repository | `$project-lite` | Negative route; do not scaffold |
| Choose the next repository action | `$project-next` | Negative route; remain read-only |
| Publish a repository to GitHub | repository-aware GitHub workflow or reviewed `gh repo create` | Separate approval of owner, name, visibility, remote, and first push |
| Adopt official Spec Kit | `$spec-adopt` | Separate approval after previewing affected paths and the immutable release |
| Compile approved artifacts into issues | `$spec-sync` | Separate dry-run and approval; never a scaffold side effect |
| Add persistent CxPP guidance or hooks | `$cxpp-init` | Separate preview, trust, approval, status, and removal contract |

The destination confirmation authorizes only the local scaffold. Each later
handoff receives its own consent and can be declined without invalidating the
project.

## Decision 2: Official Spec Kit Is the Authoring Boundary

CxPP adopts GitHub Spec Kit rather than recreating `.specify/` by hand. The
reviewed boundary is release `v0.16.0`, resolving to commit
`5dce710ce099067c7d3f2ef47a37b9a1c300b327`:

```text
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.16.0
specify init --here --integration codex
```

Stage 3 may update the pin only through a reviewed contract change. It must
record the installed version. `specify init` remains consent-first and must not
receive `--force` unless the user has seen the exact paths at risk and explicitly
approves replacement.

CxPP's additional readiness and issue-compilation behavior is implemented as an official
Spec Kit **extension**:

- An extension is additive and is the upstream mechanism for new commands,
  external integrations, and quality gates.
- A preset is rejected because presets replace or compose core authoring
  commands and templates; CxPP does not need a fork of official authoring.
- A bundle is rejected for now because it only distributes a stack of existing
  primitives. One extension is not a stack. A later bundle may be proposed if
  CxPP has multiple independently versioned Spec Kit components.
- A hand-authored substitute scaffold is rejected because it would immediately
  establish a second, drifting authoring product.

The extension manifest is
[`extensions/cxpp-issue-sync/extension.yml`](../extensions/cxpp-issue-sync/extension.yml)
and its packaged mirror ships under `plugins/spec/extensions/`. It uses Spec
Kit manifest schema `1.0`, requires exactly `0.16.0`, provides the namespaced
`speckit.cxpp-issue-sync.preview` command, and offers only an optional
`after_tasks` preview. It delegates all compilation and writes to `$spec-sync`;
the extension contains no second compiler.

## Decision 3: Artifact Readiness Is a Blocking Gate

`spec-sync` previews issue groups only when it can identify one selected
feature directory. GitHub writes require every check below to pass and the user
to approve the analyzed commit and grouping:

1. `.specify/specs/<feature>/spec.md` exists and contains its required outcome,
   stories, requirements, and acceptance criteria.
2. `.specify/specs/<feature>/plan.md` exists and describes the implementation
   approach, constraints, and dependencies.
3. `.specify/specs/<feature>/tasks.md` is non-empty and every task-like line
   parses with a canonical stable task identifier.
4. The official consistency analysis has no unresolved errors across the three
   artifacts. Warnings must be shown and explicitly accepted.
5. No unresolved template markers, empty required sections, placeholder tests,
   or placeholder implementation descriptions remain.
6. Implementation tasks name exact repository-relative paths. A discovery task
   is allowed only when discovering those paths is its explicit outcome.
7. Every proposed issue group has an independently runnable acceptance
   checkpoint and named quality commands.
8. Cross-group dependencies are explicit, resolvable, and acyclic.
9. The user approves the artifact commit, proposed groups, repository, and
   resulting GitHub writes after the dry-run.

A non-empty task file that yields zero parsed tasks is always an error. A
task-like line with an invalid identifier or malformed syntax is always an
error. The compiler never treats skipped input as successful readiness.

## Decision 4: Compile Deliverable Groups, Not Micro-Issues

The default unit is an independently deliverable stage or story:

1. Use explicit stage, wave, or phase groups when the ledger defines them as
   independently mergeable checkpoints.
2. Otherwise group by user story when each story has its own outcome and
   acceptance checkpoint.
3. Refuse ambiguous automatic grouping and request a documented boundary.
4. Create one issue per task only when the user explicitly selects task
   granularity. Task mode is a compatibility option, not the CxPP default.

`spec-sync` is the only owner of compilation and synchronization. The canonical
runtime is `spec_sync.py` behind the compatibility-named
`speckit-tasks-to-issues.sh` launcher. Evaluate,
project-init, project-next, and other skills may call or consume its public
contract; they may not carry private compiler copies.

Each issue body contains:

- the deliverable outcome;
- every included task ID and full task description;
- user-story and requirement traceability;
- an independent acceptance checkpoint;
- mapped prerequisite issue numbers and unresolved dependency identifiers;
- constraints and explicit non-goals;
- exact quality commands;
- immutable GitHub blob links to the approved `spec.md`, `plan.md`, and
  `tasks.md` commit;
- a hidden stable identity of the form
  `spec-sync:v1:<repo>:<tasks-path>:<stage-or-story-id>`;
- the feature-ledger mapping that will be written after successful sync.

Idempotency searches the stable identity across open and closed issues. Closed
work is not recreated. Changed titles or descriptions do not create duplicates.
After a successful create or repair, `spec-sync` updates the selected
`tasks.md` Issue Sync ledger with the stable group identity, issue number, URL,
and state. A partial write reports exactly which mappings remain unresolved and
does not claim the ledger is synchronized.

`project-next` contract version `1.2` consumes only these ledger identities and
reports each feature's `spec.md`, `plan.md`, `tasks.md`, aggregate mapping state,
and next synchronization action. Task IDs found incidentally in issue prose are
no longer synchronization evidence. Missing mappings recommend synchronization;
stale or ambiguous mappings recommend repair and remain explicit uncertainty.

## Ownership and Rollout

| Issue | Owner contract | Required evidence |
|-------|----------------|-------------------|
| #158 | Deterministic `project-next` foundation, merged in PR #167 while this contract was in progress | Structured models, collection, ranking, and uncertainty boundary are available for the Stage 3 mapping integration |
| #159 | Align project-init skill, help, metadata, manifest, prompts, explicit-only policy, and negative routing | Fresh prompt inventory contains no contradictory claims |
| #160 | Implement the pin, extension, readiness gate, sole compiler, grouping, rich bodies, idempotency, mapping write-back, project-next mapping consumption, and duplicate retirement | Invalid artifacts fail loudly; approved artifacts create actionable Flow issues and mapped dependencies drive recommendations |
| #161 | Evaluate routing, consent, parsing, grouping, body, mapping, idempotency, and the complete handoff | Failures identify the correct contract layer |
| #162 | Keep persistent influence behind `cxpp-init` preview, trust, approval, status, decline, and removal | Declining influence leaves only the local scaffold |
| #163 | Publish migration guidance and dogfood the pinned clean-project lifecycle | Released workflow produces sequenced issues without hidden side effects |

Issue #166 changes no runtime behavior. It closes when this decision record,
the schema and instance, the Wave 7 artifact updates, and their deterministic
tests are reviewed and green. Runtime changes belong exclusively to the owners
above.
