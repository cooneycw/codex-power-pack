---
name: "second-opinion-start"
description: "Obtain a host-managed multi-model review of a file, diff, or design question"
---

# Start a Second Opinion

1. Confirm `codex mcp get second-opinion` succeeds. If it does not, use the
   exact graceful-degradation message from `$second-opinion-help` and continue
   with a normal Codex review only if the user still wants one.
2. Read the explicitly requested file or diff. Never include `.env`, key files,
   credentials, or unredacted logs in the consultation payload.
3. Use the service's `get_code_second_opinion` tool for its default model or
   `get_multi_model_second_opinion` when the user selects one or more models.
   Supply code/diff, language, review question, and requested depth.
4. Return a concise synthesis: agreements, disagreements, risks, recommended
   action, model names, and reported cost. Do not treat a model response as an
   authority over repository evidence.

For a real code-review dogfood run, inspect a non-secret current diff and ask
for focused review of the changed behavior. Record only the non-sensitive
synthesis in the issue or PR.
