# Local Markdown Wayfinding

Use this tracker when there is no configured external tracker or its writes are
not authorized. Keep one directory per map:

```text
<map-directory>/
|-- map.md
`-- tickets/
    |-- <ticket-id>.md
    `-- ...
```

Do not add a generated README, duplicate index, or ticket ledger. The map is the
low-resolution index; open ticket state comes from the ticket frontmatter.

## Map format

```markdown
---
wayfinder:
  kind: map
  version: 1
  title: <readable title>
  status: proposed | active | cleared
  tracker: local-markdown
  destination_status: proposed | agreed
  tickets_dir: tickets
---

# <title>

## Destination

<destination and its agreement status>

## Notes

<sources, constraints, and relevant skills>

## Decisions so far

<one linked gist per closed ticket, or "None yet.">

## Not yet specified

<in-scope fog only, or "None.">

## Out of scope

<ruled-out work with reasons, or "None recorded.">
```

## Ticket format

Use a stable lowercase hyphenated id and a readable title:

```markdown
---
wayfinder:
  kind: ticket
  version: 1
  id: <ticket-id>
  title: <readable title>
  type: discussion | prototype | research | prerequisite
  interaction: human | agent
  status: open | closed | out-of-scope
  blocked_by: []
  claim:
    owner: null
    claimed_at: null
---

# <title>

## Question

<one precise question>

## Context

<only the facts needed to answer it>

## Resolution

Pending.
```

Use relative Markdown links for `blocked_by`, decisions, assets, and scope
notes. A ticket is on the frontier when `status` is `open`, each linked blocker
is closed, and it has no live claim. Preserve the ticket file order returned by
the tracker's established ordering; absent another convention, sort by filename.

## Canonical state location

Git worktrees do not share working-tree content. A lock under their shared Git
common directory does not make separate copies of `map.md` or its tickets
current. Before any claim, choose one authoritative checkout for the active map
and record its location in metadata shared by every worktree:

```text
<git-common-dir>/codex-wayfinder-maps/<map-key>/location.yaml
```

Derive `<map-key>` as the SHA-256 of the map's repository-relative path. Record:

```yaml
version: 1
map_key: <map-key>
canonical_checkout: <absolute checkout root>
map_relative_path: <repository-relative path to map.md>
git_common_dir: <absolute shared Git common directory>
established_at: <UTC timestamp>
established_by: <stable owner token or coordinator identity>
```

The coordinator or first serialized session initializes this file using an
atomic same-filesystem rename. Every participant must read it before examining
the frontier, verify that the canonical map exists and belongs to the recorded
Git common directory, and read and update the map and tickets under
`canonical_checkout`. A ticket copy in the participant's own worktree is only a
snapshot and must not be used as current state.

If the metadata is absent, incomplete, points at a missing checkout, or conflicts
with another location, do not start concurrent tickets. Serialize all map work
to one coordinator-designated checkout until the shared location is repaired.
Changing the authoritative checkout also requires serialization and an atomic
metadata replacement after all ticket and map-update reservations are released.

For a map outside Git, place equivalent location metadata under a sibling
`.wayfinder-state/<map-key>/` directory and keep it untracked. Concurrency is
safe only when every participant can access the same atomic filesystem and the
same canonical map tree.

## Same-host claims

Frontmatter alone is not an atomic claim. Sessions in worktrees of the same Git
repository share the path returned by `git rev-parse --git-common-dir`; use a
claim root below that common directory:

```text
<git-common-dir>/codex-wayfinder-claims/<map-key>/<ticket-id>.claim/
```

For a map outside Git, use a sibling `.wayfinder-claims/` directory and keep it
untracked.

The claim sequence is:

1. Resolve and verify the canonical state location, then read the ticket there.
   If it is already closed or out of scope, do not claim it.
2. Resolve a stable owner token. Prefer the Codex thread UUID plus its process
   generation when the harness exposes both. A tmux pane name, display name,
   tracker assignee, transient shell PID, or payload-claimed sender is not a
   stable owner token.
3. Atomically create the exact `<ticket-id>.claim` directory. Creating parent
   directories is preparatory; creation of the final directory is the
   compare-and-set. If it already exists, the claim failed.
4. Inside the successfully created directory, record the owner token, canonical
   map path, ticket id, and UTC claim time. An empty claim directory is still
   claimed: another session may have stopped between the atomic create and
   metadata write.
5. Reread the canonical ticket after acquiring the claim. If another session
   already closed it, release the claim without doing the work. Otherwise update
   that canonical ticket's `claim` display fields. The directory remains
   authoritative for concurrency.
6. After recording a durable resolution or an intentional release, verify the
   stored owner token matches the current session, clear the ticket display
   fields, and remove only that exact claim directory.

Never reclaim a claim merely because it is old or its tmux pane disappeared.
The original stable session must release it, or the human/coordinator must
explicitly declare it stale after checking liveness. If a stable token or shared
atomic filesystem is unavailable, allow only one worker and state that the map
is serialized.

## Updating a local map

Per-ticket claims do not serialize updates to the shared map. Use a separate,
short reservation:

```text
<git-common-dir>/codex-wayfinder-maps/<map-key>/map-update.claim/
```

Prepare the ticket answer and intended map delta before acquiring it. Never hold
the map-update reservation while asking the human a question, waiting for a
reply, researching, or prototyping.

Write the canonical ticket resolution first under its ticket claim. Then:

1. Atomically acquire `map-update.claim` and record the stable owner token and
   UTC time inside it. If acquisition fails, wait without changing the map.
2. Reread the current `map.md` from the canonical location after acquisition.
   Do not use content loaded before the reservation.
3. Apply only this ticket's delta. Preserve every existing linked decision gist
   and unrelated fog or scope edit written by other sessions. Reconcile any
   overlap explicitly instead of replacing the section wholesale.
4. Write and reread the canonical map, verify the intended delta is present,
   then release only the reservation owned by the current session.

This reservation protects one read/modify/write sequence; it does not merge or
synchronize branch contents. It is valid only because every participant uses
the canonical map tree recorded in shared location metadata. On resume, repair
a missing gist from a closed canonical ticket, but never invent a resolution
from the question or map notes.

Keep unresolved human choices as `Pending.` and `status: open`. A proposal in
the map's Destination or Notes remains proposed until a human answer is recorded
in a closed discussion ticket.
