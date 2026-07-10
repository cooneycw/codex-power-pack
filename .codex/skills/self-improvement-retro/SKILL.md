---
name: "self-improvement-retro"
description: "Turn masked Codex friction telemetry into user-confirmed workflow improvements"
---

# Friction Retro

Use this skill after a difficult run to identify recurring process failures and
propose durable fixes. It reads only minimized, masked Codex telemetry and never
prints raw tool output, prompts, environment values, or credentials.

## Procedure

1. Prefer `.codex/friction.jsonl`; treat `.claude/friction.jsonl` as an optional
   legacy import and do not create new records there.
2. In a CxPP checkout, generate proposals with:

```bash
python3 -m lib.friction.retro --path .codex/friction.jsonl
```

3. Treat every output as a proposal, not an automatic change. De-duplicate it
   against already applied/rejected learnings, then show the evidence count and
   exact proposed action for confirmation.
4. When the same command, gate, or tool failure occurs at least twice, propose a
   deterministic Makefile/CI preflight or canary validation gate. This is the
   required repeated-failure response: fix the class, not only the latest run.
5. When a signal identifies an admin-only bootstrap, IAM, or manual apply
   dependency, propose a **blocking** `bootstrap-check` before merge, deploy, or
   retry. The check must name the required manual action and exit non-zero until
   it is complete.
6. Apply a proposal only after explicit user confirmation, then run the smallest
   relevant gate followed by `make verify`. Record the outcome as masked local
   learning or an actionable issue candidate.

If no telemetry exists, report that fact and offer to analyze the current
conversation without inventing evidence.
