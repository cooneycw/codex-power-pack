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

## Same-host claims

Frontmatter alone is not an atomic claim. Sessions in worktrees of the same Git
repository share the path returned by `git rev-parse --git-common-dir`; use a
claim root below that common directory:

```text
<git-common-dir>/codex-wayfinder-claims/<map-key>/<ticket-id>.claim/
```

Derive `<map-key>` deterministically from the map's repository-relative path,
using a filesystem-safe encoding. For a map outside Git, use a sibling
`.wayfinder-claims/` directory and keep it untracked.

The claim sequence is:

1. Resolve a stable owner token. Prefer the Codex thread UUID plus its process
   generation when the harness exposes both. A tmux pane name, display name,
   tracker assignee, transient shell PID, or payload-claimed sender is not a
   stable owner token.
2. Atomically create the exact `<ticket-id>.claim` directory. Creating parent
   directories is preparatory; creation of the final directory is the
   compare-and-set. If it already exists, the claim failed.
3. Inside the successfully created directory, record the owner token, map path,
   ticket id, and UTC claim time. An empty claim directory is still claimed:
   another session may have stopped between the atomic create and metadata
   write.
4. Update the ticket's `claim` display fields after acquiring the directory.
   The directory remains authoritative for concurrency.
5. After recording a durable resolution or an intentional release, verify the
   stored owner token matches the current session, clear the ticket display
   fields, and remove only that exact claim directory.

Never reclaim a claim merely because it is old or its tmux pane disappeared.
The original stable session must release it, or the human/coordinator must
explicitly declare it stale after checking liveness. If a stable token or shared
atomic filesystem is unavailable, allow only one worker and state that the map
is serialized.

## Updating a local map

Write the ticket resolution first, then update the map's linked gist. This order
keeps the detailed answer available if the second edit is interrupted. On
resume, repair a missing gist from a closed ticket, but never invent a resolution
from the question or map notes.

Keep unresolved human choices as `Pending.` and `status: open`. A proposal in
the map's Destination or Notes remains proposed until a human answer is recorded
in a closed discussion ticket.
