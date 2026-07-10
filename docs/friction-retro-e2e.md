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
uses exact fingerprints when available and falls back to a repeated allowlisted
failure class only when no exact match is found. It never includes source summaries
or any other raw event content in its proposal.

The proposal is advisory. Applying a gate remains an explicit user decision;
the retro command does not modify the ledger, Makefile, CI, or any workflow.

## Verification

```text
make verify
```

completed successfully after the run.
