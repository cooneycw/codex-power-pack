# Friction retro dogfood

This repository exercised the Codex-native friction retrospective against its
existing, legacy `.claude/friction.jsonl` queue on 2026-07-10. The queue was
read locally; no event content was copied into this record or sent elsewhere.

## Result

```text
python3 -m lib.friction.retro --path .claude/friction.jsonl
```

returned one non-sensitive proposal:

- kind: `validation-gate`
- evidence count: `8`
- action: add a deterministic preflight or canary check to the Makefile and CI.

Legacy rows can have changing, hook-provided wording. The analyzer therefore
uses masked fingerprints and requires the same fingerprint to repeat before it
proposes a deterministic gate. It does not conflate unrelated failures merely
because they share an allowlisted failure class. It never includes source
summaries or any other raw event content in its proposal.

The proposal is advisory. Applying a gate remains an explicit user decision;
the retro command does not modify the ledger, Makefile, CI, or any workflow.

## Verification

```text
make verify
```

completed successfully after the run.

## Precision follow-up

The retrospective after `flow:auto #176` initially proposed a validation gate
from 33 unrelated `red-output` records and an admin bootstrap blocker from two
ordinary dependency-bootstrap records. Review found no repeated fingerprint and
no admin-only, IAM, permission, or manual-apply prerequisite.

The confirmed learning is that a deterministic gate requires the same masked
failure fingerprint at least twice, while a blocking bootstrap proposal requires
explicit admin-only or manual IAM, permission, or apply evidence. No workflow
gate was added because these records did not satisfy either evidence threshold.
