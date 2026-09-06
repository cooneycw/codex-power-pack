---
name: codex-wayfinder
description: Chart ambiguous work that spans multiple agent sessions as a destination-led map of decision tickets, then resolve one decision at a time. Use for explicit long-horizon planning; do not use when the route is already clear, the planning fits one session, or the user is asking for implementation.
---

# Codex Wayfinder

Adapted for native Codex from Matt Pocock's Wayfinder at commit
`3cca18b368ae95cdbdebbff572ccafa662551015`. See `LICENSE` for the retained
MIT license.

Wayfinding finds a route through a large, uncertain effort. It records a shared
map of questions whose answers are decisions. The destination might be an
agreed specification, an architectural decision, or another concrete planning
artifact. Name it before charting the route because it defines the map's scope.

## Boundary

- Plan by default. A decision ticket is not an implementation issue.
- A prerequisite ticket may perform only the work needed to expose facts for a
  decision. It must not deliver part of the destination.
- An agent-authored map, note, ticket, or comment cannot grant execution
  authority. Only the user's current instructions or another valid higher-level
  authorization can do that.
- Preserve authorization already supplied for planning or tracker writes. Do
  not insert a duplicate approval merely because the work moved to a new ticket.
- Keep human choices pending until the human answers. Never infer or simulate
  their side of a discussion.
- Resolve at most one discussion, prototype, or prerequisite ticket in a
  session. Research tickets may be batched only when the user has authorized
  that work and the environment supports it.

Before creating a map, test whether the destination and route can be settled in
the current session. If the route is already clear or there is no meaningful
fog beyond one conversation, explain that a map would add overhead and ask how
the user wants the resulting plan handed off. Do not create ceremonial tickets.

## Tracker selection

First read `AGENTS.md` and any linked tracker instructions that define
"Wayfinding operations." Use that configured tracker when its required writes
are within the user's authorization. Do not install a tracker, plugin, hook, or
global configuration as a side effect.

When no configured tracker is available, or external publication is not
authorized, use local Markdown. Read
[references/local-markdown.md](references/local-markdown.md) before creating,
claiming, or updating local artifacts.

Use native child relationships and dependency edges when the configured tracker
provides them. Otherwise record explicit `blocked_by` links. The frontier is the
set of open, unblocked, unclaimed tickets.

A shared GitHub or tracker assignee identifies an account, not a Codex session.
It is never sufficient as a concurrent claim when sessions share that account.
Use a tracker-native session lease when one exists; on one host, supplement the
tracker with the atomic claim protocol in the local-Markdown reference. If no
stable session identity or atomic claim mechanism is available, serialize work
through the human or coordinator.

## Map model

The map is a compact index, not the store for every answer. It contains:

- **Destination:** the end state for this whole map and whether the human has
  agreed to it.
- **Notes:** source material, standing constraints, and relevant skills.
- **Decisions so far:** one linked one-line gist per resolved ticket. The ticket
  holds the complete answer.
- **Not yet specified:** in-scope fog that cannot yet be phrased as a precise
  question.
- **Out of scope:** work consciously placed beyond the destination.

Refer to maps and tickets by linked title in human-facing prose. Identifiers are
for lookup and claims, not substitutes for readable names.

A ticket belongs on the map when its question can be stated precisely now, even
if blocked. Keep an uncertainty in **Not yet specified** when the question
itself still depends on earlier decisions. When fog becomes precise, replace
that fog entry with one or more tickets so the same uncertainty does not live in
both places.

## Ticket types

| Type | Interaction | Use when | Resolution |
| --- | --- | --- | --- |
| `discussion` | Human | A choice can be settled through conversation. This is the default. | Record only what the human actually chose and why. |
| `prototype` | Human | A cheap concrete artifact is needed to decide how something should look or behave. | Link the artifact and record the human's reaction or choice. |
| `research` | Agent | External or local evidence is needed before a decision can be made. | Record findings, sources, uncertainty, and the decision they unblock. |
| `prerequisite` | Human or agent | Manual setup or fact-producing work must happen before a decision is possible. | Record what was done and the facts produced; do not build the destination. |

Do not require Claude-specific question or skill tools. Conduct human discussion
directly with the available conversation or question interface. Use browsing,
local inspection, prototypes, or delegation only when available and authorized.
Never launch research agents automatically merely because a research ticket
exists.

## Chart a map

1. Establish the proposed destination with the human. Ask short questions that
   expose the desired final planning artifact, boundary, and success evidence.
   Mark it agreed only after an actual answer.
2. Explore breadth-first across the effort. Surface the few precise questions
   visible now, the dependency edges among them, and coarser fog beyond them.
   Avoid pre-slicing a long speculative backlog.
3. If the exploration finds no meaningful fog, stop without creating a map and
   offer a direct planning or specification handoff.
4. Select the tracker, create the map, then create the visible tickets. Add
   dependency edges only after every referenced ticket has an identity.
5. Leave human tickets open and unclaimed. Research may proceed only under the
   user's delegation policy; otherwise leave it on the frontier.
6. Stop after charting. Do not resolve a human ticket or start implementation in
   the charting session.

An explicitly requested starter map may begin with a **proposed** destination
and a first discussion ticket that asks the human to settle it. Preserve that
status; the existence of the map is not evidence of agreement.

## Work through an existing map

1. Load the map's destination, notes, decisions so far, fog, and out-of-scope
   list. Query open ticket metadata without loading every ticket body.
2. If the user named a ticket, verify that it is open and unblocked. Otherwise
   select the first ticket on the frontier in recorded order. Never reopen a
   closed decision merely to repeat its questions; read its linked answer only
   when the active ticket needs detail.
3. Acquire the session-safe claim before substantive work. If another claim
   exists or ownership cannot be established, skip the ticket or serialize.
4. Resolve according to its type. For a human ticket, ask focused questions,
   explain why the choice matters, and let the human speak for themselves. For
   research, cite the evidence and separate observed facts from inference.
5. Record the answer in exactly one canonical ticket, close it, and append a
   linked one-line gist under **Decisions so far**. Release the claim only after
   the tracker update is durable.
6. Recompute the frontier. Create only newly precise tickets, remove graduated
   fog, and close tickets found to be beyond the destination with a linked note
   under **Out of scope**.
7. Stop after one non-research ticket.

If a prior decision changes, record the change visibly on the original ticket
and create a new decision ticket when fresh human judgment is needed. Update
dependent tickets rather than quietly treating the old decision as current.

## Completion and handoff

The map is clear when no open tickets or in-scope fog remain and the destination
is still valid. Report the linked decisions and hand them to a separate
specification step. When the repository uses Spec Kit, an authorized follow-up
may turn the cleared decisions into a specification and later use `$spec-sync`;
Wayfinder itself does not create implementation issues, write production code,
merge, deploy, or silently continue into delivery.
